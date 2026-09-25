# -*- coding: utf-8 -*-
"""M14 #4 / SW-033 — الحاسبة ترفض راتبًا صفريًا وتاريخ تعيين ناقصًا كما ترفضهما مسودة الإنهاء."""
from datetime import date

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, plain_employee_clause

HR = ("100000000002", "hr12345")


def _post(client, hr, eid):
    return client.post("/api/eos/for-employee", headers=hr, json={
        "employee_id": eid, "end_date": date.today().isoformat(), "reason": "termination"})


def test_zero_salary_and_missing_hire_date_are_refused_in_arabic(client):
    hr = auth_headers(login(client, *HR))
    db = SessionLocal()
    emp = db.scalar(select(models.Employee).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        models.Employee.hire_date.isnot(None), models.Employee.basic_salary > 0,
        plain_employee_clause(models)))
    eid, salary, hire = emp.id, emp.basic_salary, emp.hire_date
    try:
        emp.basic_salary = 0
        db.commit()
        r = _post(client, hr, eid)
        assert r.status_code == 400 and "الراتب" in r.json()["detail"], r.text
        emp.basic_salary, emp.hire_date = salary, None
        db.commit()
        r = _post(client, hr, eid)
        assert r.status_code == 400 and "تاريخ التعيين" in r.json()["detail"], r.text
    finally:
        emp.basic_salary, emp.hire_date = salary, hire
        db.commit()
        db.close()
