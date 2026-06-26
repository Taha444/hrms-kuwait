# -*- coding: utf-8 -*-
"""
محرك مسيّر الرواتب الشهري.
الصافي = الراتب الأساسي + البدلات + أجر الساعات الإضافية - الخصومات - التأمينات.
أجر الساعة الإضافية وفق القانون الكويتي ≈ أجر الساعة العادية × 1.25 (تقديري).
"""
from datetime import date

import db

OVERTIME_MULTIPLIER = 1.25


def _month_bounds(period):
    """يرجع (أول الشهر، آخر الشهر) لصيغة YYYY-MM."""
    y, m = period.split("-")
    y, m = int(y), int(m)
    start = date(y, m, 1)
    end = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    return start.isoformat(), end.isoformat()


def compute_payslip(employee, company, period):
    """يحسب قسيمة راتب موظف لشهر معيّن. يرجع dict بالتفاصيل (دون حفظ)."""
    basic = float(employee.get("basic_salary") or 0)
    eid = employee["id"]
    start, end = _month_bounds(period)

    # البدلات المتكررة
    allow_rows = db.query(
        "SELECT COALESCE(SUM(amount),0) AS n FROM allowances WHERE employee_id=? AND recurring=1",
        (eid,), one=True)
    allowances = float(allow_rows["n"] or 0)

    # الخصومات ضمن الشهر
    ded_rows = db.query(
        "SELECT COALESCE(SUM(amount),0) AS n FROM deductions WHERE employee_id=? AND date>=? AND date<?",
        (eid, start, end), one=True)
    deductions = float(ded_rows["n"] or 0)

    # الساعات الإضافية ضمن الشهر
    ot_rows = db.query(
        "SELECT COALESCE(SUM(overtime_hours),0) AS n FROM attendance WHERE employee_id=? AND date>=? AND date<?",
        (eid, start, end), one=True)
    overtime_hours = float(ot_rows["n"] or 0)

    workweek = (company or {}).get("workweek_hours", 48) or 48
    monthly_hours = workweek * 52 / 12.0
    hourly = basic / monthly_hours if monthly_hours else 0
    overtime_pay = round(hourly * OVERTIME_MULTIPLIER * overtime_hours, 3)

    gosi_rate = float((company or {}).get("gosi_rate", 0) or 0)
    gosi = round(basic * gosi_rate / 100.0, 3) if gosi_rate else 0.0

    gross = round(basic + allowances + overtime_pay, 3)
    net = round(gross - deductions - gosi, 3)

    return {
        "employee_id": eid,
        "employee_name": employee.get("name"),
        "basic_salary": round(basic, 3),
        "allowances": round(allowances, 3),
        "overtime_pay": overtime_pay,
        "overtime_hours": overtime_hours,
        "deductions": round(deductions, 3),
        "gosi": gosi,
        "gross": gross,
        "net": net,
        "currency": "KWD",
        "period": period,
    }


def run_payroll(company_id, period, created_by=None, note=None):
    """ينشئ مسيّر رواتب لشهر ويولّد قسائم لكل موظف نشط. يرجع (run_id, slips)."""
    company = db.row_to_dict(db.query("SELECT * FROM companies WHERE id=?", (company_id,), one=True))
    employees = db.rows_to_list(db.query(
        "SELECT * FROM employees WHERE company_id=? AND status='active'", (company_id,)))

    run_id = db.execute(
        "INSERT INTO payroll_runs (company_id, period, status, note, created_by) VALUES (?,?,?,?,?)",
        (company_id, period, "draft", note, created_by))

    slips = []
    for emp in employees:
        slip = compute_payslip(emp, company, period)
        db.execute(
            """INSERT INTO payslips (run_id, company_id, employee_id, basic_salary, allowances,
                                     overtime_pay, deductions, gosi, gross, net)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (run_id, company_id, emp["id"], slip["basic_salary"], slip["allowances"],
             slip["overtime_pay"], slip["deductions"], slip["gosi"], slip["gross"], slip["net"]))
        slips.append(slip)
    return run_id, slips
