# -*- coding: utf-8 -*-
"""PILOT-P0 tests — تدقيق كل بند من قائمة الإصلاحات قبل الـPilot."""
from datetime import datetime, timedelta

from tests.conftest import auth_headers, login


# =============================================================================
# P0-1: User↔Employee link
# =============================================================================
def test_P0_1_create_employee_user_without_employee_id_rejected(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    r = client.post("/api/users", headers=admin, json={
        "civil_id": "199912345678", "role": "employee", "company_id": 1,
        "full_name": "بدون موظف",
    })
    assert r.status_code == 400
    assert "employee_id" in r.json()["detail"] or "موظف" in r.json()["detail"]


def test_P0_1_create_employee_user_with_valid_employee_id_succeeds(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    # ننشئ موظف جديد ما اتربطش بحساب لسه (بدل ما نلمس موظفي seed اللي تعتمد عليهم اختبارات أخرى)
    r_emp = client.post("/api/employees", headers=admin, json={
        "civil_id": "199977766655", "name": "zzz_p01_test_emp",
        "company_id": 1, "basic_salary": 400, "hire_date": "2024-01-01",
    })
    emp_id = r_emp.json()["id"]

    r = client.post("/api/users", headers=admin, json={
        "civil_id": "199988877766", "role": "employee", "company_id": 1,
        "employee_id": emp_id, "full_name": "موظف صحيح",
    })
    assert r.status_code == 201


def test_P0_1_orphaned_endpoint_lists_users_without_employee_link(client):
    """/api/users/orphaned يعرض users بدور employee بلا employee_id."""
    admin = auth_headers(login(client, "000000000000", "admin123"))
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        # نصنع مستخدم يتيم يدويًا في DB (تجاوز الـ validator)
        orphan = models.User(
            civil_id="199900112233", role="employee", company_id=1,
            password_hash="x", employee_id=None, is_active=True,
        )
        db.add(orphan); db.commit()
        orphan_id = orphan.id
    finally:
        db.close()
    rows = client.get("/api/users/orphaned", headers=admin).json()
    assert any(r["id"] == orphan_id for r in rows)


# =============================================================================
# P0-3: Hide leave dates from employee's own view
# =============================================================================
def test_P0_3_employee_own_leave_hides_dates(client):
    emp_tok = login(client, "100000000101", "emp12345")
    emp = auth_headers(emp_tok)
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "leave",
        "payload_json": {"start_date": "2027-05-01", "end_date": "2027-05-03", "days": 3,
                         "reason": "ظرف عائلي"},
    })
    rid = r.json()["id"]
    # الموظف نفسه: التواريخ مخفية
    own = client.get(f"/api/requests/{rid}", headers=emp).json()
    assert "start_date" not in own["payload"]
    assert "end_date" not in own["payload"]
    assert "days" not in own["payload"]
    assert own["payload"].get("reason") == "ظرف عائلي"  # النص لسه ظاهر
    assert own["payload_masked"] is True

    # المدير: يشوف كل شيء
    mgr = auth_headers(login(client, "100000000001", "manager123"))
    mgr_view = client.get(f"/api/requests/{rid}", headers=mgr).json()
    assert mgr_view["payload"].get("start_date") == "2027-05-01"
    assert mgr_view["payload"].get("end_date") == "2027-05-03"
    assert mgr_view["payload_masked"] is False


# =============================================================================
# P0-6: Employee ID auto-generation
# =============================================================================
def test_P0_6_new_employee_gets_auto_employee_no(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    # نستخدم اسم يسبقه zzz-prefix عشان يتصنّف آخر الترتيب ولا يؤثر على "الأول" في اختبارات لاحقة
    r = client.post("/api/employees", headers=admin, json={
        "civil_id": "288800008888", "name": "zzz_p06_emp_auto",
        "company_id": 1, "basic_salary": 400, "hire_date": "2024-01-01",
    })
    assert r.status_code == 201
    emp = r.json()
    assert emp["employee_no"] is not None
    # الصيغة: COxx-BRxx-####
    import re
    assert re.match(r"^CO\d{2}-BR\d{2}-\d{4}$", emp["employee_no"])


def test_P0_6_employee_no_is_unique(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    r1 = client.post("/api/employees", headers=admin, json={
        "civil_id": "277700007777", "name": "zzz_p06_uniq_a", "company_id": 1,
        "basic_salary": 400, "hire_date": "2024-01-01",
    })
    r2 = client.post("/api/employees", headers=admin, json={
        "civil_id": "277700007778", "name": "zzz_p06_uniq_b", "company_id": 1,
        "basic_salary": 400, "hire_date": "2024-01-01",
    })
    assert r1.json()["employee_no"] != r2.json()["employee_no"]


# =============================================================================
# P0-11: Commercial register unique
# =============================================================================
def test_P0_11_duplicate_commercial_reg_rejected(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    r1 = client.post("/api/companies", headers=admin, json={
        "name": "شركة تجريبية 1", "commercial_reg": "CR-99999",
    })
    assert r1.status_code == 201
    r2 = client.post("/api/companies", headers=admin, json={
        "name": "شركة تجريبية 2", "commercial_reg": "CR-99999",
    })
    assert r2.status_code == 409
    assert "السجل التجاري" in r2.json()["detail"]


def test_P0_11_null_commercial_reg_allowed_multiple(client):
    """شركتان بدون سجل تجاري (NULL) لا يعتبر تكرارًا."""
    admin = auth_headers(login(client, "000000000000", "admin123"))
    r1 = client.post("/api/companies", headers=admin, json={"name": "بلا سجل 1"})
    r2 = client.post("/api/companies", headers=admin, json={"name": "بلا سجل 2"})
    assert r1.status_code == 201
    assert r2.status_code == 201
