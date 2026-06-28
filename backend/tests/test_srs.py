# -*- coding: utf-8 -*-
"""اختبارات دفعة الـ SRS: الإدارات، البحث الشامل، مركز العمليات، الدور الإداري المرن."""
from tests.conftest import auth_headers, login


def test_departments_create_and_filter(client):
    mgr = login(client, "100000000001", "manager123")
    h = auth_headers(mgr)
    bid = client.get("/api/branches", headers=h).json()[0]["id"]
    r = client.post("/api/departments", headers=h, params={"name": "المبيعات", "branch_id": bid})
    assert r.status_code == 201, r.text
    dept_id = r.json()["id"]
    depts = client.get("/api/departments", headers=h).json()
    assert any(d["id"] == dept_id for d in depts)
    # موظف في الإدارة ثم الفلترة بها
    emp = client.post("/api/employees", headers=h, json={
        "civil_id": "199900088001", "name": "موظف مبيعات", "basic_salary": 400,
        "branch_id": bid, "department_id": dept_id}).json()
    rows = client.get("/api/employees", headers=h, params={"department_id": dept_id}).json()
    assert any(e["id"] == emp["id"] for e in rows)


def test_global_search(client):
    mgr = login(client, "100000000001", "manager123")
    r = client.get("/api/search", headers=auth_headers(mgr), params={"q": "محمد"})
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 1
    assert r.json()["results"].get("employees")
    # الإدارة العليا تبحث في الشركات
    admin = login(client, "000000000000", "admin123")
    rc = client.get("/api/search", headers=auth_headers(admin), params={"q": "100200"}).json()
    assert rc["results"].get("companies")


def test_operations_center(client):
    mgr = login(client, "100000000001", "manager123")
    r = client.get("/api/operations", headers=auth_headers(mgr))
    assert r.status_code == 200, r.text
    d = r.json()
    assert "compliance" in d and "permits" in d and "licenses" in d
    assert set(d["compliance"]) == {"expired", "critical", "warning"}


def test_operations_center_denied_for_hr(client):
    # مركز العمليات يعرض معاملات حكومية/تراخيص → ممنوع على HR (دورة حياة الموظف فقط)
    hr = login(client, "100000000002", "hr12345")
    r = client.get("/api/operations", headers=auth_headers(hr))
    assert r.status_code == 403


def test_admin_employee_role_starts_with_no_permissions(client):
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    r = client.post("/api/users", headers=ah, json={
        "civil_id": "777000111000", "full_name": "موظف إداري", "role": "admin_employee",
        "company_id": 1, "password": "temp123456"})
    assert r.status_code == 201, r.text
    uid = r.json()["id"]

    # أول دخول: تغيير كلمة المرور
    tok = login(client, "777000111000", "temp123456")
    client.post("/api/auth/change-password", headers=auth_headers(tok),
                json={"old_password": "temp123456", "new_password": "NewPass123"})
    tok = login(client, "777000111000", "NewPass123")
    h = auth_headers(tok)
    # بلا صلاحيات افتراضية → ممنوع
    assert client.get("/api/employees", headers=h).status_code == 403

    # المدير يمنحه قراءة الموظفين عبر المصفوفة
    client.post(f"/api/users/{uid}/matrix", headers=ah, json={"grants": {"employees": ["read"]}})
    tok = login(client, "777000111000", "NewPass123")
    assert client.get("/api/employees", headers=auth_headers(tok)).status_code == 200
