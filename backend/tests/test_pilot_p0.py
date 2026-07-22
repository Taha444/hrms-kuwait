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
        "attendance_mode": "qr",  # SEC2-17: سياسة صريحة
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
        "attendance_mode": "qr",
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
        "basic_salary": 400, "hire_date": "2024-01-01", "attendance_mode": "qr",
    })
    r2 = client.post("/api/employees", headers=admin, json={
        "civil_id": "277700007778", "name": "zzz_p06_uniq_b", "company_id": 1,
        "basic_salary": 400, "hire_date": "2024-01-01", "attendance_mode": "qr",
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


# =============================================================================
# P0-7: Payroll staged workflow (prepared → approved → finalized → locked)
# =============================================================================
# لكل اختبار فترة مختلفة (شهر قديم) حتى لا يتشارك state مع اختبارات features.py
def _p07_period(offset_months: int) -> str:
    """كل اختبار P0-7 يستهلك شهرًا فريدًا (بداية 12 شهرًا للخلف) لتفادي تشارك state مع
    اختبارات payroll الأخرى (مثال 2026-02 المستخدَم في test_roles_phase1)."""
    from datetime import date
    y, m = date.today().year, date.today().month
    m -= (12 + offset_months)  # اقفز عامًا كاملًا قبل offset الفردي
    while m <= 0:
        m += 12; y -= 1
    return f"{y}-{m:02d}"


def test_P0_7_payroll_new_run_starts_prepared_not_finalized(client):
    """المسيّر الجديد يبدأ بـ prepared فقط — لا اعتماد ذاتي."""
    acc = auth_headers(login(client, "100000000007", "account123"))
    r = client.post("/api/payroll/run", headers=acc, params={"period": _p07_period(2)})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "prepared"


def test_P0_7_self_approval_rejected(client):
    """المُجَهِّز لا يعتمد مسيّره — فصل السلطات إلزامي."""
    acc = auth_headers(login(client, "100000000007", "account123"))
    r = client.post("/api/payroll/run", headers=acc, params={"period": _p07_period(3)})
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    rej = client.post(f"/api/payroll/runs/{run_id}/approve", headers=acc)
    assert rej.status_code == 403


def test_P0_7_finalize_before_approve_rejected(client):
    """لا finalize قبل approve."""
    acc = auth_headers(login(client, "100000000007", "account123"))
    admin = auth_headers(login(client, "000000000000", "admin123"))
    r = client.post("/api/payroll/run", headers=acc, params={"period": _p07_period(4)})
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    fin = client.post(f"/api/payroll/runs/{run_id}/finalize", headers=admin)
    assert fin.status_code == 409


def test_P0_7_lock_before_finalize_rejected(client):
    """لا lock قبل finalize."""
    acc = auth_headers(login(client, "100000000007", "account123"))
    admin = auth_headers(login(client, "000000000000", "admin123"))
    r = client.post("/api/payroll/run", headers=acc, params={"period": _p07_period(5)})
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    client.post(f"/api/payroll/runs/{run_id}/approve", headers=admin)
    lock = client.post(f"/api/payroll/runs/{run_id}/lock", headers=admin)
    assert lock.status_code == 409  # الحالة الآن approved، والقفل يشترط finalized


# =============================================================================
# P0-8: Termination staged workflow (no direct exec)
# =============================================================================
from datetime import date

def _make_test_emp(client, hr, name_suffix, hire="2015-01-01", salary=500):
    """يخلق موظف اختبار جديد بأسم يبدأ zzz_p08_ حتى يترتب آخر ولا يؤثر على تعدادات أخرى."""
    r = client.post("/api/employees", headers=hr, json={
        "civil_id": f"19998888{name_suffix:04d}", "name": f"zzz_p08_emp_{name_suffix}",
        "basic_salary": salary, "hire_date": hire, "contract_type": "indefinite",
        "company_id": 1, "attendance_mode": "qr",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_P0_8_terminate_creates_draft_not_terminates(client):
    """التنفيذ الفوري أُلغي — الحالة تظل active بعد /terminate."""
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    emp_id = _make_test_emp(client, hr, name_suffix=101)
    r = client.post(f"/api/employees/{emp_id}/terminate", headers=hr,
                    params={"end_date": "2025-01-01", "reason": "termination"})
    assert r.status_code == 200
    assert r.json()["stage"] == "prepared"
    assert r.json()["status"] != "terminated"


def test_P0_8_execute_before_approve_rejected(client):
    """لا تنفيذ قبل الاعتماد."""
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    emp_id = _make_test_emp(client, hr, name_suffix=102)
    client.post(f"/api/employees/{emp_id}/terminate", headers=hr,
                params={"end_date": "2025-01-01", "reason": "termination"})
    execd = client.post(f"/api/employees/{emp_id}/terminate/execute", headers=hr)
    assert execd.status_code == 409


def test_P0_8_bad_inputs_rejected(client):
    """يرفض: سبب غير معتمد + end_date قبل hire_date + راتب صفري."""
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    emp_id = _make_test_emp(client, hr, name_suffix=103)
    bad_reason = client.post(f"/api/employees/{emp_id}/terminate", headers=hr,
                             params={"end_date": "2025-01-01", "reason": "xxx"})
    assert bad_reason.status_code == 400
    bad_date = client.post(f"/api/employees/{emp_id}/terminate", headers=hr,
                           params={"end_date": "2010-01-01", "reason": "termination"})
    assert bad_date.status_code == 400
    # موظف براتب سالب/صفري في القاعدة (تجاوز الـschema — سيناريو موروث)
    from app.database import SessionLocal
    from app import models
    dbs = SessionLocal()
    try:
        legacy = models.Employee(company_id=1, civil_id="199988870104",
                                 name="zzz_p08_zero_sal", basic_salary=0,
                                 hire_date=date(2020, 1, 1), status="active",
                                 attendance_mode="qr")
        dbs.add(legacy); dbs.commit()
        zero_id = legacy.id
    finally:
        dbs.close()
    zero_r = client.post(f"/api/employees/{zero_id}/terminate", headers=hr,
                        params={"end_date": "2025-01-01", "reason": "termination"})
    assert zero_r.status_code == 400


def test_P0_8_duplicate_draft_rejected(client):
    """لا يمكن تحضير مسودتين متوازيتين لنفس الموظف."""
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    emp_id = _make_test_emp(client, hr, name_suffix=105)
    client.post(f"/api/employees/{emp_id}/terminate", headers=hr,
                params={"end_date": "2025-01-01", "reason": "termination"})
    dup = client.post(f"/api/employees/{emp_id}/terminate", headers=hr,
                     params={"end_date": "2025-02-01", "reason": "termination"})
    assert dup.status_code == 409


def test_P0_8_full_workflow_terminates(client):
    """المسار الكامل: HR يحضّر → المحاسب يعتمد → HR ينفّذ → status=terminated."""
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    acc = auth_headers(login(client, "100000000007", "account123"))
    emp_id = _make_test_emp(client, hr, name_suffix=106)
    client.post(f"/api/employees/{emp_id}/terminate", headers=hr,
                params={"end_date": "2025-01-01", "reason": "termination"})
    client.post(f"/api/employees/{emp_id}/terminate/approve", headers=acc)
    execd = client.post(f"/api/employees/{emp_id}/terminate/execute", headers=hr)
    assert execd.status_code == 200
    assert execd.json()["status"] == "terminated"


def test_P0_8_cancel_draft(client):
    """يمكن إلغاء المسودة قبل التنفيذ."""
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    emp_id = _make_test_emp(client, hr, name_suffix=107)
    client.post(f"/api/employees/{emp_id}/terminate", headers=hr,
                params={"end_date": "2025-01-01", "reason": "termination"})
    cancel = client.post(f"/api/employees/{emp_id}/terminate/cancel", headers=hr)
    assert cancel.status_code == 200
    # بعد الإلغاء يمكن تحضير مسودة جديدة
    new_draft = client.post(f"/api/employees/{emp_id}/terminate", headers=hr,
                            params={"end_date": "2025-02-01", "reason": "termination"})
    assert new_draft.status_code == 200


def test_P0_7_adjustment_requires_reason_and_lock(client):
    """التسوية بعد lock فقط، وسبب إلزامي."""
    acc = auth_headers(login(client, "100000000007", "account123"))
    admin = auth_headers(login(client, "000000000000", "admin123"))
    period = _p07_period(6)
    r = client.post("/api/payroll/run", headers=acc, params={"period": period})
    run_id = r.json()["run_id"]
    # مسيّر لسه في prepared — لا تسوية
    adj_early = client.post(f"/api/payroll/runs/{run_id}/adjustment", headers=admin,
                            params={"reason": "تصحيح"})
    assert adj_early.status_code == 409
    # مسار الاعتماد الكامل
    client.post(f"/api/payroll/runs/{run_id}/approve", headers=admin)
    client.post(f"/api/payroll/runs/{run_id}/finalize", headers=admin)
    client.post(f"/api/payroll/runs/{run_id}/lock", headers=admin)
    # سبب فارغ — مرفوض
    no_reason = client.post(f"/api/payroll/runs/{run_id}/adjustment", headers=admin,
                            params={"reason": "   "})
    assert no_reason.status_code == 400
    # تسوية صحيحة
    adj = client.post(f"/api/payroll/runs/{run_id}/adjustment", headers=admin,
                     params={"reason": "تصحيح خصم شهر سابق"})
    assert adj.status_code == 200
    assert adj.json()["status"] == "adjustment_run"
