# -*- coding: utf-8 -*-
"""M04 — السياج الجغرافي لا يُجتاز بإحداثياتٍ غير معرَّفة.

``_check_geofence`` يقارن ``dist > radius``؛ و``NaN > r`` تُقيَّم ``False`` — فمن يرسل
``{"lat": NaN, "lng": NaN}`` يحصل على تذكرة بصمة صالحة (200) من أيّ مكان (قيس)، و``Infinity``
يسقط ``ValueError`` (500). والحضور أساس الرواتب. فالمدى والمتناهي يُفرَضان عند المدخل
(الحضور والفرع معًا) ودفاعًا ثانيًا عند القياس.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HQ = (29.3759, 47.9774)


@pytest.fixture
def gps_employee():
    db = SessionLocal()
    u = db.scalar(select(models.User).where(models.User.civil_id == EMP[0]))
    emp = db.get(models.Employee, u.employee_id)
    br = (db.get(models.Branch, emp.branch_id) if emp.branch_id else
          db.scalar(select(models.Branch).where(models.Branch.company_id == emp.company_id)))
    saved = dict(mode=emp.attendance_mode, branch=emp.branch_id, lat=br.latitude,
                 lng=br.longitude, radius=br.geofence_radius_m, bid=br.id, eid=emp.id)
    emp.attendance_mode, emp.branch_id = "gps", br.id
    br.latitude, br.longitude, br.geofence_radius_m = HQ[0], HQ[1], 100
    db.commit()
    db.close()
    yield saved
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, saved["eid"])
        br = db.get(models.Branch, saved["bid"])
        emp.attendance_mode, emp.branch_id = saved["mode"], saved["branch"]
        br.latitude, br.longitude, br.geofence_radius_m = saved["lat"], saved["lng"], saved["radius"]
        db.commit()
    finally:
        db.close()


def _gps(client, raw):
    hdr = auth_headers(login(client, *EMP))
    return client.post("/api/attendance/validate-gps",
                       headers={**hdr, "Content-Type": "application/json"}, content=raw)


def test_a_real_position_inside_the_fence_still_gets_a_ticket(client, gps_employee):
    r = _gps(client, '{"lat": 29.3759, "lng": 47.9774}')
    assert r.status_code == 200 and r.json()["checkin_ticket"], r.text[:120]


def test_a_position_outside_the_fence_is_refused(client, gps_employee):
    assert _gps(client, '{"lat": 29.4759, "lng": 47.9774}').status_code == 400


@pytest.mark.parametrize("raw", [
    '{"lat": NaN, "lng": NaN}',
    '{"lat": Infinity, "lng": 47.9}',
    '{"lat": 47.9, "lng": -Infinity}',
    '{"lat": 1000, "lng": 47.9}',
    '{"lat": 29.3, "lng": 999}',
])
def test_undefined_or_out_of_range_coordinates_never_get_a_ticket(client, gps_employee, raw):
    r = _gps(client, raw)
    assert r.status_code == 422, f"{raw} → {r.status_code} {r.text[:100]}"


def test_a_branch_cannot_be_saved_with_undefined_coordinates(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    r = client.post("/api/branches", headers={**admin, "Content-Type": "application/json"},
                    content='{"company_id": 1, "name": "x", "latitude": NaN, "longitude": 1}')
    assert r.status_code == 422, r.status_code
