# -*- coding: utf-8 -*-
"""موظفٌ نمطُه ``gps`` يستطيع البصم (2026-09-24).

قيس على الإنتاج: الطريقُ الوحيد لتذكرة التسجيل كان ``validate-qr`` وهو يردّ من نمطُه gps بـ
«نمط حضورك لا يعتمد على رمز QR» — فخيارٌ يقدّمه النظام لا يعمل.
"""
import io
import secrets

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.security import hash_password
from tests.conftest import login, purge


def _world(mode="gps", lat=29.3, lng=47.9):
    db = SessionLocal()
    co = models.Company(name="شركة الحضور بالموقع")
    db.add(co)
    db.flush()
    br = models.Branch(company_id=co.id, name="فرع", code="GP1", latitude=lat, longitude=lng,
                       geofence_radius_m=100, qr_secret=secrets.token_hex(8),
                       kiosk_key=secrets.token_hex(8))
    db.add(br)
    db.flush()
    emp = models.Employee(company_id=co.id, name="بصّام", status="active", branch_id=br.id,
                          attendance_mode=mode)
    db.add(emp)
    db.flush()
    civ = "88" + str(secrets.randbelow(10**10)).zfill(10)
    u = models.User(civil_id=civ, password_hash=hash_password("Gps12345!x"), full_name="بصّام",
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
        purge(db, "attendance_records", [x.id for x in db.scalars(select(models.AttendanceRecord).where(
            models.AttendanceRecord.employee_id == ids["emp"])).all()])
        purge(db, "users", [ids["u"]])
        purge(db, "employees", [ids["emp"]])
        purge(db, "branches", [ids["br"]])
        purge(db, "companies", [ids["co"]])
        db.commit()
    finally:
        db.close()


def test_a_gps_only_employee_gets_a_ticket_inside_the_fence_and_checks_in(client):
    ids = _world()
    try:
        h = {"Authorization": f"Bearer {login(client, ids['civ'], 'Gps12345!x')}"}
        far = client.post("/api/attendance/validate-gps", json={"lat": 29.4, "lng": 47.9}, headers=h)
        assert far.status_code == 400 and "خارج نطاق" in far.text, far.text
        ok = client.post("/api/attendance/validate-gps", json={"lat": 29.3, "lng": 47.9}, headers=h)
        assert ok.status_code == 200, ok.text
        r = client.post("/api/attendance/check-in", headers=h,
                        data={"checkin_ticket": ok.json()["checkin_ticket"], "action": "in"},
                        files={"selfie": ("s.jpg", io.BytesIO(b"\xff\xd8" + b"x" * 400), "image/jpeg")})
        assert r.status_code == 200, r.text
    finally:
        _clean(ids)


def test_other_modes_do_not_use_the_gps_door(client):
    ids = _world(mode="qr")
    try:
        h = {"Authorization": f"Bearer {login(client, ids['civ'], 'Gps12345!x')}"}
        r = client.post("/api/attendance/validate-gps", json={"lat": 29.3, "lng": 47.9}, headers=h)
        assert r.status_code == 400, r.text
    finally:
        _clean(ids)
