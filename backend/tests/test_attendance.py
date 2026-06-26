# -*- coding: utf-8 -*-
"""اختبار تدفّق الحضور: مسح QR → تذكرة → سيلفي → تسجيل، مع منع إعادة الاستخدام والـ Geofence."""
import io

from app import models, qr_token
from app.database import SessionLocal
from tests.conftest import auth_headers, login

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 400  # صورة سيلفي وهمية صالحة الحجم


def _emp_branch():
    db = SessionLocal()
    emp = db.query(models.Employee).filter_by(civil_id="100000000101").first()
    branch = db.get(models.Branch, emp.branch_id)
    out = (emp.id, branch.id, branch.kiosk_key, branch.latitude, branch.longitude)
    db.close()
    return out


def _selfie_files():
    return {"selfie": ("s.jpg", io.BytesIO(JPEG), "image/jpeg")}


def test_full_qr_then_selfie_checkin(client):
    _, branch_id, _, lat, lng = _emp_branch()
    tok = login(client, "100000000101", "emp12345")
    h = auth_headers(tok)

    qr = qr_token.make_qr_token(branch_id)[0]
    r = client.post("/api/attendance/validate-qr", headers=h,
                    json={"qr_token": qr, "lat": lat, "lng": lng})
    assert r.status_code == 200, r.text
    ticket = r.json()["checkin_ticket"]

    # نفس الرمز لا يصلح مرتين (anti-replay)
    r2 = client.post("/api/attendance/validate-qr", headers=h,
                     json={"qr_token": qr, "lat": lat, "lng": lng})
    assert r2.status_code == 409

    # تسجيل حضور بالتذكرة + السيلفي
    r3 = client.post("/api/attendance/check-in", headers=h,
                     data={"checkin_ticket": ticket, "action": "in"}, files=_selfie_files())
    assert r3.status_code == 200, r3.text
    assert r3.json()["action"] == "in"

    # التذكرة لا تُستخدم مرتين
    r4 = client.post("/api/attendance/check-in", headers=h,
                     data={"checkin_ticket": ticket, "action": "in"}, files=_selfie_files())
    assert r4.status_code == 409


def test_checkin_rejected_without_selfie(client):
    _, branch_id, _, lat, lng = _emp_branch()
    tok = login(client, "100000000101", "emp12345")
    h = auth_headers(tok)
    qr = qr_token.make_qr_token(branch_id)[0]
    ticket = client.post("/api/attendance/validate-qr", headers=h,
                         json={"qr_token": qr, "lat": lat, "lng": lng}).json()["checkin_ticket"]
    # بدون ملف سيلفي → 422 (حقل مطلوب)
    r = client.post("/api/attendance/check-in", headers=h,
                    data={"checkin_ticket": ticket, "action": "in"})
    assert r.status_code == 422


def test_invalid_qr_token_rejected(client):
    tok = login(client, "100000000101", "emp12345")
    r = client.post("/api/attendance/validate-qr", headers=auth_headers(tok),
                    json={"qr_token": "not-a-valid-token", "lat": 29.33, "lng": 48.02})
    assert r.status_code == 400


def test_outside_geofence_rejected(client):
    _, branch_id, _, _, _ = _emp_branch()
    tok = login(client, "100000000101", "emp12345")
    qr = qr_token.make_qr_token(branch_id)[0]
    # إحداثيات بعيدة جدًا (خارج النطاق)
    r = client.post("/api/attendance/validate-qr", headers=auth_headers(tok),
                    json={"qr_token": qr, "lat": 30.0, "lng": 50.0})
    assert r.status_code == 400


def test_kiosk_endpoint_key_required(client):
    _, branch_id, kiosk_key, _, _ = _emp_branch()
    # مفتاح خاطئ → 403
    bad = client.get(f"/api/kiosk/{branch_id}/qr", params={"key": "wrong"})
    assert bad.status_code == 403
    # مفتاح صحيح → رمز حيّ
    good = client.get(f"/api/kiosk/{branch_id}/qr", params={"key": kiosk_key})
    assert good.status_code == 200, good.text
    body = good.json()
    assert body["token"] and body["branch_name"] and body["refresh_in_seconds"] > 0


def test_attendance_review_for_manager(client):
    mgr = login(client, "100000000001", "manager123")
    r = client.get("/api/attendance/review", headers=auth_headers(mgr))
    assert r.status_code == 200, r.text
    body = r.json()
    assert "days" in body and "employees" in body
    # كل الموظفين المعروضين مفعّل لهم الحضور (mode != none)
    assert all(e["attendance_mode"] != "none" for e in body["employees"])
    if body["employees"]:
        e0 = body["employees"][0]
        assert set(e0["summary"]) >= {"present", "late", "absent", "leave"}
        assert len(e0["cells"]) == len(body["days"])


def test_attendance_review_denied_for_employee(client):
    emp = login(client, "100000000101", "emp12345")
    r = client.get("/api/attendance/review", headers=auth_headers(emp))
    assert r.status_code == 403  # الموظف لا يملك view_attendance


def test_kiosk_token_validates_end_to_end(client):
    """رمز صادر فعليًا من شاشة الفرع (kiosk) يُقبَل في تدفّق الحضور."""
    _, branch_id, kiosk_key, lat, lng = _emp_branch()
    kiosk = client.get(f"/api/kiosk/{branch_id}/qr", params={"key": kiosk_key})
    assert kiosk.status_code == 200
    token = kiosk.json()["token"]

    tok = login(client, "100000000101", "emp12345")
    h = auth_headers(tok)
    r = client.post("/api/attendance/validate-qr", headers=h,
                    json={"qr_token": token, "lat": lat, "lng": lng})
    assert r.status_code == 200, r.text
    ticket = r.json()["checkin_ticket"]
    r2 = client.post("/api/attendance/check-in", headers=h,
                     data={"checkin_ticket": ticket, "action": "in"}, files=_selfie_files())
    assert r2.status_code in (200, 409)  # 409 لو سبق تسجيل حضور مفتوح في اختبار آخر


def test_kiosk_rotate_invalidates_old_key(client):
    _, branch_id, old_key, _, _ = _emp_branch()
    mgr = login(client, "100000000001", "manager123")
    r = client.post(f"/api/branches/{branch_id}/kiosk-key/rotate", headers=auth_headers(mgr))
    assert r.status_code == 200, r.text
    new_key = r.json()["kiosk_key"]
    assert new_key != old_key
    # المفتاح القديم بطل فورًا
    assert client.get(f"/api/kiosk/{branch_id}/qr", params={"key": old_key}).status_code == 403
    assert client.get(f"/api/kiosk/{branch_id}/qr", params={"key": new_key}).status_code == 200
