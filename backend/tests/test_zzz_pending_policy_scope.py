# -*- coding: utf-8 -*-
"""قائمة «بلا سياسة حضور» بنطاق الفرع.

``/employees/attendance-policy/pending`` كانت تُقيَّد بالشركة وحدها، و
``view_attendance`` يملكها مسؤوُل الفرع — فيرى أسماء موظفي الفروع الأخرى
وأرقامهم، وهي أسماٌء لا تعرضها له قائمُة الموظفين نفسها.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.deps import resolve_scope
from tests.conftest import auth_headers, login

SUP1 = ("100000000005", "sup12345")


def _with_foreign_pending(fn):
    db = SessionLocal()
    try:
        sup = db.scalar(select(models.User).where(models.User.civil_id == SUP1[0]))
        mine = resolve_scope(sup, db).branch_ids or set()
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            models.Employee.branch_id.isnot(None),
            models.Employee.branch_id.notin_(mine)))
        old = (emp.attendance_mode, emp.attendance_exempt)
        emp.attendance_mode, emp.attendance_exempt = "none", False
        db.commit()
        try:
            return fn(emp.id, mine)
        finally:
            emp.attendance_mode, emp.attendance_exempt = old
            db.commit()
    finally:
        db.close()


def test_a_branch_supervisor_sees_only_his_branches(client):
    def check(emp_id, mine):
        r = client.get("/api/employees/attendance-policy/pending",
                       headers=auth_headers(login(client, *SUP1)))
        assert r.status_code == 200, r.text[:150]
        ids = {row["id"] for row in r.json()}
        assert emp_id not in ids
        assert all(row["branch_id"] in mine for row in r.json())
    _with_foreign_pending(check)


def test_hr_still_sees_the_other_branch(client):
    def check(emp_id, _mine):
        r = client.get("/api/employees/attendance-policy/pending",
                       headers=auth_headers(login(client, "100000000002", "hr12345")))
        assert r.status_code == 200, r.text[:150]
        assert emp_id in {row["id"] for row in r.json()}
    _with_foreign_pending(check)
