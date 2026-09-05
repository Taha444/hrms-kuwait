# -*- coding: utf-8 -*-
"""P6-27 — حالة نهاية الخدمة هي المرجع، ومسار الطلبات يبلغها.

**قرار المالك**: ``EosCase`` هي المرجع.

**وما ظهر بالقياس**: مسار الطلبات **لا يبلغ المرجع إطلاًقا**. لا نوع
خروج له أثر عند الاكتمال — يقدّم الموظف استقالته، ويعتمدها المدير
وشؤون الموظفين، ويوقّعها، فيُختم الطلب «مكتمل»… ولا حالة نهاية خدمة
تُفتح، ولا يتغيّر شيء في ملفه. فيبقى على رأس العمل في كل تقرير حتى
يتذكّر أحدهم أن يفتح الحالة يدًوا.

وهو النمط الثالث في هذه الجولة بعد ``REQSIG`` والمستند المولَّد:
**إجراء يُعلَن ناجًحا ولا يقع أثره**.

**والإنشاء من مصدر واحد**: كان مكتوًبا داخل ``initiate_case`` وحدها،
فربطُ الطلبات به كان يعني نسخة ثانية — ونسختان لقاعدة واحدة تنحرف
إحداهما.
"""
from __future__ import annotations

import inspect

import pytest
from sqlalchemy import delete as sa_delete, select

from app import exit_case, models, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")
MGR = ("100000000001", "manager123")

RESIGN = {"submitted_at": "2027-04-01", "proposed_last_day": "2027-05-01",
          "notice_period_days": 30, "reason": "ظروف شخصية"}


@pytest.fixture
def leaver():
    """موظف يُساق إلى الخروج، ثم يُنظَّف أثره كلّه."""
    db = SessionLocal()
    eid = None
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
        # الشرط المسبق يُثبَّت لا يُفترَض: «لا خروج آخر مفتوح». وموظف
        # البذرة يتشاركه اختبارات أخرى، وبعضها يفتح مرجًعا ويتركه.
        db.execute(sa_delete(models.EosCase).where(
            models.EosCase.employee_id == eid))
        db.commit()
        yield eid
    finally:
        db.execute(sa_delete(models.EosCase).where(
            models.EosCase.employee_id == eid))
        rows = [r for (r,) in db.execute(select(models.Request.id).where(
            models.Request.employee_id == eid,
            models.Request.request_type_code.in_(("REQRESIGN", "REQEOS")))).all()]
        if rows:
            for tbl in (models.Task, models.RequestApproval, models.RequestDocument):
                col = (models.Task.related_entity_id if tbl is models.Task
                       else tbl.request_id)
                stmt = sa_delete(tbl).where(col.in_(rows))
                if tbl is models.Task:
                    stmt = stmt.where(models.Task.related_entity_type == "request")
                db.execute(stmt)
            db.execute(sa_delete(models.Request).where(models.Request.id.in_(rows)))
        db.commit()
        db.close()


def _resign_to_completion(client, eid: int) -> int:
    """يسوق استقالة كاملة — بما فيها التوقيع (P5-23)."""
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQRESIGN",
        "payload_json": RESIGN})
    assert r.status_code == 201, r.text[:250]
    rid = r.json()["id"]
    for who in (MGR, HR):
        d = client.post(f"/api/requests/{rid}/decide",
                        headers=auth_headers(login(client, *who)),
                        json={"decision": "approved"})
        assert d.status_code == 200, d.text[:200]

    hh = auth_headers(login(client, *HR))
    body = client.get(f"/api/requests/{rid}", headers=hh).json()
    assert body["status"] == "awaiting_signature", body["status"]
    signed = client.post(f"/api/requests/{rid}/documents", headers=hh,
                         data={"kind": "signed_scan"},
                         files={"file": ("s.pdf", b"%PDF-1.4", "application/pdf")})
    assert signed.status_code in (200, 201), signed.text[:200]
    return rid


def test_a_completed_resignation_opens_the_master_case(client, leaver):
    """**جوهر البند**: الاستقالة المكتملة تفتح المرجع، لا تُختم وتُنسى."""
    rid = _resign_to_completion(client, leaver)

    db = SessionLocal()
    try:
        req = db.get(models.Request, rid)
        cases = db.scalars(select(models.EosCase).where(
            models.EosCase.employee_id == leaver)).all()
    finally:
        db.close()

    assert req.status == "completed", req.status
    assert cases, "اكتملت الاستقالة ولا حالة نهاية خدمة — المرجع لم يُبلَغ"
    assert len(cases) == 1, f"فُتح أكثر من مرجع: {[c.id for c in cases]}"


