# -*- coding: utf-8 -*-
"""اختبارات نطاق بيانات الفرع: مسؤول الفرع والمستخدم المقيّد يريان فرعهم فقط."""
from tests.conftest import auth_headers, login


def test_branch_supervisor_sees_only_own_branch(client):
    # مسؤول فرع 1 (100000000005) يشرف على الفرع الأول فقط
    sup = login(client, "100000000005", "sup12345")
    rows = client.get("/api/employees", headers=auth_headers(sup)).json()
    assert len(rows) >= 1
    assert all(e["branch_id"] == 1 for e in rows)  # فرعه فقط


def test_supervisor_cannot_open_other_branch_employee(client):
    # موظف في الفرع 2
    mgr = login(client, "100000000001", "manager123")
    b2_emp = next(e for e in client.get("/api/employees", headers=auth_headers(mgr),
                                        params={"branch_id": 2}).json())
    sup = login(client, "100000000005", "sup12345")
    r = client.get(f"/api/employees/{b2_emp['id']}", headers=auth_headers(sup))
    assert r.status_code == 404  # خارج نطاق فرعه


def test_admin_can_set_and_clear_user_scope(client):
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    uid = client.post("/api/users", headers=ah, json={
        "civil_id": "666000111000", "full_name": "موظف مقيّد", "role": "admin_employee",
        "company_id": 1, "password": "temp123456"}).json()["id"]
    # منح قراءة الموظفين + تقييده بالفرع 2
    client.post(f"/api/users/{uid}/matrix", headers=ah, json={"grants": {"employees": ["read"]}})
    r = client.post(f"/api/users/{uid}/scope", headers=ah, params={"branch_id": 2})
    assert r.status_code == 200 and r.json()["scope_branch_id"] == 2

    tok = login(client, "666000111000", "temp123456")
    client.post("/api/auth/change-password", headers=auth_headers(tok),
                json={"old_password": "temp123456", "new_password": "NewPass123"})
    tok = login(client, "666000111000", "NewPass123")
    rows = client.get("/api/employees", headers=auth_headers(tok)).json()
    assert all(e["branch_id"] == 2 for e in rows)  # الفرع 2 فقط
