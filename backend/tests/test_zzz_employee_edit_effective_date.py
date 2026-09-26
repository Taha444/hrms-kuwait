# -*- coding: utf-8 -*-
"""M05 #5 — التعديل المباشر لا يقبل تاريخ سريانٍ مستقبليًّا على حقلٍ حرج (يُطبَّق فورًا، فلا يكذب السجلّ)."""
from datetime import timedelta

from sqlalchemy import select

from app import models
from app.clock import today
from app.database import SessionLocal
from tests.conftest import auth_headers, login, plain_employee_clause

HR = ("100000000002", "hr12345")


def test_a_future_effective_date_on_a_critical_field_is_refused_and_nothing_changes(client):
    hr = auth_headers(login(client, *HR))
    db = SessionLocal()
    emp = db.scalar(select(models.Employee).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        plain_employee_clause(models)))
    eid, before = emp.id, emp.actual_job_title
    db.close()
    body = client.get(f"/api/employees/{eid}", headers=hr).json()
    body = {k: body[k] for k in ("name", "civil_id", "basic_salary", "hire_date") if k in body}
    future = (today() + timedelta(days=30)).isoformat()
    r = client.put(f"/api/employees/{eid}", headers=hr, params={"effective_date": future},
                   json={**body, "actual_job_title": "عنوانٌ مؤجَّل"})
    assert r.status_code == 400 and "يسري فورًا" in r.json()["detail"], (r.status_code, r.text[:120])
    db = SessionLocal()
    assert db.get(models.Employee, eid).actual_job_title == before, "الرفضُ ترك تغييرًا مُطبَّقًا"
    db.close()
    ok = client.put(f"/api/employees/{eid}", headers=hr, params={"effective_date": today().isoformat()},
                    json={**body, "actual_job_title": before or ""})
    assert ok.status_code == 200, ok.text[:120]
