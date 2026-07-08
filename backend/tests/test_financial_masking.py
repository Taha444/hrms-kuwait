# -*- coding: utf-8 -*-
"""إخفاء الحقول المالية الحساسة (FIX-013): الخصم يُخفى عن المسؤول المباشر، يظهر للمحاسب/الإدارة."""
from datetime import date

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login


def _emp_and_add_deduction():
    db = SessionLocal()
    emp = db.query(models.Employee).filter_by(civil_id="100000000101").first()
    d = models.Deduction(company_id=emp.company_id, employee_id=emp.id, amount=75.5,
                        reason="مخالفة حضور", ded_type="violation", date=date.today())
    db.add(d)
    db.commit()
    eid = emp.id
    db.close()
    return eid


def test_supervisor_sees_masked_deduction_amount(client):
    eid = _emp_and_add_deduction()
    sup = auth_headers(login(client, "100000000005", "sup12345"))
    prof = client.get(f"/api/employees/{eid}/profile", headers=sup).json()
    assert prof["deductions_masked"] is True
    assert all(d["amount"] is None for d in prof["deductions"])
    assert any(d["reason"] == "مخالفة حضور" for d in prof["deductions"])


def test_accountant_sees_full_deduction_amount(client):
    eid = _emp_and_add_deduction()
    acc = auth_headers(login(client, "100000000007", "account123"))
    prof = client.get(f"/api/employees/{eid}/profile", headers=acc).json()
    assert prof["deductions_masked"] is False
    assert any(d["amount"] == 75.5 for d in prof["deductions"])


def test_payroll_export_requires_view_payroll_not_just_export_reports(client):
    # مسؤول الفرع يملك export_reports لكن ليس view_payroll → يُمنع من تصدير الرواتب
    sup = auth_headers(login(client, "100000000005", "sup12345"))
    r = client.get("/api/reports/payroll/1", headers=sup, params={"reason": "x"})
    assert r.status_code == 403
