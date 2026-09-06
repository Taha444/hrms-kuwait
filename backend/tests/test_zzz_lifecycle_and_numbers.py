# -*- coding: utf-8 -*-
"""البنود 17 و24 و25 — دورة حياة المستند، والرقم الوظيفي.

**17 — ``ARCHIVED`` كانت تُقرأ ولا تُكتَب أبًدا.** يمرّ المستند بالطباعة
والحفظ ويبقى ``GENERATED`` إلى الأبد، فلا حالة نهائية له في السجل.

**وموضعها الحفظ لا التوليد**: التوليد يُدخل المستند أرشيف الموظف
(P1-03)، لكن نسخًة أحدث قد تعلوه — وحارس التوليد لا يخفض ``ARCHIVED``
إلى ``SUPERSEDED``. فلو وُسمت عند الصدور لَما صار مستنٌد مستبدًَلا أبًدا.

**25 — الكشف كان يحمل معرّف القاعدة وحده.** رقٌم داخلي يتغيّر بين
البيئات ولا يعرفه أحد خارجها، والورقة تُنسَب للرقم الوظيفي.

**24 — والتعبئة أداة قائمة لم تُشغَّل**: 26 من 26 موظًفا بلا رقم على
قاعدة التطوير. القياس هنا يثبت أنها تعمل وقابلة لإعادة التشغيل ولا
تمسّ رقًما قائًما.
"""
from __future__ import annotations

import io as _io

from sqlalchemy import func, select

from app import employee_no as en, models, payroll
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
SUP = ("100000000005", "sup12345")
HR = ("100000000002", "hr12345")
MGR = ("100000000001", "manager123")


def _leave_with_document(client, day: str) -> int:
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()
    hdr = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQLV",
        "payload_json": {"start_date": f"2032-{day}-01", "end_date": f"2032-{day}-03",
                         "days": 3, "leave_type": "unpaid",
                         "reason": "قياس دورة الحياة"}}).json()["id"]
    for who in (SUP, HR):
        client.post(f"/api/requests/{rid}/decide",
                    headers=auth_headers(login(client, *who)),
                    json={"decision": "approved"})
    return rid


def _lifecycle(rid: int) -> str:
    db = SessionLocal()
    try:
        doc = db.scalar(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid,
            models.RequestDocument.kind == "generated_pdf"))
        return doc.lifecycle_status
    finally:
        db.close()


def test_filing_completes_the_document_lifecycle(client):
    """**جوهر البند 17**: الحفظ يُنهي الدورة بدل أن يتركها معلَّقة."""
    rid = _leave_with_document(client, "03")
    assert _lifecycle(rid) == "GENERATED", "لم يُولَّد المستند"

    mgr = auth_headers(login(client, *MGR))
    hr = auth_headers(login(client, *HR))
    p = client.post(f"/api/requests/{rid}/document/generated_pdf/mark-printed",
                    headers=mgr)
    assert p.status_code == 200, p.text[:200]
    f = client.post(f"/api/requests/{rid}/document/generated_pdf/mark-filed",
                    headers=hr)
    assert f.status_code == 200, f.text[:200]
    assert _lifecycle(rid) == "ARCHIVED", _lifecycle(rid)


def test_generation_alone_does_not_archive(client):
    """**وموضعها الحفظ لا التوليد.**

    فلو وُسمت عند الصدور لَما صار مستنٌد ``SUPERSEDED`` أبًدا: حارس
    التوليد لا يخفض ``ARCHIVED``، فيبقى القديم «مؤرشًفا» بجانب الأحدث
    ولا يُعرف أيّهما السارية.
    """
    import inspect

    from app import workflow

    rid = _leave_with_document(client, "04")
    assert _lifecycle(rid) == "GENERATED", "أُرشِف عند التوليد"

    src = inspect.getsource(workflow.generate_document)
    assert '"SUPERSEDED", "ARCHIVED"' in src, (
        "تغيّر حارس التوليد — أعد النظر في موضع الأرشفة"
    )


def test_the_payslip_carries_the_employee_number(client):
    """**البند 25**: الورقة تُنسَب للرقم الوظيفي لا لمعرّف القاعدة."""
    db = SessionLocal()
    try:
        en.backfill_missing(db, company_id=1)
        db.commit()
        res = payroll.compute_payroll(db, 1, 2026, 3)
    finally:
        db.close()
    assert res["payslips"], "لا كشوف"
    row = res["payslips"][0]
    assert "employee_no" in row, sorted(row)
    assert row["employee_no"], "الرقم فارغ رغم التعبئة"
    # ويبقى المعرّف الداخلي للربط لا للعرض.
    assert "employee_id" in row


def test_the_backfill_fills_and_repeats_safely(client):
    """**البند 24**: تُعبَّئ الأرقام الناقصة ولا يُمسّ رقٌم قائم."""
    db = SessionLocal()
    try:
        en.backfill_missing(db, company_id=None)
        db.commit()
        sample = db.scalar(select(models.Employee).where(
            models.Employee.employee_no.is_not(None)))
        kept = sample.employee_no
        missing = db.scalar(select(func.count()).select_from(models.Employee).where(
            (models.Employee.employee_no.is_(None))
            | (models.Employee.employee_no == "")))
        again = en.backfill_missing(db, company_id=None)
        db.commit()
        still = db.get(models.Employee, sample.id).employee_no
    finally:
        db.close()
    assert missing == 0, f"بقي {missing} بلا رقم"
    assert again == 0, "إعادة التشغيل أنشأت أرقاًما جديدة"
    assert still == kept, f"تغيّر رقم قائم: {kept} → {still}"


def test_the_numbers_are_readable_not_raw_ids(client):
    """والرقم يُقرأ: لاحقة الفرع وتسلسل — لا معرّف قاعدة معاد تسميته."""
    db = SessionLocal()
    try:
        en.backfill_missing(db, company_id=None)
        db.commit()
        nums = [e.employee_no for e in db.scalars(
            select(models.Employee).limit(5)) if e.employee_no]
    finally:
        db.close()
    assert nums, "لا أرقام"
    for n in nums:
        assert "-" in n and any(ch.isdigit() for ch in n), n
