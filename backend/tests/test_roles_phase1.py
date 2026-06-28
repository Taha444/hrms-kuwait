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
    # لوحة PRO: معاملات حكومية فقط — بلا إجازات/خصومات/تقارير HR
    assert {"expired_residencies", "residencies_expiring_30", "expiring_work_permits",
            "expiring_licenses", "open_transactions", "gov_tasks", "notifications"} <= set(d)
    assert "on_leave" not in d and "contracts" not in d


def test_hr_dashboard_employee_focused(client):
    hr = login(client, "100000000002", "hr12345")
    d = client.get("/api/dashboard", headers=auth_headers(hr)).json()
    assert "employees" in d
    assert "branches" not in d  # HR لا يرى عدد الفروع


def test_eos_leave_balance_auto(client):
    hr = login(client, "100000000002", "hr12345")  # EOS من اختصاص HR
    eid = _emp_id(client, hr)
    r = client.post("/api/eos/leave-balance", headers=auth_headers(hr),
                    params={"employee_id": eid, "consumed_days": 10})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["accrued_days"] > 0
    assert b["remaining_days"] == round(b["accrued_days"] - 10, 2)


def test_employee_self_service_only(client):
    # الموظف: خدمة ذاتية — ملفه/إنذاراته فقط، بلا موظفين آخرين ولا لوحة شركة
    emp = login(client, "100000000101", "emp12345")
    h = auth_headers(emp)
    me = client.get("/api/me/profile", headers=h)
    assert me.status_code == 200
    d = me.json()
    assert {"employee", "documents", "warnings", "leaves"} <= set(d)
    # لا يصل لقائمة الموظفين إطلاقًا (بلا view_employee)
    assert client.get("/api/employees", headers=h).status_code == 403
    # لوحة شخصية فقط — لا إحصائيات شركة/فروع
    dash = client.get("/api/dashboard", headers=h).json()
    assert dash.get("personal_only") is True
    assert "branches" not in dash and "employees" not in dash
    # ممنوع: عمليات/رواتب/تدقيق
    assert client.get("/api/operations", headers=h).status_code == 403
    assert client.get("/api/audit", headers=h).status_code == 403


def test_branch_supervisor_scoped_to_own_branch(client):
    # مسؤول الفرع: فرعه فقط — لا فروع أخرى، لا رواتب/مستخدمين، لوحة الفرع
    sup = login(client, "100000000005", "sup12345")
    h = auth_headers(sup)
    d = client.get("/api/dashboard", headers=h).json()
    assert "branch_employees" in d
    assert "branches" not in d and "expiring_permits" not in d
    emps = client.get("/api/employees", headers=h).json()
    assert 0 < len(emps) < 6  # فرعه فقط، أقل من إجمالي الشركة (6)
    assert client.post("/api/payroll/run", headers=h, params={"period": "2026-01"}).status_code == 403
    # تقرير الموظفين مقيّد بفرعه (لا يتعدّى عدد موظفي فرعه)
    rep = client.get("/api/reports/employees", headers=h, params={"fmt": "csv"})
    assert rep.status_code == 200
    assert rep.content.count(b"\n") - 1 <= len(emps)  # صفوف البيانات = موظفو فرعه


def test_hr_employee_lifecycle_only(client):
    # HR: موظفون فقط — لا حكومة/رواتب/عمليات/تقارير
    hr = login(client, "100000000002", "hr12345")
    h = auth_headers(hr)
    assert client.get("/api/operations", headers=h).status_code == 403
    assert client.post("/api/payroll/run", headers=h, params={"period": "2026-01"}).status_code == 403
    eid = _emp_id(client, hr)
    # إقامة (حكومية) ممنوعة على HR
    assert client.post(f"/api/employees/{eid}/permits", headers=h,
                       params={"kind": "residency", "number": "Z"}).status_code == 403


def test_hr_dashboard_has_warnings_and_contracts(client):
    hr = login(client, "100000000002", "hr12345")
    d = client.get("/api/dashboard", headers=auth_headers(hr)).json()
    assert {"employees", "on_leave", "contracts", "warnings", "pending_requests"} <= set(d)
    assert "expiring_permits" not in d and "expiring_licenses" not in d and "branches" not in d


def test_manager_is_operational_only(client):
    # المدير: تشغيل يومي فقط — لا رواتب/EOS/عمليات حكومية/تدقيق
    mgr = login(client, "100000000001", "manager123")
    h = auth_headers(mgr)
    assert client.post("/api/payroll/run", headers=h, params={"period": "2026-01"}).status_code == 403
    assert client.get("/api/operations", headers=h).status_code == 403
    assert client.get("/api/audit", headers=h).status_code == 403
    eid = _emp_id(client, mgr)
    assert client.post("/api/eos/leave-balance", headers=h,
                       params={"employee_id": eid, "consumed_days": 5}).status_code == 403


def test_manager_dashboard_is_operational(client):
    # لوحة المدير: موظفون/فروع/طلبات/إجازات/تنبيهات/عقود — بلا مؤشرات حكومية
    mgr = login(client, "100000000001", "manager123")
    d = client.get("/api/dashboard", headers=auth_headers(mgr)).json()
    assert {"employees", "branches", "pending_requests", "on_leave",
            "notifications", "contracts"} <= set(d)
    assert "expiring_permits" not in d and "expiring_licenses" not in d


def test_accountant_runs_payroll_not_employees_edit(client):
    # المحاسب: الرواتب فقط — لا تعديل موظفين
    acc = login(client, "100000000007", "account123")
    h = auth_headers(acc)
    assert client.post("/api/payroll/run", headers=h, params={"period": "2026-02"}).status_code == 200
    assert client.post("/api/employees", headers=h,
                       json={"name": "x", "basic_salary": 100}).status_code == 403


def test_search_by_residency_number(client):
    mgr = login(client, "100000000001", "manager123")
    # رقم إقامة من البذور للشركة 1 (RES-1000)
    r = client.get("/api/employees", headers=auth_headers(mgr), params={"q": "RES-1000"})
    assert r.status_code == 200
    assert len(r.json()) >= 1  # وجد الموظف عبر رقم الإقامة
