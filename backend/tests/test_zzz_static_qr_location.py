# -*- coding: utf-8 -*-
"""الرمز الثابت يُلزِم بالموقع حيث للفرع إحداثيات — قرار المالك (2026-09-18).

لا رمَز متغيًّرا في النظام: كلُّ QR ثابت. وموظُف نمط ``qr`` لم يكن ملزًَما
بإرسال إحداثيات — فمن صوّر رمَز الشاشة مرًّة يبصم من بيته. والفرع بلا
إحداثيات يبقى كما كان (إلزامه يوقف حضوره كلَّه)، ويُعلَّم «يلزم إعداد».
"""
from __future__ import annotations

from sqlalchemy import select

from app import models, qr_token
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")


def _setup(mode: str, coords: bool):
    """ينصب الموظف على نمط ونمط إحداثيات الفرع؛ يُعيد (token, lat, lng, restore)."""
    db = SessionLocal()
    try:
        user = db.scalar(select(models.User).where(models.User.civil_id == EMP[0]))
        emp = db.get(models.Employee, user.employee_id)
        br = db.get(models.Branch, emp.branch_id)
        old = (emp.attendance_mode, br.latitude, br.longitude, br.kiosk_key)
        emp.attendance_mode = mode
        if not br.kiosk_key:
            br.kiosk_key = "guard-key"
        if coords and br.latitude is None:
            br.latitude, br.longitude = 29.3759, 47.9774
        if not coords:
            br.latitude = br.longitude = None
        db.commit()
        token = qr_token.make_static_qr_token(br.id, br.kiosk_key)
        lat, lng = br.latitude, br.longitude
        emp_id, br_id = emp.id, br.id
    finally:
        db.close()

    def restore():
        db = SessionLocal()
        try:
            e, b = db.get(models.Employee, emp_id), db.get(models.Branch, br_id)
            e.attendance_mode, b.latitude, b.longitude, b.kiosk_key = old
            db.commit()
        finally:
            db.close()
    return token, lat, lng, restore


def _scan(client, token, **pos):
    return client.post("/api/attendance/validate-qr",
                       headers=auth_headers(login(client, *EMP)),
                       json={"qr_token": token, **pos})


def test_static_qr_without_location_is_refused_where_the_branch_has_coordinates(client):
    token, _, _, restore = _setup("qr", coords=True)
    try:
        r = _scan(client, token)
        assert r.status_code == 400, (r.status_code, r.text[:200])
        assert "الموقع" in r.text
    finally:
        restore()


def test_static_qr_with_location_inside_the_radius_still_works(client):
    token, lat, lng, restore = _setup("qr", coords=True)
    try:
        r = _scan(client, token, lat=lat, lng=lng)
        assert r.status_code == 200, r.text[:200]
    finally:
        restore()


def test_a_branch_without_coordinates_keeps_working(client):
    token, _, _, restore = _setup("qr", coords=False)
    try:
        r = _scan(client, token)
        assert r.status_code == 200, r.text[:200]
    finally:
        restore()
