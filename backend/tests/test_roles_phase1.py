# -*- coding: utf-8 -*-
"""اختبارات مراجعة الأدوار (Phase 1): الصلاحيات، النماذج، اللوحات، EOS، البحث."""
from tests.conftest import auth_headers, login


def _emp_id(client, token):
    return client.get("/api/employees", headers=auth_headers(token)).json()[0]["id"]


def test_hr_cannot_manage_government_permits(client):
    hr = login(client, "100000000002", "hr12345")
    eid = _emp_id(client, hr)
    r = client.post(f"/api/employees/{eid}/permits", headers=auth_headers(hr),
                    params={"kind": "residency", "number": "X"})
    assert r.status_code == 403  # الإقامات من مهام المندوب لا الـ HR


def test_pro_can_manage_permits_and_licenses(client):
    pro = login(client, "100000000003", "deleg123")
    eid = _emp_id(client, login(client, "100000000001", "manager123"))
    r = client.post(f"/api/employees/{eid}/permits", headers=auth_headers(pro),
                    params={"kind": "residency", "number": "RES-NEW"})
    assert r.status_code == 200


def test_only_super_admin_creates_templates(client):
    mgr = login(client, "100000000001", "manager123")
    body = {"name": "صيغة مدير", "body_html": "<p>{{employee_name}}</p>"}
    assert client.post("/api/templates", headers=auth_headers(mgr), json=body).status_code == 403
    admin = login(client, "000000000000", "admin123")
    assert client.post("/api/templates", headers=auth_headers(admin), json=body).status_code == 201


def test_employee_dashboard_is_personal_only(client):
    emp = login(client, "100000000101", "emp12345")
    d = client.get("/api/dashboard", headers=auth_headers(emp)).json()
    assert d.get("personal_only") is True
    assert "employees" not in d and "branches" not in d  # لا إحصائيات شركة


def test_pro_dashboard_has_government_metrics(client):
    pro = login(client, "100000000003", "deleg123")
    d = client.get("/api/dashboard", headers=auth_headers(pro)).json()
    assert "expiring_licenses" in d and "expiring_residencies" in d


def test_hr_dashboard_employee_focused(client):
    hr = login(client, "100000000002", "hr12345")
    d = client.get("/api/dashboard", headers=auth_headers(hr)).json()
    assert "employees" in d
    assert "branches" not in d  # HR لا يرى عدد الفروع


def test_eos_leave_balance_auto(client):
    mgr = login(client, "100000000001", "manager123")
    eid = _emp_id(client, mgr)
    r = client.post("/api/eos/leave-balance", headers=auth_headers(mgr),
                    params={"employee_id": eid, "consumed_days": 10})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["accrued_days"] > 0
    assert b["remaining_days"] == round(b["accrued_days"] - 10, 2)


def test_search_by_residency_number(client):
    mgr = login(client, "100000000001", "manager123")
    # رقم إقامة من البذور للشركة 1 (RES-1000)
    r = client.get("/api/employees", headers=auth_headers(mgr), params={"q": "RES-1000"})
    assert r.status_code == 200
    assert len(r.json()) >= 1  # وجد الموظف عبر رقم الإقامة
