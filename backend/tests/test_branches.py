# -*- coding: utf-8 -*-
"""اختبارات هيكلة الفروع: الهيكل، إحصائيات الفرع، فلترة الموظفين والتقارير بالفرع."""
from tests.conftest import auth_headers, login


def test_company_structure(client):
    mgr = login(client, "100000000001", "manager123")
    r = client.get("/api/org/structure", headers=auth_headers(mgr))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["company"]["name"]
    assert len(d["branches"]) == 2  # فرعان للشركة 1
    assert sum(b["employee_count"] for b in d["branches"]) <= d["total_employees"]
    # مسؤول الفرع يظهر
    assert any(b["supervisors"] for b in d["branches"])


def test_branch_stats(client):
    mgr = login(client, "100000000001", "manager123")
    branches = client.get("/api/branches", headers=auth_headers(mgr)).json()
    bid = branches[0]["id"]
    r = client.get(f"/api/branches/{bid}/stats", headers=auth_headers(mgr))
    assert r.status_code == 200, r.text
    s = r.json()
    assert set(s) >= {"employees", "present_today", "on_leave", "expiring_permits"}


def test_employees_filtered_by_branch(client):
    mgr = login(client, "100000000001", "manager123")
    h = auth_headers(mgr)
    branches = client.get("/api/branches", headers=h).json()
    bid = branches[0]["id"]
    rows = client.get("/api/employees", headers=h, params={"branch_id": bid}).json()
    assert all(e["branch_id"] == bid for e in rows)
    # أقل من إجمالي موظفي الشركة (التوزيع على فرعين)
    all_rows = client.get("/api/employees", headers=h).json()
    assert len(rows) <= len(all_rows)


def test_report_export_by_branch(client):
    mgr = login(client, "100000000001", "manager123")
    h = auth_headers(mgr)
    bid = client.get("/api/branches", headers=h).json()[0]["id"]
    r = client.get("/api/reports/employees", headers=h, params={"fmt": "xlsx", "branch_id": bid})
    assert r.status_code == 200
    assert r.content[:2] == b"PK"


def test_structure_requires_company_for_super_admin_all(client):
    admin = login(client, "000000000000", "admin123")
    # بدون اختيار شركة (كل الشركات) → يطلب تحديد شركة
    r = client.get("/api/org/structure", headers=auth_headers(admin))
    assert r.status_code == 400
    # مع تحديد شركة → يعمل
    r2 = client.get("/api/org/structure", headers=auth_headers(admin), params={"company_id": 1})
    assert r2.status_code == 200
