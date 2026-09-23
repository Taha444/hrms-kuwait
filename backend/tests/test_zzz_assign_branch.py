# -*- coding: utf-8 -*-
"""النقل المباشر للإدارة العليا — قرار المالك (2026-09-23).

الإداريون (مدير/HR/محاسب/مندوب) بلا فرع في الإنتاج، ولا جهةَ تعتمد نقلًا لمن لا فرع
له. فـ``super_admin`` ينقل أيَّ موظف مباشرةً — ويبقى غيره على ``REQTRF``، والـ``PUT``
لا يمسّ الفرع لأحد.
"""
from __future__ import annotations

import secrets

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import login, purge


@pytest.fixture
def world():
    db = SessionLocal()
    co = models.Company(name="شركة النقل المباشر")
    other = models.Company(name="شركة أخرى للنقل")
    db.add_all([co, other])
    db.flush()

    def br(c, code, **kw):
        b = models.Branch(company_id=c.id, name=code, code=code, qr_secret=secrets.token_hex(8), **kw)
        db.add(b)
        return b
    hq = br(co, "HQ", is_headquarters=True)
    arch = br(co, "OLD", status="archived")
    foreign = br(other, "FX")
    db.flush()
    emp = models.Employee(company_id=co.id, name="مدير بلا فرع", status="active")
    db.add(emp)
    db.commit()
    ids = dict(co=co.id, other=other.id, hq=hq.id, arch=arch.id, foreign=foreign.id, emp=emp.id)
    db.close()
    yield ids
    db = SessionLocal()
    try:
        purge(db, "employee_field_changes", [x.id for x in db.scalars(select(
            models.EmployeeFieldChange).where(models.EmployeeFieldChange.employee_id == ids["emp"])).all()])
        purge(db, "employees", [ids["emp"]])
        purge(db, "branches", [x.id for x in db.scalars(select(models.Branch).where(
            models.Branch.company_id.in_([ids["co"], ids["other"]]))).all()])
        purge(db, "companies", [ids["co"], ids["other"]])
        db.commit()
    finally:
        db.close()


def _h(client, civil, pw):
    return {"Authorization": f"Bearer {login(client, civil, pw)}"}


def test_super_admin_moves_a_branchless_employee_to_the_hq_with_a_trail(client, world):
    h = _h(client, "000000000000", "admin123")
    r = client.post(f"/api/employees/{world['emp']}/assign-branch",
                    params={"branch_id": world["hq"], "reason": "وضع الإداريين على المقر"}, headers=h)
    assert r.status_code == 200 and r.json()["changed"] is True, r.text
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, world["emp"])
        assert emp.branch_id == world["hq"] and emp.actual_branch_id == world["hq"]
        ch = db.scalar(select(models.EmployeeFieldChange).where(
            models.EmployeeFieldChange.employee_id == emp.id,
            models.EmployeeFieldChange.field_name == "branch_id"))
        assert ch and ch.old_value is None and ch.new_value == str(world["hq"]) and ch.reason
        assert db.scalar(select(models.AuditLog).where(
            models.AuditLog.action == "assign_branch", models.AuditLog.entity_id == emp.id))
    finally:
        db.close()
    # وتكراره لا يفعل شيئًا ولا يكتب سجلًّا ثانيًا.
    r = client.post(f"/api/employees/{world['emp']}/assign-branch",
                    params={"branch_id": world["hq"], "reason": "مرة ثانية"}, headers=h)
    assert r.json()["changed"] is False


def test_it_refuses_the_wrong_targets_and_the_wrong_caller(client, world):
    admin = _h(client, "000000000000", "admin123")
    url = f"/api/employees/{world['emp']}/assign-branch"
    assert client.post(url, params={"branch_id": world["foreign"], "reason": "x"},
                       headers=admin).status_code == 404, "نُقل لفرع شركة أخرى"
    assert client.post(url, params={"branch_id": world["arch"], "reason": "x"},
                       headers=admin).status_code == 409, "نُقل لفرع مؤرشف"
    assert client.post(url, params={"branch_id": world["hq"], "reason": " "},
                       headers=admin).status_code == 400, "بلا سبب"
    hr = _h(client, "100000000002", "hr12345")
    assert client.post(url, params={"branch_id": world["hq"], "reason": "x"},
                       headers=hr).status_code == 403, "HR نقل مباشرةً"
    db = SessionLocal()
    try:
        assert db.get(models.Employee, world["emp"]).branch_id is None
    finally:
        db.close()
