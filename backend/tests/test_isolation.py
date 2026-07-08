# -*- coding: utf-8 -*-
"""اختبارات العزل بين الشركات (Multi-Tenancy) وفرض الصلاحيات على السيرفر."""
from tests.conftest import auth_headers, login


def test_manager_sees_only_own_company_employees(client):
    token1 = login(client, "100000000001", "manager123")  # شركة 1
    r = client.get("/api/employees", headers=auth_headers(token1))
    assert r.status_code == 200
    company_ids = {e["company_id"] for e in r.json()}
    assert company_ids <= {1}  # شركة المدير فقط
    assert len(r.json()) >= 4


def test_manager_cannot_access_other_company_employee(client):
    token2 = login(client, "200000000001", "manager123")  # شركة 2
    # موظف الشركة 1 (سارة في شركة 2 لها id مختلف؛ نجرّب أحد موظفي شركة 1)
    token1 = login(client, "100000000001", "manager123")
    emps1 = client.get("/api/employees", headers=auth_headers(token1)).json()
    target = emps1[0]["id"]
    r = client.get(f"/api/employees/{target}", headers=auth_headers(token2))
    assert r.status_code == 404  # العزل يُخفي وجوده


def test_super_admin_sees_all_companies(client):
    token = login(client, "000000000000", "admin123")
    r = client.get("/api/companies", headers=auth_headers(token))
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_employee_cannot_list_employees(client):
    token = login(client, "100000000101", "emp12345")
    r = client.get("/api/employees", headers=auth_headers(token))
    assert r.status_code == 403  # لا يملك صلاحية view_employee


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"civil_id": "100000000001", "password": "x"})
    assert r.status_code == 401


def test_owner_is_cross_company_and_sees_all(client):
    token = login(client, "111111111111", "owner123")
    me = client.get("/api/auth/me", headers=auth_headers(token)).json()
    assert me["is_cross_company"] is True
    companies = client.get("/api/companies", headers=auth_headers(token)).json()
    assert len(companies) >= 2  # المالك يرى كل الشركات


def test_owner_can_scope_to_any_company(client):
    token = login(client, "111111111111", "owner123")
    # المالك يصل لموظفي الشركة 2 (عبر تمرير company_id)
    emps = client.get("/api/employees", headers=auth_headers(token),
                      params={"company_id": 2}).json()
    assert all(e["company_id"] == 2 for e in emps)


def test_owner_dashboard_is_oversight_view(client):
    token = login(client, "111111111111", "owner123")
    d = client.get("/api/dashboard", headers=auth_headers(token)).json()
    assert d.get("owner_view") is True
    # كروت المتابعة: موظفون/فروع/إقامات/تراخيص/إشعارات + مؤشر الأداء
    for k in ("employees", "branches", "residencies", "licenses", "notifications", "performance"):
        assert k in d, k
    perf = d["performance"]
    assert {"attendance_rate", "valid_licenses_pct", "expired_licenses_pct"} <= set(perf)


def test_owner_is_read_only_no_operational_actions(client):
    token = login(client, "111111111111", "owner123")
    h = auth_headers(token)
    # المالك دور رقابي: لا يعتمد طلبات ولا ينشئ موظفين ولا يشغّل رواتب
    assert client.post("/api/employees", headers=h,
                       json={"name": "x", "basic_salary": 100}).status_code == 403
    assert client.post("/api/payroll/run", headers=h, params={"period": "2026-01"}).status_code == 403


def test_owner_has_readonly_audit_and_payroll_visibility(client):
    """FIX-010: المالك دور حوكمة — يطّلع على التدقيق والرواتب دون تنفيذ."""
    token = login(client, "111111111111", "owner123")
    h = auth_headers(token)
    assert client.get("/api/audit", headers=h, params={"company_id": 1}).status_code == 200
    assert client.get("/api/payroll/runs", headers=h, params={"company_id": 1}).status_code == 200
    # لا يزال ممنوعًا من تشغيل الرواتب فعليًا
    assert client.post("/api/payroll/run", headers=h, params={"period": "2026-01"}).status_code == 403


def test_dashboard_scopes_to_selected_company(client):
    token = login(client, "000000000000", "admin123")
    h = auth_headers(token)
    c1 = client.get("/api/dashboard", headers=h, params={"company_id": 1}).json()
    c2 = client.get("/api/dashboard", headers=h, params={"company_id": 2}).json()
    all_ = client.get("/api/dashboard", headers=h).json()  # كل الشركات
    assert c1["employees"] == 6 and c2["employees"] == 6  # لكل شركة 6 موظفين
    assert all_["employees"] == 12  # المجموع عند اختيار "كل الشركات"
    assert c1["branches"] == 2 and c2["branches"] == 2


def test_manager_not_cross_company(client):
    token = login(client, "100000000001", "manager123")
    me = client.get("/api/auth/me", headers=auth_headers(token)).json()
    assert me["is_cross_company"] is False


def test_hierarchy_blocks_creating_higher_role(client):
    token = login(client, "100000000001", "manager123")  # company_manager
    r = client.post("/api/users", headers=auth_headers(token),
                    json={"civil_id": "999888777666", "full_name": "x", "role": "company_owner"})
    assert r.status_code == 403  # لا يُنشئ دورًا أعلى من مستواه
