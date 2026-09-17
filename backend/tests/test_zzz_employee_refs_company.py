# -*- coding: utf-8 -*-
"""معرّفاتُ الكيانات المُسنَدة لموظفٍ من شركته — لا من أي شركة.

**القياس**: موظفُ موارد الشركة الأولى عدّل موظفًا فيها بمديرٍ مباشرٍ وفرعٍ
وترخيصٍ ووردّيةٍ وقسمٍ **من الشركة الثانية** — الخمسةُ ردّت 200. وفحصُ الفرع
القائم يعمل لمن نطاقُه فروعٌ محددة وحده.

والأثر: طلباتُ الموظف تُوجَّه إلى مديرٍ في شركةٍ أخرى، وتُعَدّ عمالتُه على
ترخيص غيرِ شركته، ويُحسب غيابُه بوردّيةٍ ليست لشركته.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")

_FIELDS = {
    "direct_manager_id": models.Employee,
    "branch_id": models.Branch,
    "department_id": models.Department,
    "shift_id": models.Shift,
    "license_id": models.License,
}


def _target():
    db = SessionLocal()
    try:
        e = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            models.Employee.civil_id.notin_(("100000000001", "100000000002"))))
        snap = {f: getattr(e, f) for f in _FIELDS}
        return e.id, {"name": e.name, "civil_id": e.civil_id}, snap
    finally:
        db.close()


def _restore(eid, snap):
    db = SessionLocal()
    try:
        e = db.get(models.Employee, eid)
        for f, v in snap.items():
            setattr(e, f, v)
        db.commit()
    finally:
        db.close()


@pytest.mark.parametrize("field", list(_FIELDS))
def test_a_reference_from_another_company_is_refused(client, field):
    eid, body, snap = _target()
    db = SessionLocal()
    try:
        other = db.scalar(select(_FIELDS[field]).where(_FIELDS[field].company_id == 2))
        if other is None:
            pytest.skip(f"لا {field} في الشركة الثانية")
        oid = other.id
    finally:
        db.close()
    try:
        r = client.put(f"/api/employees/{eid}", json={**body, field: oid},
                       headers=auth_headers(login(client, *HR)))
        assert r.status_code == 400, (field, r.status_code, r.text[:200])
        db = SessionLocal()
        try:
            assert getattr(db.get(models.Employee, eid), field) == snap[field], field
        finally:
            db.close()
    finally:
        _restore(eid, snap)


def test_a_reference_from_the_same_company_is_accepted(client):
    eid, body, snap = _target()
    db = SessionLocal()
    try:
        mgr = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.id != eid))
        mid = mgr.id
    finally:
        db.close()
    try:
        r = client.put(f"/api/employees/{eid}", json={**body, "direct_manager_id": mid},
                       headers=auth_headers(login(client, *HR)))
        assert r.status_code == 200, (r.status_code, r.text[:200])
    finally:
        _restore(eid, snap)


def test_an_employee_is_not_their_own_manager(client):
    eid, body, snap = _target()
    try:
        r = client.put(f"/api/employees/{eid}", json={**body, "direct_manager_id": eid},
                       headers=auth_headers(login(client, *HR)))
        assert r.status_code == 400, (r.status_code, r.text[:200])
    finally:
        _restore(eid, snap)


def test_creation_is_checked_too(client):
    db = SessionLocal()
    try:
        b2 = db.scalar(select(models.Branch).where(models.Branch.company_id == 2))
        bid = b2.id
    finally:
        db.close()
    r = client.post("/api/employees", headers=auth_headers(login(client, *HR)), json={
        "name": "قياس مرجع", "civil_id": "299000000913", "basic_salary": 400,
        "hire_date": "2026-01-01", "branch_id": bid})
    assert r.status_code == 400, (r.status_code, r.text[:200])
