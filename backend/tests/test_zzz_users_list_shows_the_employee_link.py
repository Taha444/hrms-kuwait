# -*- coding: utf-8 -*-
"""M02 SW-006/028 — قائمة المستخدمين تُرجع ``employee_id``: بدونه لا يُتحقَّق من ربط الحساب الإداري بموظفه من الشاشة."""
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login


def test_the_users_list_carries_each_accounts_employee_link(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    rows = client.get("/api/users", headers=admin).json()
    assert rows and all("employee_id" in r for r in rows), "الحقل غائب من الاستجابة"
    db = SessionLocal()
    try:
        expected = {u.id: u.employee_id for u in db.scalars(select(models.User)).all()}
    finally:
        db.close()
    assert all(r["employee_id"] == expected[r["id"]] for r in rows)
    assert any(r["employee_id"] for r in rows), "لا حسابَ مربوط في القياس"


def test_a_disabled_account_cannot_be_impersonated_and_no_start_is_recorded(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    db = SessionLocal()
    target = db.scalar(select(models.User).where(
        models.User.civil_id == "100000000101"))
    uid, was = target.id, target.is_active
    before = db.query(models.AuditLog).filter(
        models.AuditLog.action == "impersonate_start", models.AuditLog.entity_id == uid).count()
    target.is_active = False
    db.commit()
    db.close()
    try:
        r = client.post(f"/api/users/{uid}/impersonate", headers=admin)
        assert r.status_code == 409, (r.status_code, r.text[:100])
        db = SessionLocal()
        after = db.query(models.AuditLog).filter(
            models.AuditLog.action == "impersonate_start", models.AuditLog.entity_id == uid).count()
        db.close()
        assert after == before, "قُيّد بدءُ انتحالٍ لم يقع"
    finally:
        db = SessionLocal()
        db.get(models.User, uid).is_active = was
        db.commit()
        db.close()
