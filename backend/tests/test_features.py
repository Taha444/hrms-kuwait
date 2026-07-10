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
    """P1-03: بعد قفل المسيّر (locked) لا يمكن إعادة تشغيله فوق نفسه."""
    acc = login(client, "100000000007", "account123")
    h = auth_headers(acc)
    period = f"{date.today().year}-{date.today().month:02d}"
    r = client.post("/api/payroll/run", headers=h, params={"period": period})
    run_id = r.json()["run_id"]
    lock = client.post(f"/api/payroll/runs/{run_id}/lock", headers=h)
    assert lock.status_code == 200 and lock.json()["status"] == "locked"
    r2 = client.post("/api/payroll/run", headers=h, params={"period": period})
    assert r2.status_code == 409


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
    # إنهاء الخدمة + EOS من اختصاص HR (انتقلت من المدير)
    hr = login(client, "100000000002", "hr12345")
    h = auth_headers(hr)
    # موظف جديد ثم إنهاء خدمته (حتى لا يؤثر على إجماليات بقية الاختبارات)
    new = client.post("/api/employees", headers=h, json={
        "civil_id": "199900099001", "name": "موظف للإنهاء", "basic_salary": 520,
        "hire_date": "2015-01-01", "contract_type": "indefinite"}).json()
    r = client.post(f"/api/employees/{new['id']}/terminate", headers=h,
                    params={"end_date": "2025-01-01", "reason": "termination"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "terminated"
    assert r.json()["settlement"]["total_settlement"] > 0
    # DEMO-014: النتيجة تُحفَظ في ملف الموظف وتُصدَّر
    prof = client.get(f"/api/employees/{new['id']}/profile", headers=h).json()
    assert prof["saved_eos"] and prof["saved_eos"]["total_settlement"] > 0
    assert prof["termination_date"] == "2025-01-01"
    exp = client.get(f"/api/reports/eos/{new['id']}", headers=h,
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
