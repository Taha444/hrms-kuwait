# -*- coding: utf-8 -*-
"""M12 #7 — حساب نهاية الخدمة يعرض ما يعرفه النظام عن الإجازات المستهلَكة ويحذّر إن نقص المُدخل عنه."""
from datetime import date

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, plain_employee_clause, purge

HR = ("100000000002", "hr12345")


def _employee_with_leave(days):
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            models.Employee.hire_date.isnot(None), models.Employee.basic_salary > 0,
            plain_employee_clause(models)))
        lv = models.Leave(company_id=1, employee_id=emp.id, leave_type="annual",
                          start_date=date(2026, 1, 4), end_date=date(2026, 1, 4),
                          days=days, status="approved")
        db.add(lv)
        db.commit()
        return emp.id, lv.id
    finally:
        db.close()


def _drop(lid):
    db = SessionLocal()
    try:
        purge(db, "leaves", [lid])
        db.commit()
    finally:
        db.close()


def test_typed_usage_below_the_system_record_is_flagged(client):
    hr = auth_headers(login(client, *HR))
    eid, lid = _employee_with_leave(12)
    try:
        end = date.today().isoformat()
        r = client.post("/api/eos/for-employee", headers=hr,
                        json={"employee_id": eid, "end_date": end, "reason": "termination",
                              "used_leave_days": 0})
        assert r.status_code == 200, r.text
        leave = r.json()["leave"]
        assert leave["system_used_days"] >= 12
        assert leave["used_days_mismatch"] is True and leave["used_days_note"]
        ok = client.post("/api/eos/for-employee", headers=hr,
                         json={"employee_id": eid, "end_date": end, "reason": "termination",
                               "used_leave_days": int(leave["system_used_days"])})
        assert ok.json()["leave"]["used_days_mismatch"] is False
    finally:
        _drop(lid)
