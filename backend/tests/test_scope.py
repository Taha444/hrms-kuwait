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


def _mk_user(client, ah, civil_id, **extra):
    """ينشئ مستخدمًا بكلمة مرور معروفة ويتجاوز إجبار التغيير، ويعيد توكنه."""
    body = {"civil_id": civil_id, "full_name": "اختبار النطاق", "role": "admin_employee",
            "company_id": 1, "password": "temp123456", **extra}
    uid = client.post("/api/users", headers=ah, json=body).json()["id"]
    client.post(f"/api/users/{uid}/matrix", headers=ah, json={"grants": {"employees": ["read"]}})
    tok = login(client, civil_id, "temp123456")
    client.post("/api/auth/change-password", headers=auth_headers(tok),
                json={"old_password": "temp123456", "new_password": "NewPass123"})
    return uid, login(client, civil_id, "NewPass123")


def test_scope_self_sees_only_own_record(client):
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    emp_id = client.post("/api/employees", headers=ah, json={
        "name": "موظف الخدمة الذاتية", "civil_id": "199900011122", "basic_salary": 400,
        "company_id": 1, "branch_id": 1}).json()["id"]
    uid, tok = _mk_user(client, ah, "666000222000", employee_id=emp_id)
    client.post(f"/api/users/{uid}/scope", headers=ah, params={"level": "self"})
    rows = client.get("/api/employees", headers=auth_headers(tok)).json()
    assert [e["id"] for e in rows] == [emp_id]  # سجله فقط لا غير


def test_scope_company_sees_all_branches(client):
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    uid, tok = _mk_user(client, ah, "666000333000")
    client.post(f"/api/users/{uid}/scope", headers=ah, params={"level": "company"})
    rows = client.get("/api/employees", headers=auth_headers(tok)).json()
    assert {e["branch_id"] for e in rows} >= {1, 2}  # يرى كل فروع شركته


def test_scope_multi_sees_listed_branches_only(client):
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    uid, tok = _mk_user(client, ah, "666000444000")
    r = client.post(f"/api/users/{uid}/scope", headers=ah, params={"level": "multi", "branch_ids": [2]})
    assert r.status_code == 200 and r.json()["scope_level"] == "multi"
    rows = client.get("/api/employees", headers=auth_headers(tok)).json()
    assert rows and all(e["branch_id"] == 2 for e in rows)  # الفروع المُسندة فقط
