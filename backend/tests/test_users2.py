# -*- coding: utf-8 -*-
"""اختبارات حالات المستخدم (تعطيل/إيقاف) وانتحال الهوية (Impersonation)."""
from tests.conftest import auth_headers, login


def test_user_status_suspend_blocks_login(client):
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    uid = client.post("/api/users", headers=ah, json={
        "civil_id": "888000111000", "full_name": "مستخدم اختبار", "role": "hr",
        "company_id": 1, "password": "temp123456"}).json()["id"]

    # إيقاف → يُمنع الدخول
    client.post(f"/api/users/{uid}/status", headers=ah, params={"status": "suspended"})
    r = client.post("/api/auth/login", json={"civil_id": "888000111000", "password": "temp123456"})
    assert r.status_code == 403

    # إعادة تفعيل → يدخل
    client.post(f"/api/users/{uid}/status", headers=ah, params={"status": "active"})
    r2 = client.post("/api/auth/login", json={"civil_id": "888000111000", "password": "temp123456"})
    assert r2.status_code == 200


def test_impersonation_super_admin_only(client):
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    # هوية موظف
    users = client.get("/api/users", headers=ah, params={"company_id": 1}).json()
    emp_uid = next(u["id"] for u in users if u["civil_id"] == "100000000101")

    r = client.post(f"/api/users/{emp_uid}/impersonate", headers=ah, params={"reason": "دعم"})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    me = client.get("/api/auth/me", headers=auth_headers(tok)).json()
    assert me["civil_id"] == "100000000101"  # نتصفّح كالموظف فعليًا

    # المدير لا يستطيع الانتحال
    mgr = login(client, "100000000001", "manager123")
    assert client.post(f"/api/users/{emp_uid}/impersonate", headers=auth_headers(mgr)).status_code == 403


def test_cannot_impersonate_super_admin(client):
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    admins = client.get("/api/users", headers=ah).json()
    sa_uid = next(u["id"] for u in admins if u["civil_id"] == "000000000000")
    assert client.post(f"/api/users/{sa_uid}/impersonate", headers=ah).status_code == 400
