# -*- coding: utf-8 -*-
"""M14 — باب «حالات نهاية الخدمة» (``POST /eos/cases``) يحرس ما يحرسه بابا الخروج الآخران.

ثلاثة أبواب تفتح المرجع نفسه (الطلبات، ملف الموظف، /eos/cases). كان الأخير بلا حارس
التسلسل الذي في ``employees.prepare_termination`` (قرار المالك #38)، وبلا فحص حالة
الموظف، وبلا فحص تاريخ الإنهاء مقابل التعيين — فالمقيس: HR يفتح حالةً على مدير الشركة،
وحالةً لمن انتهت خدمته، ولتاريخٍ قبل تعيينه (ولا يُرفض إلا عند الحساب لاحقًا).
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, plain_employee_clause, purge

HR = ("100000000002", "hr12345")
MGR_CIVIL = "100000000001"


def _open(client, hr, emp_id, when=None, reason="termination"):
    d = (when or (date.today() + timedelta(days=30))).isoformat()
    r = client.post("/api/eos/cases", headers=hr, params={
        "employee_id": emp_id, "termination_date": d, "reason": reason})
    if r.status_code == 201:
        _purge_case(r.json()["id"])
    return r


def _purge_case(cid):
    db = SessionLocal()
    try:
        purge(db, "eos_cases", [cid])
        db.commit()
    finally:
        db.close()


def test_hr_cannot_open_an_eos_case_on_the_company_manager(client):
    db = SessionLocal()
    try:
        mgr_emp = db.scalar(select(models.User.employee_id).where(
            models.User.civil_id == MGR_CIVIL))
    finally:
        db.close()
    r = _open(client, auth_headers(login(client, *HR)), mgr_emp)
    assert r.status_code == 403, f"HR فتح إنهاء خدمة مدير الشركة: {r.status_code} {r.text[:150]}"


def test_no_case_is_opened_for_an_employee_whose_service_already_ended(client):
    db = SessionLocal()
    try:
        e = models.Employee(company_id=1, name="M14 منتهي", civil_id="777000333",
                            status="terminated", basic_salary=400, hire_date=date(2020, 1, 1))
        db.add(e)
        db.commit()
        eid = e.id
    finally:
        db.close()
    try:
        r = _open(client, auth_headers(login(client, *HR)), eid)
        assert r.status_code == 409, f"فُتحت حالة لموظف منتهي الخدمة: {r.status_code}"
    finally:
        db = SessionLocal()
        try:
            purge(db, "employees", [eid])
            db.commit()
        finally:
            db.close()


def test_the_termination_date_cannot_precede_the_hire_date_at_opening(client):
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            models.Employee.hire_date.isnot(None), plain_employee_clause(models)).limit(1))
        eid, hire = emp.id, emp.hire_date
    finally:
        db.close()
    r = _open(client, auth_headers(login(client, *HR)), eid, when=hire - timedelta(days=1))
    assert r.status_code == 400, f"قُبل تاريخ إنهاء قبل التعيين: {r.status_code} {r.text[:120]}"
