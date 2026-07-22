# -*- coding: utf-8 -*-
"""اختبارات الموديولات الجديدة: الرواتب، التصدير، التدقيق، إنهاء الخدمة، OCR، التحقق."""
from datetime import date

from app.ocr import parse_mrz_td3
from tests.conftest import auth_headers, login


# ----------------------------- OCR / MRZ -----------------------------

def test_mrz_passport_parser():
    mrz = ("P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n"
           "L898902C36UTO7408122F1204159ZE184226B<<<<<10")
    r = parse_mrz_td3(mrz)
    assert r["passport_number"] == "L898902C3"
    assert r["nationality"] == "UTO"
    assert "ERIKSSON" in r["full_name"]
    assert r["expiry_date"] == "2012-04-15"
    assert r["_checks"]["passport_number"] is True  # رقم الضبط صحيح


# ----------------------------- الرواتب -----------------------------

def test_payroll_run_and_view(client):
    acc = login(client, "100000000007", "account123")  # محاسب الشركة
    h = auth_headers(acc)
    period = f"{date.today().year}-{date.today().month:02d}"
    r = client.post("/api/payroll/run", headers=h, params={"period": period})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["employees_count"] == 7  # 6 موظفين + المحاسب (له ملف موظف أيًضا)
    assert "net" in body["totals"]
    assert len(body["payslips"]) == 7
    # كل قسيمة لها صافي محسوب
    assert all("net" in p for p in body["payslips"])
    runs = client.get("/api/payroll/runs", headers=h).json()
    assert any(x["period"] == period for x in runs)


def test_payroll_requires_permission(client):
    emp = login(client, "100000000101", "emp12345")
    r = client.post("/api/payroll/run", headers=auth_headers(emp), params={"period": "2026-01"})
    assert r.status_code == 403


def test_payroll_rejects_future_period_without_force(client):
    """P1-03: لا تشغيل شهر مستقبلي بلا استثناء صريح force_future."""
    acc = login(client, "100000000007", "account123")
    h = auth_headers(acc)
    future = f"{date.today().year + 5}-01"
    r = client.post("/api/payroll/run", headers=h, params={"period": future})
    assert r.status_code == 400
    r2 = client.post("/api/payroll/run", headers=h, params={"period": future, "force_future": True})
    assert r2.status_code == 200, r2.text


def test_payroll_lock_prevents_rerun(client):
    """PILOT-P0-7: المسيّر لا يقفل مباشرة — يمر بـ prepared → approved → finalized → locked.
    بعد الـlock إعادة التشغيل فوق نفس الفترة تُرفض ويجب adjustment."""
    acc = login(client, "100000000007", "account123")  # المُجَهِّز
    admin = login(client, "000000000000", "admin123")  # المُعتمِد المختلف
    h_acc = auth_headers(acc)
    h_admin = auth_headers(admin)
    period = f"{date.today().year}-{date.today().month:02d}"
    # 1) تجهيز
    r = client.post("/api/payroll/run", headers=h_acc, params={"period": period})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "prepared"
    run_id = r.json()["run_id"]
    # 2) اعتماد (لازم مستخدم مختلف)
    self_approve = client.post(f"/api/payroll/runs/{run_id}/approve", headers=h_acc)
    assert self_approve.status_code == 403  # المُجَهِّز لا يعتمد نفسه
    ok = client.post(f"/api/payroll/runs/{run_id}/approve", headers=h_admin)
    assert ok.status_code == 200 and ok.json()["status"] == "approved"
    # 3) finalize
    fin = client.post(f"/api/payroll/runs/{run_id}/finalize", headers=h_admin)
    assert fin.status_code == 200 and fin.json()["status"] == "finalized"
    # 4) lock
    lock = client.post(f"/api/payroll/runs/{run_id}/lock", headers=h_admin)
    assert lock.status_code == 200 and lock.json()["status"] == "locked"
    # إعادة التشغيل فوق مسيّر متقدّم — مرفوضة
    r2 = client.post("/api/payroll/run", headers=h_acc, params={"period": period})
    assert r2.status_code == 409
    # التسوية بعد lock — مسموحة بسبب صريح
    adj = client.post(f"/api/payroll/runs/{run_id}/adjustment", headers=h_admin,
                     params={"reason": "تصحيح خصم"})
    assert adj.status_code == 200 and adj.json()["status"] == "adjustment_run"
    assert adj.json()["adjustment_of"] == run_id


