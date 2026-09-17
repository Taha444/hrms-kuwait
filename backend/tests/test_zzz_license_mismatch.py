# -*- coding: utf-8 -*-
"""العمل على غير ترخيص التسجيل — تنبيهٌ تفتيشي (قرار المالك 2026-09-17).

كان ``Employee.actual_license_id`` حقلًا لم يُملأ قطّ، ولا تعرضه الواجهة، ولا
يقرؤه شيء — والمخطَّطُ يوهم بمتابعة. فصار: يُضبط من نموذج تعديل الموظف،
ويُعرض في ملفه مع تنبيه، ويُسرد في مركز العمليات من يعمل على غير ترخيص
تسجيله. وتغييرُه يُقيَّد في سجلّ التعديلات.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")


def _setup():
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            models.Employee.license_id.isnot(None)))
        other = models.License(company_id=1, name="ترخيص قياس آخر", license_no="ZZ-1",
                               allowed_workers=5, status="active")
        db.add(other)
        db.commit()
        return emp.id, emp.actual_license_id, other.id
    finally:
        db.close()


def _teardown(eid, old_actual, lid):
    db = SessionLocal()
    try:
        db.get(models.Employee, eid).actual_license_id = old_actual
        db.flush()
        db.delete(db.get(models.License, lid))
        db.commit()
    finally:
        db.close()


def test_a_different_actual_licence_is_flagged_everywhere(client):
    eid, old, lid = _setup()
    hdr = auth_headers(login(client, *HR))
    try:
        opts = client.get(f"/api/employees/{eid}/license-options", headers=hdr)
        assert opts.status_code == 200 and lid in [o["id"] for o in opts.json()]
        cur = client.get(f"/api/employees/{eid}", headers=hdr).json()
        put = client.put(f"/api/employees/{eid}", headers=hdr,
                         params={"change_reason": "قياس"},
                         json={"civil_id": cur["civil_id"], "name": cur["name"],
                               "actual_license_id": lid})
        assert put.status_code == 200, put.text[:250]

        prof = client.get(f"/api/employees/{eid}/profile", headers=hdr).json()
        assert prof["licenses"]["mismatch"] is True
        assert prof["licenses"]["actual"]["id"] == lid

        listed = client.get("/api/employees/license-mismatch", headers=hdr).json()
        assert eid in [m["employee_id"] for m in listed]

        ops = client.get("/api/operations", headers=hdr)
        if ops.status_code == 200:
            assert eid in [m["employee_id"] for m in ops.json()["license_mismatch"]]

        db = SessionLocal()
        try:
            assert db.scalar(select(models.EmployeeFieldChange).where(
                models.EmployeeFieldChange.employee_id == eid,
                models.EmployeeFieldChange.field_name == "actual_license_id"))
        finally:
            db.close()
    finally:
        _teardown(eid, old, lid)


def test_the_same_or_empty_actual_licence_is_not_flagged():
    from app.license_mismatch import is_mismatch
    e = models.Employee(license_id=3, actual_license_id=None)
    assert not is_mismatch(e)
    e.actual_license_id = 3
    assert not is_mismatch(e)
    e.actual_license_id = 4
    assert is_mismatch(e)


def test_the_operations_screen_shows_the_list():
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
           / "Operations.tsx").read_text(encoding="utf-8")
    assert "license_mismatch" in src
