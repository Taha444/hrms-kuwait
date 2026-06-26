# -*- coding: utf-8 -*-
"""اختبارات pytest للميزات والإصلاحات الجديدة."""


def _first_company(client):
    return client.get("/api/companies").get_json()[0]["id"]


def _emp_in(client, cid):
    emps = client.get(f"/api/employees?company_id={cid}").get_json()
    return emps[0]["id"]


# ---- إصلاح تسريب العزل عند النقل ----
def test_transfer_moves_child_records(admin):
    comps = admin.get("/api/companies").get_json()
    c1, c2 = comps[0]["id"], comps[1]["id"]
    eid = _emp_in(admin, c1)
    # أضف إقامة وخصم للموظف
    admin.post("/api/permits", json={"employee_id": eid, "kind": "residency", "number": "T-1",
                                     "expiry_date": "2030-01-01"})
    admin.post("/api/deductions", json={"employee_id": eid, "amount": 10, "reason": "اختبار"})
    r = admin.post(f"/api/employees/{eid}/transfer", json={"to_company_id": c2})
    assert r.status_code == 200
    # بعد النقل، الموظف وكل سجلاته في الشركة 2
    detail = admin.get(f"/api/employees/{eid}").get_json()
    assert detail["company_id"] == c2
    for p in detail["permits"]:
        assert p["company_id"] == c2
    for d in detail["deductions"]:
        assert d["company_id"] == c2


# ---- حذف موظف ----
def test_delete_employee(admin):
    c1 = _first_company(admin)
    r = admin.post("/api/employees", json={"company_id": c1, "name": "موظف مؤقت", "basic_salary": 300,
                                           "hire_date": "2022-01-01"})
    eid = r.get_json()["id"]
    assert admin.delete(f"/api/employees/{eid}").status_code == 200
    assert admin.get(f"/api/employees/{eid}").status_code == 404


# ---- الأقسام ----
def test_departments_crud(admin):
    c1 = _first_company(admin)
    r = admin.post("/api/departments", json={"company_id": c1, "name": "قسم الهندسة"})
    did = r.get_json()["id"]
    assert did
    deps = admin.get(f"/api/departments?company_id={c1}").get_json()
    assert any(d["id"] == did for d in deps)
    assert admin.delete(f"/api/departments/{did}").status_code == 200


# ---- إنهاء الخدمة يحسب ويخزّن EOS ----
def test_end_service_stores_eos(admin):
    c1 = _first_company(admin)
    r = admin.post("/api/employees", json={"company_id": c1, "name": "للإنهاء", "basic_salary": 600,
                                           "hire_date": "2015-01-01"})
    eid = r.get_json()["id"]
    res = admin.post(f"/api/employees/{eid}/end-service", json={"reason": "termination"})
    data = res.get_json()
    assert res.status_code == 200
    assert data["settlement"] is not None
    assert data["settlement"]["total_settlement"] > 0


# ---- تقرير التزامات نهاية الخدمة ----
def test_eos_liability(admin):
    r = admin.get("/api/eos/liability")
    assert r.status_code == 200
    d = r.get_json()
    assert "total_liability" in d and d["total_liability"] >= 0


# ---- مسيّر الرواتب ----
def test_payroll_run(admin):
    c1 = _first_company(admin)
    r = admin.post("/api/payroll/run", json={"company_id": c1, "period": "2025-01"})
    assert r.status_code == 201
    d = r.get_json()
    assert d["count"] >= 1
    detail = admin.get(f"/api/payroll/runs/{d['run_id']}").get_json()
    assert len(detail["payslips"]) == d["count"]


# ---- رصيد الإجازات ----
def test_leave_balance(admin):
    c1 = _first_company(admin)
    eid = _emp_in(admin, c1)
    r = admin.get(f"/api/employees/{eid}/leave-balance")
    assert r.status_code == 200
    assert "balance" in r.get_json()


# ---- سياسة كلمة المرور ----
def test_weak_password_rejected(admin):
    c1 = _first_company(admin)
    r = admin.post("/api/users", json={"username": "weakuser", "password": "123",
                                       "role": "employee", "company_id": c1})
    assert r.status_code == 400


# ---- التحقق من نوع الملف ----
def test_upload_rejects_bad_extension(admin):
    import io
    c1 = _first_company(admin)
    data = {"title": "خبيث", "company_id": str(c1),
            "file": (io.BytesIO(b"<script>"), "x.html")}
    r = admin.post("/api/documents", data=data, content_type="multipart/form-data")
    assert r.status_code == 400


# ---- منع تعطيل آخر إدارة عليا ----
def test_cannot_disable_last_admin(admin):
    users = admin.get("/api/users").get_json()
    admin_user = [u for u in users if u["role"] == "super_admin"][0]
    r = admin.post(f"/api/users/{admin_user['id']}/toggle")
    assert r.status_code == 400


# ---- الإشعارات ----
def test_notifications_endpoint(admin):
    r = admin.get("/api/notifications")
    assert r.status_code == 200
    assert "items" in r.get_json()


# ---- عزل: مدير شركة لا يصل لموظف شركة أخرى ----
def test_isolation_cross_company(manager1):
    # manager1 في الشركة 1؛ نحاول الوصول لموظف الشركة 2
    comps = manager1.get("/api/companies").get_json()
    # المدير يرى شركته فقط
    assert len(comps) == 1