# ----------------------------- التصدير -----------------------------

def test_export_employees_xlsx_and_csv(client):
    mgr = login(client, "100000000001", "manager123")
    h = auth_headers(mgr)
    x = client.get("/api/reports/employees", headers=h, params={"fmt": "xlsx"})
    assert x.status_code == 200
    assert x.content[:2] == b"PK"  # توقيع ملف xlsx (zip)
    c = client.get("/api/reports/employees", headers=h, params={"fmt": "csv"})
    assert c.status_code == 200
    assert c.content[:3] == b"\xef\xbb\xbf"  # BOM لدعم العربية في Excel


# ----------------------------- التدقيق -----------------------------

def test_audit_log_visible_to_admin(client):
    # سجل التدقيق للإدارة العليا فقط (تمت إزالته من المدير)
    admin = login(client, "000000000000", "admin123")
    r = client.get("/api/audit", headers=auth_headers(admin))
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    # تسجيل الدخول يُسجَّل في التدقيق
    assert any(e["action"] == "login" for e in r.json())


def test_audit_denied_for_employee(client):
    emp = login(client, "100000000101", "emp12345")
    assert client.get("/api/audit", headers=auth_headers(emp)).status_code == 403


# ----------------------------- إنهاء الخدمة -----------------------------

def test_terminate_employee_computes_eos(client):
    """PILOT-P0-8: التنفيذ الفوري أُلغي — دورة إلزامية (HR يحضّر → محاسب يعتمد → HR ينفّذ)."""
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    acc = auth_headers(login(client, "100000000007", "account123"))  # مُعتمِد ماليًا
    # موظف جديد ثم إنهاء خدمته
    new = client.post("/api/employees", headers=hr, json={
        "civil_id": "199900099001", "name": "موظف للإنهاء", "basic_salary": 520,
        "hire_date": "2015-01-01", "contract_type": "indefinite"}).json()
    emp_id = new["id"]

    # 1) HR يحضّر المسودة — لا يتغير الـstatus
    prep = client.post(f"/api/employees/{emp_id}/terminate", headers=hr,
                       params={"end_date": "2025-01-01", "reason": "termination"})
    assert prep.status_code == 200, prep.text
    assert prep.json()["stage"] == "prepared"
    assert prep.json()["status"] != "terminated"
    assert prep.json()["settlement"]["total_settlement"] > 0

    # 2) HR لا يعتمد نفسه
    self_appr = client.post(f"/api/employees/{emp_id}/terminate/approve", headers=hr)
    assert self_appr.status_code in (403, 404)  # 403 لو له approve_termination، 404 لو ليس له

    # 3) المحاسب يعتمد ماليًا
    appr = client.post(f"/api/employees/{emp_id}/terminate/approve", headers=acc)
    assert appr.status_code == 200
    assert appr.json()["stage"] == "approved"

    # 4) HR ينفذ — تغيير status = terminated
    execd = client.post(f"/api/employees/{emp_id}/terminate/execute", headers=hr)
    assert execd.status_code == 200
    assert execd.json()["status"] == "terminated"

    # DEMO-014: النتيجة تُحفَظ في ملف الموظف وتُصدَّر
    prof = client.get(f"/api/employees/{emp_id}/profile", headers=hr).json()
    assert prof["saved_eos"] and prof["saved_eos"]["total_settlement"] > 0
    assert prof["termination_date"] == "2025-01-01"
    exp = client.get(f"/api/reports/eos/{emp_id}", headers=hr,
                     params={"fmt": "xlsx", "reason": "أرشفة"})
    assert exp.status_code == 200 and exp.content[:2] == b"PK"


# ----------------------------- التحقق من المدخلات -----------------------------

def test_invalid_civil_id_rejected(client):
    mgr = login(client, "100000000001", "manager123")
    r = client.post("/api/employees", headers=auth_headers(mgr), json={
        "civil_id": "abc!!", "name": "خطأ", "basic_salary": 100})
    assert r.status_code == 422  # الرقم المدني غير صالح


def test_leave_end_before_start_rejected(client):
    emp = login(client, "100000000101", "emp12345")
    r = client.post("/api/requests", headers=auth_headers(emp), json={
        "request_type_code": "leave",
        "payload_json": {"start_date": "2026-08-10", "end_date": "2026-08-01"}})
    assert r.status_code == 400
