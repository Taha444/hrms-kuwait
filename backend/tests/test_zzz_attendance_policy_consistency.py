# -*- coding: utf-8 -*-
"""M11 #1 — سياسة الحضور المضبوطة لا تناقض نفسها ولا تستحيل: لا «يبصم ومعفًى»، ولا gps بلا إحداثيات فرع."""
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, plain_employee_clause

HR = ("100000000002", "hr12345")


def _policy(client, hr, eid, **params):
    return client.post(f"/api/employees/{eid}/attendance-policy", headers=hr, params=params)


def test_the_policy_is_consistent_and_executable(client):
    hr = auth_headers(login(client, *HR))
    db = SessionLocal()
    emp = db.scalar(select(models.Employee).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        plain_employee_clause(models)))
    eid, branch_id = emp.id, emp.branch_id
    saved = (emp.attendance_mode, emp.attendance_exempt, emp.attendance_exempt_reason)
    branch = db.get(models.Branch, branch_id) if branch_id else None
    lat = (branch.latitude, branch.longitude) if branch else None
    db.close()
    try:
        r = _policy(client, hr, eid, mode="qr", exempt="true", exempt_reason="س")
        assert r.status_code == 400 and "لا يجتمع" in r.json()["detail"], r.text[:120]
        assert _policy(client, hr, eid, mode="qr").status_code == 200
        if branch is not None:
            db = SessionLocal()
            b = db.get(models.Branch, branch_id)
            b.latitude = b.longitude = None
            db.commit()
            db.close()
            for path, params in (("attendance-policy", {"mode": "gps"}), ("attendance-mode", {"mode": "both"})):
                r = client.post(f"/api/employees/{eid}/{path}", headers=hr, params=params)
                assert r.status_code == 409 and "إحداثيات" in r.json()["detail"], (path, r.text[:120])
    finally:
        db = SessionLocal()
        e = db.get(models.Employee, eid)
        e.attendance_mode, e.attendance_exempt, e.attendance_exempt_reason = saved
        if branch_id and lat:
            b = db.get(models.Branch, branch_id)
            b.latitude, b.longitude = lat
        db.commit()
        db.close()
