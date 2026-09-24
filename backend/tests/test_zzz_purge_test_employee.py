# -*- coding: utf-8 -*-
"""مسح موظفٍ تجريبيّ (SWEEP_) وما حوله — ولا غيره (2026-09-24)."""
import secrets

from sqlalchemy import func, select

from app import models
from app.database import SessionLocal
from app.security import hash_password
from tests.conftest import login, purge


def _mk(name):
    db = SessionLocal()
    co = models.Company(name="شركة المسح التجريبي")
    db.add(co)
    db.flush()
    br = models.Branch(company_id=co.id, name="ف", code="PT1", qr_secret=secrets.token_hex(8))
    db.add(br)
    db.flush()
    emp = models.Employee(company_id=co.id, name=name, status="active", branch_id=br.id,
                          attendance_mode="none", annual_leave_balance=30)
    db.add(emp)
    db.flush()
    civ = "87" + str(secrets.randbelow(10**10)).zfill(10)
    u = models.User(civil_id=civ, password_hash=hash_password("Pt12345!xy"), full_name=name,
                    role="employee", company_id=co.id, employee_id=emp.id,
                    must_change_password=False)
    db.add(u)
    db.commit()
    ids = dict(co=co.id, br=br.id, emp=emp.id, u=u.id, civ=civ)
    db.close()
    return ids


def _clean(ids):
    db = SessionLocal()
    try:
        purge(db, "users", [ids["u"]])
        purge(db, "employees", [ids["emp"]])
        purge(db, "branches", [ids["br"]])
        purge(db, "companies", [ids["co"]])
        db.commit()
    finally:
        db.close()


def test_a_sweep_employee_is_purged_with_its_requests_and_tasks_but_the_account_and_audit_stay(client):
    ids = _mk("SWEEP_ موظف للمسح")
    admin = {"Authorization": f"Bearer {login(client, '000000000000', 'admin123')}"}
    try:
        h = {"Authorization": f"Bearer {login(client, ids['civ'], 'Pt12345!xy')}"}
        r = client.post("/api/requests", headers=h, json={
            "request_type_code": "REQCERTSAL", "payload_json": {"purpose": "x", "language": "ar"}})
        assert r.status_code == 201, r.text
        rid = r.json()["id"]
        db = SessionLocal()
        try:
            assert db.get(models.Request, rid) is not None
            others_before = db.scalar(select(func.count()).select_from(models.Employee).where(
                models.Employee.id != ids["emp"]))
        finally:
            db.close()

        # بلا تأكيدٍ صريح لا يمسح (الإنتاج يشترطه؛ التطوير لا) — وفي كل حال يمسح التجريبي وحده.
        res = client.post("/api/admin/purge-test-employee", params={
            "employee_id": ids["emp"], "confirm": "PURGE-TEST-EMPLOYEE"}, headers=admin)
        assert res.status_code == 200, res.text
        db = SessionLocal()
        try:
            assert db.get(models.Employee, ids["emp"]) is None, "بقي الموظف"
            assert db.get(models.Request, rid) is None, "بقي طلبُه"
            acct = db.get(models.User, ids["u"])
            assert acct is not None and acct.is_active is False and acct.employee_id is None, \
                "الحساب حُذف أو بقي فاعلًا"
            assert db.scalar(select(models.AuditLog).where(
                models.AuditLog.action == "purge_test_employee",
                models.AuditLog.entity_id == ids["emp"])), "لا أثر تدقيق"
            assert db.scalar(select(func.count()).select_from(models.Employee).where(
                models.Employee.id != ids["emp"])) == others_before, "مُسح موظفٌ آخر"
        finally:
            db.close()
    finally:
        _clean(ids)


def test_a_real_employee_is_never_purged(client):
    ids = _mk("موظف حقيقي")
    admin = {"Authorization": f"Bearer {login(client, '000000000000', 'admin123')}"}
    try:
        r = client.post("/api/admin/purge-test-employee", params={
            "employee_id": ids["emp"], "confirm": "PURGE-TEST-EMPLOYEE"}, headers=admin)
        assert r.status_code == 403, r.text
        db = SessionLocal()
        try:
            assert db.get(models.Employee, ids["emp"]) is not None
        finally:
            db.close()
        hr = {"Authorization": f"Bearer {login(client, '100000000002', 'hr12345')}"}
        assert client.post("/api/admin/purge-test-employee", params={
            "employee_id": ids["emp"]}, headers=hr).status_code == 403
    finally:
        _clean(ids)
