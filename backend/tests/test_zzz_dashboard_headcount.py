# -*- coding: utf-8 -*-
"""عدد الموظفين في اللوحة — قرار المالك (2026-09-18).

الإجمالُي = من لم تنتهِ خدمته (نشط + في إجازة + موقوف)، وتحته «منهم X في
إجازة». كان يعدُّ «النشط» وحده، فموظٌف يخرج في إجازته السنوية يختفي من
عدد الشركة — والمسيّر (قرار 2026-09-17) يدفع له.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
SUP1 = ("100000000005", "sup12345")


def _dash(client, who):
    r = client.get("/api/dashboard", headers=auth_headers(login(client, *who)))
    assert r.status_code == 200, r.text[:150]
    return r.json()


def _set_status(emp_id, status):
    db = SessionLocal()
    try:
        db.get(models.Employee, emp_id).status = status
        db.commit()
    finally:
        db.close()


def _an_active_employee_in_branch_of(civil_id):
    db = SessionLocal()
    try:
        from app.deps import resolve_scope
        u = db.scalar(select(models.User).where(models.User.civil_id == civil_id))
        bids = resolve_scope(u, db).branch_ids or set()
        return db.scalar(select(models.Employee.id).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            models.Employee.branch_id.in_(bids)))
    finally:
        db.close()


def test_an_employee_on_leave_stays_in_the_headcount_and_is_shown_apart(client):
    emp = _an_active_employee_in_branch_of(SUP1[0])
    before = _dash(client, HR)
    sup_before = _dash(client, SUP1)
    _set_status(emp, "vacation")
    try:
        after = _dash(client, HR)
        assert after["employees"] == before["employees"], "في إجازة خرج من العدد"
        assert after["employees_on_vacation"] == before.get("employees_on_vacation", 0) + 1
        sup_after = _dash(client, SUP1)
        assert sup_after["branch_employees"] == sup_before["branch_employees"]
        assert sup_after["branch_employees_on_vacation"] >= 1
    finally:
        _set_status(emp, "active")
