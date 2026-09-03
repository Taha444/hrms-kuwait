# -*- coding: utf-8 -*-
"""V-B — إعادة توليد العقد الحكومي: هل ما زال السلوك يسمح؟

**التحقيق**: سجّلت المراجعة خمس توليدات تاريخية لعقد واحد. والسؤال ليس
«هل التكرار ممكن» — فإعادة التوليد بعد تصحيح بيانات موظف عمل مشروع —
بل **متى يصير التكرار ضرًرا**.

والجواب: حين يوقّع الموظف. عندها تنشأ ثلاث نسخ لها معنى قانوني:
المولَّدة، والموقّعة من الموظف، والموقّعة من الطرفين. وإعادة التوليد بعد
التوقيع تُنشئ نسخة «سارية» تختلف عمّا وقّعه الموظف بيده — فيُقدَّم إلى
الجهة عقدٌ لم يوقّعه أحد، أو يُحتجّ بتوقيع على نصّ غيره.

فالقياس هنا على هذه الحدود بالذات، لا على العدد.
"""
from __future__ import annotations

import io
from datetime import date, timedelta

import pytest
from sqlalchemy import and_ as sa_and, delete as sa_delete, or_ as sa_or, select

from app import models
from app import renewal as R
from app.database import SessionLocal
from tests.conftest import auth_headers, login

PRO = ("100000000003", "deleg123")


def _f():
    return {"file": ("doc.pdf", io.BytesIO(b"content"), "application/pdf")}


@pytest.fixture
def case(client):
    """معاملة تجديد على موظف يُبنى هنا — لا تنافس على بيانات البذرة."""
    db = SessionLocal()
    made = {}
    try:
        pro = db.scalar(select(models.User).where(
            models.User.civil_id == PRO[0]))
        emp = models.Employee(
            company_id=pro.company_id, name="موظف فحص التوليد",
            name_en="Regeneration Test", civil_id="255500110077",
            job_title="فني", job_title_en="Technician", basic_salary=350,
            passport_number="PRG0001", status="active", nationality="مصري")
        db.add(emp)
        db.flush()
        db.add(models.Permit(
            company_id=emp.company_id, employee_id=emp.id, kind="residency",
            number=f"RES-RG-{emp.id}",
            start_date=date.today() - timedelta(days=345),
            expiry_date=date.today() + timedelta(days=20), status="active"))
        db.commit()
        eid = emp.id
    finally:
        db.close()

    hdr = auth_headers(login(client, *PRO))
    r = client.post("/api/renewals", headers=hdr, data={"employee_id": eid})
    assert r.status_code == 201, r.text
    made = {"rid": r.json()["id"], "eid": eid}
    yield hdr, made["rid"]

    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Document).where(sa_or(
            sa_and(models.Document.entity_type == "renewal",
                   models.Document.entity_id == made["rid"]),
            sa_and(models.Document.entity_type == "employee",
                   models.Document.entity_id == made["eid"]))))
        db.execute(sa_delete(models.Task).where(sa_or(
            sa_and(models.Task.related_entity_type == "renewal",
                   models.Task.related_entity_id == made["rid"]),
            sa_and(models.Task.related_entity_type == "employee",
                   models.Task.related_entity_id == made["eid"]))))
        db.execute(sa_delete(models.ResidencyRenewal).where(
            models.ResidencyRenewal.id == made["rid"]))
        db.execute(sa_delete(models.Permit).where(
            models.Permit.employee_id == made["eid"]))
        db.execute(sa_delete(models.Employee).where(
            models.Employee.id == made["eid"]))
        db.commit()
    finally:
        db.close()


def _generate(client, hdr, rid):
    return client.post(f"/api/renewals/{rid}/gov-contract/generate", headers=hdr)


def test_generation_works_at_all(client, case):
    """خطّ الأساس — بلا توليد ناجح لا معنى لما بعده."""
    hdr, rid = case
    r = _generate(client, hdr, rid)
    assert r.status_code == 200, r.text


def test_regenerating_before_signature_is_allowed(client, case):
    """**وهذا مقصود**: تصحيح بيانات موظف ثم إعادة التوليد عمل مشروع.

    منعه يدفع المندوب إلى فتح معاملة ثانية — وهو أسوأ.
    """
    hdr, rid = case
    assert _generate(client, hdr, rid).status_code == 200
    again = _generate(client, hdr, rid)
    assert again.status_code == 200, (
        f"مُنعت إعادة التوليد قبل التوقيع: {again.text[:200]}"
    )


def test_regenerating_after_the_employee_signed_is_refused(client, case):
    """**الحدّ الذي يهمّ**: بعد التوقيع، النسخة السارية تصير غير ما وُقّع.

    فيُقدَّم إلى الجهة عقد لم يوقّعه أحد، أو يُحتجّ بتوقيع على نصّ غيره.
    """
    hdr, rid = case
    assert _generate(client, hdr, rid).status_code == 200
    client.post(f"/api/renewals/{rid}/upload", headers=hdr,
                data={"doc_type": "renewal_contract_gov"}, files=_f())
    client.post(f"/api/renewals/{rid}/upload", headers=hdr,
                data={"doc_type": "renewal_signed_gov"}, files=_f())

    st = client.get(f"/api/renewals/{rid}", headers=hdr).json()["status"]
    assert st == R.CONTRACTS_SIGNED, f"لم نصل لحالة التوقيع: {st}"

    r = _generate(client, hdr, rid)
    assert r.status_code == 409, (
        "أُعيد توليد العقد بعد توقيع الموظف — النسخة السارية تفارق الموقّعة"
    )
    assert "وقّع" in r.json()["detail"] or "توقيع" in r.json()["detail"], (
        f"الرفض لا يشرح سببه: {r.json()}"
    )


def test_the_signed_copy_survives_the_refusal(client, case):
    """والرفض لا يمسّ ما وُقّع: النسخة الموقّعة تبقى كما هي."""
    hdr, rid = case
    _generate(client, hdr, rid)
    client.post(f"/api/renewals/{rid}/upload", headers=hdr,
                data={"doc_type": "renewal_contract_gov"}, files=_f())
    client.post(f"/api/renewals/{rid}/upload", headers=hdr,
                data={"doc_type": "renewal_signed_gov"}, files=_f())
    _generate(client, hdr, rid)          # يُرفض

    db = SessionLocal()
    try:
        signed = db.scalars(select(models.Document).where(
            models.Document.entity_type == "renewal",
            models.Document.entity_id == rid,
            models.Document.document_type_code == R.DOC_SIGNED_GOV)).all()
    finally:
        db.close()
    assert signed, "اختفت النسخة الموقّعة"
    assert any(d.is_current for d in signed), "النسخة الموقّعة لم تعد سارية"
