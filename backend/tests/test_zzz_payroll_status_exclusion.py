# -*- coding: utf-8 -*-
"""من على الرواتب — قرارُ المالك (2026-09-17) مُثبَّتًا.

كان ``compute_payroll`` يختار ``status == "active"`` وحده، فكان:

- «**في إجازة**» (من شاشة ملف الموظف) يُسقط راتبَ الشهر كلّه، والإجازةُ
  السنوية مدفوعة ومسجَّلةٌ صفوفَ ``Leave``.
- ومن سُوِّيت خدمتُه قبل المسيّر يسقط من **شهره الأخير** كلّه — ومنطقُ التناسب
  المكتوبُ لهذا الشهر لا يبلغه (إنهاءٌ في 20/9 على 2,500 = 1,666.667 لا يُدفع).

**والقرار**: «في إجازة» و«موقوف» يُدفعان (``PAYABLE_STATUSES``)، ومن انتهت
خدمته يبقى في مسيّر شهر إنهائه حتى تاريخ الإنهاء. ولا يمتدّ لما بعده.

**ودرسُ قياس**: ``SessionLocal`` بـ``autoflush=False`` — فالحرّاسُ تكتب
``flush`` صريحًا قبل كل قراءة.
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select

from app import deps, models, payroll as P
from app.database import SessionLocal


def _slip(db, emp_id: int, cid: int, y: int, m: int):
    rows = [r for r in P.compute_payroll(db, cid, y, m)["payslips"] if r["employee_id"] == emp_id]
    return rows[0] if rows else None


def _paid_employee(db):
    return db.scalar(select(models.Employee).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        models.Employee.basic_salary.isnot(None),
        models.Employee.hire_date < date(2026, 1, 1)))


@pytest.mark.parametrize("status", ["vacation", "suspended"])
def test_leave_and_suspension_stay_on_the_payroll(status):
    db = SessionLocal()
    try:
        emp = _paid_employee(db)
        full = _slip(db, emp.id, emp.company_id, 2026, 9)["net"]
        emp.status = status
        db.flush()
        s = _slip(db, emp.id, emp.company_id, 2026, 9)
        assert s is not None, f"«{status}» سقط من المسيّر — والقرارُ أنه يُدفع"
        assert s["net"] == full, (status, s["net"], full)
    finally:
        db.rollback()
        db.close()


def test_a_settled_employee_is_paid_up_to_the_termination_date():
    db = SessionLocal()
    try:
        emp = _paid_employee(db)
        emp.status = "terminated"
        emp.termination_date = date(2026, 9, 20)
        db.flush()
        s = _slip(db, emp.id, emp.company_id, 2026, 9)
        assert s is not None, "المُسوّى سقط من مسيّر شهره الأخير"
        expected = round(float(emp.basic_salary) / 30 * 20, 3)
        assert abs(s["earned_basic"] - expected) < 0.01, (s["earned_basic"], expected)
        assert s["partial_month"]
    finally:
        db.rollback()
        db.close()


def test_the_month_after_termination_pays_nothing():
    db = SessionLocal()
    try:
        emp = _paid_employee(db)
        emp.status = "terminated"
        emp.termination_date = date(2026, 9, 20)
        db.flush()
        assert _slip(db, emp.id, emp.company_id, 2026, 10) is None
    finally:
        db.rollback()
        db.close()


def test_an_ended_service_without_a_date_is_not_paid():
    """ومن انتهت خدمته بلا تاريخٍ مُسجَّل لا يُتناسَب له — فلا يُدرَج."""
    db = SessionLocal()
    try:
        emp = _paid_employee(db)
        emp.status = "resigned"
        emp.termination_date = None
        db.flush()
        assert _slip(db, emp.id, emp.company_id, 2026, 9) is None
    finally:
        db.rollback()
        db.close()


def test_the_decision_lives_in_one_constant():
    assert deps.PAYABLE_STATUSES == ("active", "vacation", "suspended")
    import inspect

    from app.routers import payroll as RP

    assert "PAYABLE_STATUSES" in inspect.getsource(P.compute_payroll)
    assert "PAYABLE_STATUSES" in inspect.getsource(RP.finalize_run)
