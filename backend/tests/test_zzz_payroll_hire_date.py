# -*- coding: utf-8 -*-
"""P0 — المسيّر يحترم مدة التوظيف.

**العطل**: التصفية كانت على الشركة والحالة فقط، فيدخل الموظف كشف **أي**
شهر بكامل راتبه — بما فيه شهور تسبق تعيينه بسنوات. قِيس فعًلا: مسيّر
2010 و2018 و2026 يعطي الأسماء نفسها والإجمالي نفسه.

و``hire_date`` كان يُقرأ في مكان واحد: قصّ نافذة **الغياب**. فالتاريخ
معروف للنظام ومستعمَل في الخصم، ولا يمنع صرف راتب عن شهر لم يكن الموظف
فيه موظًَّفا.

**والشهر الجزئي يُحسب بالتناسب**: من عُيّن يوم 28 لا يستحق شهًرا كامًلا،
ومن انتهت خدمته يوم 5 كذلك. والمعدّل اليومي هو نفسه المستعمل في خصم
الغياب — فلا معياران للقيمة الواحدة.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app import models, payroll
from app.database import SessionLocal

CIVIL = "100000000101"


def _set(hire=None, term=None, salary=600.0):
    db = SessionLocal()
    try:
        e = db.scalar(select(models.Employee).where(
            models.Employee.civil_id == CIVIL))
        e.hire_date, e.termination_date, e.basic_salary = hire, term, salary
        db.commit()
        return e.id, e.company_id
    finally:
        db.close()


def _row(cid: int, eid: int, year: int, month: int):
    db = SessionLocal()
    try:
        res = payroll.compute_payroll(db, cid, year, month)
    finally:
        db.close()
    return next((p for p in res["payslips"] if p["employee_id"] == eid), None)


def test_nobody_is_paid_for_a_month_before_they_were_hired():
    """**جوهر العطل**: راتب 2010 لمن عُيّن 2024."""
    eid, cid = _set(hire=date(2024, 2, 28))
    assert _row(cid, eid, 2010, 5) is None, "صُرف راتب قبل التعيين بأعوام"
    assert _row(cid, eid, 2018, 7) is None
    assert _row(cid, eid, 2024, 1) is None, "صُرف راتب عن الشهر السابق للتعيين"


def test_the_month_of_hire_is_prorated():
    """ومن عُيّن يوم 28 يستحق يومين لا شهًرا."""
    eid, cid = _set(hire=date(2024, 2, 28), salary=600.0)
    row = _row(cid, eid, 2024, 2)
    assert row is not None, "غاب عن شهر تعيينه"
    assert row["employed_days"] == 2 and row["partial_month"] is True, row
    # 600/30 × 2
    assert abs(row["earned_basic"] - 40.0) < 0.01, row["earned_basic"]


def test_a_full_month_is_paid_in_full():
    """ولا يُنقَص من عمل الشهر كلّه — العلاج لا يخصم ممّن يستحق."""
    eid, cid = _set(hire=date(2024, 2, 28), salary=600.0)
    row = _row(cid, eid, 2024, 3)
    assert row is not None
    assert row["partial_month"] is False and row["earned_basic"] == 600.0, row
    assert row["gross"] == 600.0


def test_termination_ends_eligibility_and_prorates_its_month():
    """ومن انتهت خدمته: يُحسب حتى يومها، ولا يظهر بعدها."""
    eid, cid = _set(hire=date(2024, 1, 1), term=date(2024, 3, 10), salary=600.0)
    row = _row(cid, eid, 2024, 3)
    assert row is not None and row["employed_days"] == 10, row
    assert abs(row["earned_basic"] - 200.0) < 0.01, row["earned_basic"]
    assert _row(cid, eid, 2024, 4) is None, "ظهر بعد انتهاء خدمته"


def test_the_number_explains_itself_on_the_payslip():
    """ورقٌم يخالف الراتب الأساسي يحتاج تفسيره في الورقة لا في الذاكرة.

    فمن يقرأ «40» أمام راتب أساسي «600» يجب أن يجد **لماذا** بجواره.
    """
    eid, cid = _set(hire=date(2024, 2, 28), salary=600.0)
    row = _row(cid, eid, 2024, 2)
    for key in ("basic_salary", "earned_basic", "employed_days", "partial_month"):
        assert key in row, f"«{key}» غائب عن الكشف"
    assert row["basic_salary"] != row["earned_basic"], row


def test_the_existing_exclusions_still_hold():
    """**ولا يُكسر ما كان صحيًحا**: المؤرشَف ومن لا راتب له يبقيان خارج الكشف."""
    db = SessionLocal()
    try:
        e = db.scalar(select(models.Employee).where(
            models.Employee.civil_id == CIVIL))
        eid, cid = e.id, e.company_id
        e.hire_date, e.termination_date = date(2024, 1, 1), None
        e.status = "archived"
        db.commit()
    finally:
        db.close()
    assert _row(cid, eid, 2024, 3) is None, "دخل المؤرشَف الكشف"

    db = SessionLocal()
    try:
        e = db.get(models.Employee, eid)
        e.status, e.non_payroll = "active", True
        db.commit()
    finally:
        db.close()
    assert _row(cid, eid, 2024, 3) is None, "دخل من لا راتب له في هذه الشركة"

    db = SessionLocal()
    try:
        e = db.get(models.Employee, eid)
        e.non_payroll = False
        db.commit()
    finally:
        db.close()
