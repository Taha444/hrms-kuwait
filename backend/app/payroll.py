# -*- coding: utf-8 -*-
"""محرّك الرواتب: يحسب مسيّر رواتب شهري من الحضور والخصومات والإضافي.

القواعد (قابلة للضبط):
- أجر اليوم للرواتب = الراتب الأساسي ÷ 30 (تقويمي).
- خصم الغياب = أجر اليوم × أيام الغياب غير المبرّر.
- الإضافي = (أجر الساعة × 1.25 × ساعات الإضافي)؛ أجر الساعة = أجر اليوم ÷ 8.
- الصافي = الأساسي + الإضافي − (خصم الغياب + الخصومات الأخرى).
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models

PAYROLL_DAY_DIVISOR = 30
OVERTIME_RATE = 1.25


def compute_payroll(db: Session, company_id: int, year: int, month: int) -> dict:
    """يحسب مسيّر رواتب الشركة لشهر معيّن ويُرجع قسائم الموظفين والإجماليات."""
    days_in_month = calendar.monthrange(year, month)[1]
    first = datetime(year, month, 1)
    nxt = datetime(year, month, days_in_month) + timedelta(days=1)

    employees = db.scalars(select(models.Employee).where(
        models.Employee.company_id == company_id,
        models.Employee.status == "active")).all()

    payslips = []
    totals = {"gross": 0.0, "deductions": 0.0, "net": 0.0, "overtime": 0.0}
    for e in employees:
        basic = float(e.basic_salary or 0)
        daily = basic / PAYROLL_DAY_DIVISOR if basic else 0.0
        hourly = daily / 8 if daily else 0.0

        recs = db.scalars(select(models.AttendanceRecord).where(
            models.AttendanceRecord.employee_id == e.id,
            models.AttendanceRecord.check_in_at >= first,
            models.AttendanceRecord.check_in_at < nxt)).all()
        present_days = len(recs)
        overtime_minutes = sum(r.overtime_minutes or 0 for r in recs)

        # أيام الغياب: أيام العمل الماضية بلا حضور ولا إجازة (تقدير مبسّط للموظفين المتتبَّعين)
        absent_days = 0
        if e.attendance_mode != "none":
            shift = db.get(models.Shift, e.shift_id) if e.shift_id else None
            workset = set((shift.work_days if shift else "0,1,2,3,4").split(","))
            leaves = db.scalars(select(models.Leave).where(
                models.Leave.employee_id == e.id, models.Leave.status == "approved")).all()
            present_dates = {r.check_in_at.date() for r in recs}
            today = date.today()
            for i in range(days_in_month):
                day = date(year, month, i + 1)
                if day > today:
                    continue
                if str((day.weekday() + 1) % 7) not in workset:
                    continue
                if day in present_dates:
                    continue
                if any(lv.start_date <= day <= lv.end_date for lv in leaves):
                    continue
                absent_days += 1

        deductions = db.scalars(select(models.Deduction).where(
            models.Deduction.employee_id == e.id,
            models.Deduction.date >= first.date(),
            models.Deduction.date < nxt.date())).all()
        other_deductions = sum(float(x.amount or 0) for x in deductions)

        overtime_pay = round(hourly * OVERTIME_RATE * (overtime_minutes / 60), 3)
        absence_deduction = round(daily * absent_days, 3)
        gross = round(basic + overtime_pay, 3)
        total_ded = round(absence_deduction + other_deductions, 3)
        net = round(gross - total_ded, 3)

        payslips.append({
            "employee_id": e.id, "name": e.name, "job_title": e.job_title,
            "basic_salary": round(basic, 3), "present_days": present_days,
            "absent_days": absent_days, "overtime_minutes": overtime_minutes,
            "overtime_pay": overtime_pay, "absence_deduction": absence_deduction,
            "other_deductions": round(other_deductions, 3), "gross": gross,
            "total_deductions": total_ded, "net": net,
        })
        totals["gross"] += gross
        totals["deductions"] += total_ded
        totals["net"] += net
        totals["overtime"] += overtime_pay

    totals = {k: round(v, 3) for k, v in totals.items()}
    return {"period": f"{year}-{month:02d}", "company_id": company_id,
            "employees_count": len(payslips), "totals": totals, "payslips": payslips}
