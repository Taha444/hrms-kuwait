# -*- coding: utf-8 -*-
"""V-G — الرفض على الخادم لا في الواجهة.

يحذّر الكيت: بعد إصلاح إخفاء الأزرار، **تأكّد أن الـPOST نفسه يرفض**.
وواجهة تُخفي الزرّ ليست حماية — من يعرف المسار يفتح الطلب بأمر واحد،
ويصير للنظام طلب مفتوح باسم موظف انتهت خدمته: مهمة تصل معتمًِدا،
وربما مستند رسمي يُطبع باسم من لم يعد على رأس العمل.

وهذا فحص **تحقيق** لا إصلاح: قد يكون الخادم يرفض أصًلا.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")


@pytest.fixture
def terminated_employee():
    """موظف منتهية خدمته في شركة من يسأل — يُبنى ويُحذف."""
    db = SessionLocal()
    made = None
    try:
        hr = db.scalar(select(models.User).where(models.User.civil_id == HR[0]))
        emp = models.Employee(
            company_id=hr.company_id, name="موظف منتهية خدمته",
            name_en="Terminated Employee", civil_id="266600110099",
            job_title="فني", basic_salary=300, status="terminated",
            nationality="مصري")
        db.add(emp)
        db.commit()
        made = emp.id
        yield emp.id
    finally:
        if made:
            db.execute(sa_delete(models.Request).where(
                models.Request.employee_id == made))
            db.execute(sa_delete(models.Employee).where(
                models.Employee.id == made))
            db.commit()
        db.close()


def _request_type(db):
    return db.scalars(select(models.RequestType)).first()


#: حمولة إجازة مكتملة.
#:
#: **ولماذا مكتملة**: أول كتابة أرسلت ``{}`` فردّ الخادم 400 لنقص الحقول
#: — في الحالتين معًا، للمنتهية خدمته وللنشط. فمرّ الاختبار أخضر وهو لم
#: يبلغ بوّابة الحالة إطلاًقا. ورفضٌ لسبب آخر ليس إثبات منع.
LEAVE_PAYLOAD = {
    "start_date": "2026-10-01",
    "end_date": "2026-10-03",
    "days": 3,
    "leave_type": "annual",
    "reason": "فحص بوّابة حالة الموظف",
}


def _leave_code(db) -> str:
    """كود نوع الإجازة — تُقرأ حمولته من مخطّطه لا من التخمين."""
    from app import form_schemas

    for rt in db.scalars(select(models.RequestType)).all():
        if form_schemas.get_schema(rt.code) and "leave" in (rt.code or "").lower():
            return rt.code
    return db.scalars(select(models.RequestType)).first().code


def test_the_fixture_really_builds_a_terminated_employee(terminated_employee):
    """ادّعاء على موظف نشط لا يقيس شيًئا."""
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, terminated_employee)
        assert emp.status == "terminated", emp.status
    finally:
        db.close()


def test_the_server_itself_refuses_a_request_for_a_terminated_employee(
        client, terminated_employee):
    """**السؤال**: هل يرفض الخادم، أم تكتفي الواجهة بإخفاء الزرّ؟"""
    db = SessionLocal()
    try:
        code = _leave_code(db)
    finally:
        db.close()

    hdr = auth_headers(login(client, *HR))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": terminated_employee,
        "request_type_code": code,
        "payload_json": LEAVE_PAYLOAD,
    })
    assert r.status_code != 201, (
        f"فُتح طلب باسم موظف منتهية خدمته — الحماية في الواجهة وحدها: {r.text[:200]}"
    )
    # والرفض لسببه: رسالة عن حالة الموظف لا عن حقل ناقص.
    detail = str(r.json().get("detail", ""))
    assert not any(w in detail for w in ("مطلوب", "required")), (
        f"رُفض لنقص حقول لا لحالة الموظف — البوّابة لم تُختبَر: {detail[:200]}"
    )


def test_no_request_row_was_created(client, terminated_employee):
    """و«رُفض» تعني ألّا يبقى صفّ — لا رفض بعد كتابة."""
    db = SessionLocal()
    try:
        n = db.scalar(select(models.Request).where(
            models.Request.employee_id == terminated_employee))
    finally:
        db.close()
    assert n is None, "رُفض الطلب وبقي صفّه في القاعدة"


def test_an_active_employee_is_still_accepted(client):
    """والحدّ المقابل: منع يشمل الجميع ليس منًعا.

    لو رُدّ كل طلب لأي سبب آخر، لمرّ الاختبار أعلاه وهو لا يقيس الحالة.
    """
    db = SessionLocal()
    try:
        hr = db.scalar(select(models.User).where(models.User.civil_id == HR[0]))
        active = db.scalar(select(models.Employee).where(
            models.Employee.company_id == hr.company_id,
            models.Employee.status == "active"))
        emp_id, code = active.id, _leave_code(db)
    finally:
        db.close()

    hdr = auth_headers(login(client, *HR))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": emp_id, "request_type_code": code,
        "payload_json": LEAVE_PAYLOAD,
    })
    assert r.status_code == 201, (
        f"حتى الموظف النشط مرفوض — القياس السابق بلا معنى: "
        f"{r.status_code} {r.text[:200]}"
    )