def test_the_case_records_where_it_came_from(client, leaver):
    """والرابط في الاتجاهين: من يقرأ المرجع يعرف أصله."""
    rid = _resign_to_completion(client, leaver)
    db = SessionLocal()
    try:
        case = db.scalar(select(models.EosCase).where(
            models.EosCase.employee_id == leaver))
    finally:
        db.close()
    assert case.source_request_id == rid, (
        f"المرجع بلا أصل: source={case.source_request_id} والطلب {rid}"
    )


def test_the_case_carries_the_data_the_request_declared(client, leaver):
    """ولا يُفتح المرجع بتاريخ مخترع: التاريخ والسبب من الطلب نفسه."""
    _resign_to_completion(client, leaver)
    db = SessionLocal()
    try:
        case = db.scalar(select(models.EosCase).where(
            models.EosCase.employee_id == leaver))
    finally:
        db.close()
    assert str(case.termination_date) == RESIGN["proposed_last_day"], (
        f"تاريخ المغادرة يخالف الطلب: {case.termination_date}"
    )
    assert case.termination_reason == "resignation", case.termination_reason
    assert case.status == "initiated", case.status
    assert case.reference_no and case.reference_no.startswith("EOS/"), (
        case.reference_no
    )


def test_the_actor_is_the_person_who_completed_it(client, leaver):
    """ومن فتح المرجع هو من أتمّ الطلب، لا «النظام»."""
    _resign_to_completion(client, leaver)
    db = SessionLocal()
    try:
        case = db.scalar(select(models.EosCase).where(
            models.EosCase.employee_id == leaver))
    finally:
        db.close()
    assert case.initiated_by, "فُتح المرجع بلا منفذ"


def test_creation_lives_in_one_place():
    """**والقاعدة في موضع واحد**: نسختان تنحرف إحداهما.

    كان المنطق مكتوًبا داخل ``initiate_case`` وحدها.
    """
    from app.routers import eos as eos_router

    src = inspect.getsource(eos_router.initiate_case)
    assert "exit_case.open_case" in src, "الراوتر لا يقرأ المصدر الواحد"
    assert "models.EosCase(" not in src, (
        "عاد الراوتر يُنشئ الحالة بنفسه — نسخة ثانية من القاعدة"
    )


def test_the_effect_goes_through_the_same_door():
    """ويمرّ الأثر من باب الآثار لا من طريق ثانٍ.

    فيرث ذرّيته ومسار ``apply_failed`` — فلو تعذّر فتح المرجع صار
    الطلب متعثًّرا بسببه المكتوب، لا «مكتمًلا» بلا أثر.
    """
    src = inspect.getsource(workflow._finalize)
    assert "REQRESIGN" in src and "REQEOS" in src, (
        "طلبات الخروج ليست في جدول الآثار"
    )
    assert "_open_exit_case" in src


def test_a_failure_to_open_the_master_is_not_silent(client, leaver, monkeypatch):
    """وفشل فتح المرجع يُعلَن: الطلب يتعثّر ولا يُختم «مكتمًلا» بلا أثر."""
    monkeypatch.setattr(exit_case, "open_case",
                        lambda *a, **k: (_ for _ in ()).throw(
                            __import__("fastapi").HTTPException(
                                status_code=409, detail="سبب اختباري")))
    rid = _resign_to_completion(client, leaver)
    db = SessionLocal()
    try:
        req = db.get(models.Request, rid)
        cases = db.scalars(select(models.EosCase).where(
            models.EosCase.employee_id == leaver)).all()
    finally:
        db.close()
    assert not cases, "فُتح مرجع رغم فشل الفتح"
    assert req.status == "apply_failed", (
        f"فشل فتح المرجع وخُتم الطلب «{req.status}»"
    )


def test_reopening_does_not_create_a_second_master(client, leaver):
    """وإعادة إنهاء الطلب لا تفتح مرجًعا ثانًيا."""
    rid = _resign_to_completion(client, leaver)
    db = SessionLocal()
    try:
        req = db.get(models.Request, rid)
        ok, note = exit_case.open_from_request(db, req)
        cases = db.scalars(select(models.EosCase).where(
            models.EosCase.employee_id == leaver)).all()
    finally:
        db.close()
    assert ok, note
    assert len(cases) == 1, f"فُتح مرجع ثانٍ: {[c.id for c in cases]}"


def test_clearance_is_not_wired_to_advance_the_case():
    """**وREQCLR لم يُوصَل قصًدا** — والسبب يُقال لا يُسكَت عنه.

    إخلاء الطرف مرحلة داخل المرجع (``clearance``) ولها منفذها وسببها
    ونصّها. وجعلُ اكتمال ``REQCLR`` يتقدّم بالمرحلة يعني تسجيل إقرار
    باسم من لم يقرّه — تزوير فاعل، وهو ما عالجته P11-36 لا ما يُعاد.
    """
    assert "REQCLR" not in exit_case.EXIT_REQUEST_SPEC, (
        "وُصِل REQCLR بفتح المرجع — وهو خطوة داخله لا بداية له"
    )
