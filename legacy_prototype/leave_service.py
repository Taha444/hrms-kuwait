# -*- coding: utf-8 -*-
"""
خدمة الإجازات: تجميع الرصيد السنوي (accrual) وخصمه عند اعتماد الإجازة المدفوعة.
الرصيد القانوني الافتراضي في الكويت 30 يومًا سنويًا (قابل للتعديل لكل شركة).
"""
from datetime import date

import db


def _parse(d):
    try:
        return date.fromisoformat(str(d)[:10])
    except (ValueError, TypeError):
        return None


def accrue_for_employee(employee, company):
    """يحسب الرصيد المستحق بناءً على مدة الخدمة منذ التعيين.

    يرجع الرصيد المتوقع (أيام). الخصومات تُطبّق عند اعتماد الإجازات.
    """
    hire = _parse(employee.get("hire_date"))
    if not hire:
        return employee.get("annual_leave_balance", 0) or 0
    days_per_year = (company or {}).get("annual_leave_days", 30) or 30
    served_years = (date.today() - hire).days / 365.25
    return round(served_years * days_per_year, 2)


def recalc_balance(employee_id):
    """يعيد حساب الرصيد = المستحق - المستهلك (الإجازات السنوية المدفوعة المعتمدة)."""
    emp = db.query("SELECT * FROM employees WHERE id=?", (employee_id,), one=True)
    if not emp:
        return 0
    emp = db.row_to_dict(emp)
    comp = db.row_to_dict(db.query("SELECT * FROM companies WHERE id=?", (emp["company_id"],), one=True))
    accrued = accrue_for_employee(emp, comp)
    used = db.query(
        """SELECT COALESCE(SUM(days),0) AS n FROM leaves
           WHERE employee_id=? AND status='approved' AND paid=1 AND leave_type='annual'""",
        (employee_id,), one=True)["n"]
    balance = round(accrued - (used or 0), 2)
    db.execute("UPDATE employees SET annual_leave_balance=? WHERE id=?", (balance, employee_id))
    return balance


def recalc_all(company_id=None):
    """يعيد حساب رصيد كل الموظفين (لمهمة الجدولة)."""
    if company_id:
        rows = db.query("SELECT id FROM employees WHERE company_id=?", (company_id,))
    else:
        rows = db.query("SELECT id FROM employees")
    for r in rows:
        recalc_balance(r["id"])
    return len(rows)
