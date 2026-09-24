# -*- coding: utf-8 -*-
"""إبطال إقامة/إذن أُدخل بالخطأ — للإدارة العليا وحدها، لا حذف (2026-09-24).

قيس أثناء المسح الشامل: فحصٌ أنشأ إقامة تجريبية حقيقية على موظف حقيقي بلا نقطة رجوع.
"""
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import login, purge

MGR = ("100000000001", "manager123")
ADMIN = ("000000000000", "admin123")


def _h(client, cred):
    return {"Authorization": f"Bearer {login(client, *cred)}"}


def test_super_admin_voids_a_wrongly_added_permit_and_it_vanishes_from_the_dashboards(client):
    admin = _h(client, ADMIN)
    mgr_emp = client.get("/api/auth/me", headers=_h(client, MGR)).json()["employee_id"]
    add = client.post(f"/api/employees/{mgr_emp}/permits",
                      params={"kind": "residency", "number": "TEST_VOID_ME"}, headers=admin)
    assert add.status_code == 200, add.text
    pid = add.json()["id"]
    try:
        before = client.get("/api/pro/permits", params={"company_id": 1}, headers=admin).json()
        assert any(p["id"] == pid and p["status"] == "active" for p in before)

        assert client.post(f"/api/employees/{mgr_emp}/permits/{pid}/void",
                           params={"reason": " "}, headers=admin).status_code == 400
        ok = client.post(f"/api/employees/{mgr_emp}/permits/{pid}/void",
                         params={"reason": "أُدخلت بالخطأ أثناء المسح"}, headers=admin)
        assert ok.status_code == 200 and ok.json()["status"] == "voided", ok.text

        after = client.get("/api/pro/permits", params={"company_id": 1}, headers=admin).json()
        assert not any(p["id"] == pid for p in after), "لا يزال ظاهرًا في القائمة النشطة"
        db = SessionLocal()
        try:
            row = db.get(models.Permit, pid)
            assert row is not None and row.status == "voided", "حُذف الصفّ أو لم يُبطَل"
            assert db.scalar(select(models.AuditLog).where(
                models.AuditLog.action == "void_permit", models.AuditLog.entity_id == mgr_emp))
        finally:
            db.close()

        again = client.post(f"/api/employees/{mgr_emp}/permits/{pid}/void",
                            params={"reason": "x"}, headers=admin)
        assert again.status_code == 409, again.text
    finally:
        db = SessionLocal()
        try:
            purge(db, "permits", [pid])
            db.commit()
        finally:
            db.close()


def test_only_the_top_admin_may_void(client):
    admin = _h(client, ADMIN)
    mgr = _h(client, MGR)
    mgr_emp = client.get("/api/auth/me", headers=mgr).json()["employee_id"]
    add = client.post(f"/api/employees/{mgr_emp}/permits",
                      params={"kind": "residency", "number": "TEST_VOID_2"}, headers=admin)
    pid = add.json()["id"]
    try:
        r = client.post(f"/api/employees/{mgr_emp}/permits/{pid}/void",
                        params={"reason": "x"}, headers=mgr)
        assert r.status_code == 403, r.text
    finally:
        db = SessionLocal()
        try:
            purge(db, "permits", [pid])
            db.commit()
        finally:
            db.close()
