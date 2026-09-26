# -*- coding: utf-8 -*-
"""M11 #5 — مراجعة الحضور ورقم الإقفال يعدّان من يعدّه المسيّر واللوحة: من لم تنتهِ خدمته (لا «active» وحدها)."""
from sqlalchemy import select

from app import attendance_close, models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, plain_employee_clause

HR = ("100000000002", "hr12345")
PERIOD = "2026-08"


def test_an_employee_on_vacation_stays_in_the_review_and_in_the_close_count(client):
    hr = auth_headers(login(client, *HR))
    db = SessionLocal()
    emp = db.scalar(select(models.Employee).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        models.Employee.attendance_mode != "none", plain_employee_clause(models)))
    eid, old_status = emp.id, emp.status
    try:
        emp.attendance_exempt = False
        db.commit()
        in_review = lambda: {r["employee_id"] for r in client.get(
            "/api/attendance/review", headers=hr, params={"month": PERIOD, "company_id": 1}
        ).json()["employees"]}
        active_count = attendance_close.unrecorded_day_count(db, 1, PERIOD)
        assert eid in in_review()
        emp.status = "vacation"
        db.commit()
        assert eid in in_review(), "من في إجازة اختفى من مراجعة الحضور"
        assert attendance_close.unrecorded_day_count(db, 1, PERIOD) == active_count, (
            "رقم الإقفال أسقط موظفًا في إجازة يُدفع راتبُه")
        emp.status = "terminated"
        db.commit()
        assert eid not in in_review()
    finally:
        emp.status = old_status
        db.commit()
        db.close()
