# -*- coding: utf-8 -*-
"""M15 — معاملة تجديد الإقامة لا تُربط بإقامة لا تخصّ موظفها.

``create_renewal`` كان يحمّل ``permit_id`` المُرسَل بلا فحص نسبه: قيس أن مندوب الشركة 1
يفتح (201) معاملةً لموظفٍ من شركته مربوطةً بإقامة موظف في الشركة 2 — فتُحسب مدة التجديد
ونوعه من إقامة غيره، ويكتب الإنهاءُ لاحقًا على إقامةٍ خارج شركته.
"""
from __future__ import annotations

from datetime import date, timedelta

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, purge

PRO = ("100000000003", "deleg123")


def _seed():
    db = SessionLocal()
    try:
        a = models.Employee(company_id=1, name="RN-A", civil_id="777000501", status="active",
                            basic_salary=400, hire_date=date(2020, 1, 1))
        b = models.Employee(company_id=2, name="RN-B", civil_id="777000502", status="active",
                            basic_salary=400, hire_date=date(2020, 1, 1))
        a2 = models.Employee(company_id=1, name="RN-A2", civil_id="777000503", status="active",
                             basic_salary=400, hire_date=date(2020, 1, 1))
        db.add_all([a, b, a2])
        db.flush()
        soon = date.today() + timedelta(days=20)
        pa = models.Permit(company_id=1, employee_id=a.id, kind="residency", status="active",
                           number="RNA1", expiry_date=soon)
        pb = models.Permit(company_id=2, employee_id=b.id, kind="residency", status="active",
                           number="RNB1", expiry_date=soon)
        pa2 = models.Permit(company_id=1, employee_id=a2.id, kind="residency", status="active",
                            number="RNA2", expiry_date=soon)
        db.add_all([pa, pb, pa2])
        db.commit()
        return {"a": a.id, "b": b.id, "a2": a2.id, "pa": pa.id, "pb": pb.id, "pa2": pa2.id}
    finally:
        db.close()


def _cleanup(ids, rids):
    db = SessionLocal()
    try:
        for rid in rids:
            purge(db, "residency_renewals", [rid])
        purge(db, "permits", [ids["pa"], ids["pb"], ids["pa2"]])
        purge(db, "employees", [ids["a"], ids["b"], ids["a2"]])
        db.commit()
    finally:
        db.close()


def test_a_renewal_cannot_be_bound_to_another_companys_or_employees_permit(client):
    ids = _seed()
    rids = []
    try:
        pro = auth_headers(login(client, *PRO))
        other_company = client.post("/api/renewals", headers=pro, data={
            "employee_id": str(ids["a"]), "permit_id": str(ids["pb"])})
        other_employee = client.post("/api/renewals", headers=pro, data={
            "employee_id": str(ids["a"]), "permit_id": str(ids["pa2"])})
        for r in (other_company, other_employee):
            if r.status_code == 201:
                rids.append(r.json()["id"])
        assert other_company.status_code == 404, f"إقامة شركة أخرى قُبلت: {other_company.status_code}"
        assert other_employee.status_code == 404, f"إقامة موظف آخر قُبلت: {other_employee.status_code}"
    finally:
        _cleanup(ids, rids)


def test_the_employees_own_permit_still_renews(client):
    ids = _seed()
    rids = []
    try:
        pro = auth_headers(login(client, *PRO))
        r = client.post("/api/renewals", headers=pro, data={
            "employee_id": str(ids["a"]), "permit_id": str(ids["pa"])})
        if r.status_code == 201:
            rids.append(r.json()["id"])
        assert r.status_code == 201, r.text[:200]
    finally:
        _cleanup(ids, rids)
