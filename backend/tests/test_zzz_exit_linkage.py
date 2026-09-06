# -*- coding: utf-8 -*-
"""بابا الخروج يفتحان المرجع نفسه، والتايملاين يروي القصة (18 و19).

**العطل (18)**: الاستقالة و طلب التسوية يفتحان حالة نهاية خدمة عبر
``exit_case.open_from_request``. أما الإنهاء من الإدارة
(``/terminate/execute``) فكان يختم الحالة ويحسب التسوية **ثم يقف**: لا
مرجع يُفتَح ولا رابط. فينتهي موظف من باب ويبقى خروجه بلا أثر في المرجع
الذي يُفتّش فيه.

**والعطل (19)**: سجلّ الحالة جيّد وسجلّ الإنهاء جيّد، وكلٌّ في مكانه —
ومن يفتح ملف الموظف ليقرأ سيرته لا يجد خروجه: يرى إجازاته ومستنداته ثم
ينقطع الخيط عند أهمّ حدث في الملف.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
ACC = ("100000000007", "account123")
ADMIN = ("000000000000", "admin123")


def _fresh_employee(db) -> models.Employee:
    """موظف خاصٌّ بهذا القياس — لا نمسّ من تستعمله اختبارات أخرى."""
    e = models.Employee(
        company_id=1, name="موظف قياس الخروج", civil_id="299000000777",
        hire_date=date.today() - timedelta(days=800), basic_salary=500.0,
        status="active", nationality="مصري", job_title="فنّي")
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _drive_termination(client, emp_id: int) -> dict:
    """يمرّ بكل المراحل الإلزامية حتى التنفيذ."""
    hr = auth_headers(login(client, *HR))
    acc = auth_headers(login(client, *ACC))
    end = (date.today() + timedelta(days=5)).isoformat()

    r = client.post(f"/api/employees/{emp_id}/terminate",
                    headers=hr, params={"end_date": end, "reason": "termination"})
    assert r.status_code == 200, r.text[:250]
    for path, hdr in ((f"/api/employees/{emp_id}/terminate/approve", acc),
                      (f"/api/employees/{emp_id}/terminate/clearance", hr),
                      (f"/api/employees/{emp_id}/terminate/acknowledge", hr)):
        rr = client.post(path, headers=hdr)
        assert rr.status_code == 200, f"{path}: {rr.text[:200]}"
    done = client.post(f"/api/employees/{emp_id}/terminate/execute", headers=hr)
    assert done.status_code == 200, done.text[:250]
    return done.json()


def test_an_administrative_termination_opens_the_exit_case(client):
    """**جوهر العطل**: باب الإدارة كان يُنهي بلا مرجع."""
    db = SessionLocal()
    try:
        emp = _fresh_employee(db)
        eid = emp.id
    finally:
        db.close()

    out = _drive_termination(client, eid)
    assert out.get("exit_case_id"), f"أُنهيت الخدمة بلا مرجع: {out}"

    db = SessionLocal()
    try:
        case = db.get(models.EosCase, out["exit_case_id"])
        assert case is not None and case.employee_id == eid
        assert case.termination_date is not None
        assert case.reference_no, "مرجع بلا رقم مرجعي"
    finally:
        db.close()


def test_both_doors_open_the_same_kind_of_case(client):
    """والبابان يفتحان المرجع نفسه لا مرجعين مختلفين.

    فالمفتّش يقرأ خروج الموظف من مكان واحد بصرف النظر عن بابه.
    """
    import inspect

    from app import exit_case
    from app.routers import employees as emp_router

    assert "open_case" in inspect.getsource(emp_router.execute_termination), (
        "باب الإدارة لا يمرّ بباب المراجع"
    )
    assert "open_case" in inspect.getsource(exit_case.open_from_request), (
        "باب الطلبات لا يمرّ به — تغيّر التصميم"
    )


def test_a_failure_to_open_the_case_is_not_swallowed(client):
    """وفشل فتح المرجع يُعلَن: القرار وقع والتسوية حُسبت.

    فإسقاط الإنهاء كلّه بسبب المرجع أسوأ، وابتلاع الفشل بصمت أسوأ
    منهما — فتُفتَح مهمة حرجة باسم السبب.
    """
    import inspect

    from app.routers import employees as emp_router

    src = inspect.getsource(emp_router.execute_termination)
    assert "exit_case_missing" in src, "فشل فتح المرجع يُبتلَع بصمت"
    assert "critical" in src


def test_the_timeline_tells_the_exit_story(client):
    """**والقصة في الشاشة التي تُقرأ**: من يفتح الملف يجد خروجه."""
    db = SessionLocal()
    try:
        emp = _fresh_employee(db)
        emp.civil_id = "299000000778"
        db.commit()
        eid = emp.id
    finally:
        db.close()

    _drive_termination(client, eid)
    body = client.get(f"/api/employees/{eid}/timeline",
                      headers=auth_headers(login(client, *HR))).json()
    exits = [x for x in body["timeline"] if x["category"] == "exit"]
    assert exits, "التايملاين لا يذكر الخروج"
    joined = " | ".join(x["text"] for x in exits)
    assert "حالة نهاية خدمة" in joined, joined
    assert "انتهت الخدمة" in joined, joined


def test_the_case_reference_is_visible_in_the_story(client):
    """ورقم المرجع في النصّ: من يقرأ السطر يصل إلى الحالة."""
    db = SessionLocal()
    try:
        emp = _fresh_employee(db)
        emp.civil_id = "299000000779"
        db.commit()
        eid = emp.id
    finally:
        db.close()

    out = _drive_termination(client, eid)
    db = SessionLocal()
    try:
        ref = db.get(models.EosCase, out["exit_case_id"]).reference_no
    finally:
        db.close()

    body = client.get(f"/api/employees/{eid}/timeline",
                      headers=auth_headers(login(client, *HR))).json()
    assert any(ref in x["text"] for x in body["timeline"]), ref


def test_the_accountant_still_sees_the_settlement_side(client):
    """والمحاسب يرى الخروج: التسوية والصرف شأنه.

    وتنقية التايملاين بالأدوار لا يجوز أن تُخفي عنه ما يخصّه.
    """
    db = SessionLocal()
    try:
        emp = _fresh_employee(db)
        emp.civil_id = "299000000780"
        db.commit()
        eid = emp.id
    finally:
        db.close()

    _drive_termination(client, eid)
    body = client.get(f"/api/employees/{eid}/timeline",
                      headers=auth_headers(login(client, *ACC))).json()
    assert any(x["category"] == "exit" for x in body["timeline"]), (
        "أُخفي الخروج عن المحاسب"
    )
