# -*- coding: utf-8 -*-
"""المسيّر يختار بالحالة لا بمدّة الخدمة — يُحرَس ليُرى، لا ليُقَرّ.

**المقيس** (محاكاة، ``rollback``): ``compute_payroll`` يختار
``status == "active"`` وحده. وشاشةُ ملف الموظف تضبط أيًّا من
``EMP_STATUSES`` — فـ«**في إجازة**» تُسقط الموظف من المسيّر **كلّه**، والإجازةُ
السنوية مدفوعة ومسجَّلةٌ صفوفَ ``Leave`` يقرؤها المسيّرُ فلا يعدّها غيابًا.

**والشهرُ الأخير**: ``settle_case`` يكتب ``terminated`` مع
``termination_date``؛ فإن سُوِّيت الخدمةُ قبل المسيّر سقط الموظف من شهره
الأخير كلّه، ومنطقُ التناسب المكتوبُ لهذا الشهر لا يبلغه. والتسويةُ لا تحمله.

**ولا يُصلَح بلا كلمة**: أيُّ الحالات تُدفَع قرارٌ ماليٌّ وقانوني — والقاعدةُ
أن Payroll لا يُمسّ بلا اعتماد. فيُثبَّت الحالُ: من يغيّره يُسقط هذا الحارس،
فيُعلَم أن مالًا تغيّر **بقصد**. والتقريرُ في ``scripts/payroll_exclusions.py``.

**ودرسُ قياس**: المحاكاةُ الأولى قالت «الموظف المنتهية خدمته ما زال في
المسيّر» — و``SessionLocal`` بـ``autoflush=False``، فلم يبلغ التغييرُ
الاستعلام. فيُكتب ``flush`` صريحًا قبل كل قراءة.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app import models, payroll as P
from app.database import SessionLocal


def _in_run(db, emp_id: int, cid: int) -> bool:
    return any(r["employee_id"] == emp_id
               for r in P.compute_payroll(db, cid, 2026, 9)["payslips"])


def _paid_employee(db):
    return db.scalar(select(models.Employee).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        models.Employee.basic_salary.isnot(None),
        models.Employee.hire_date < date(2026, 1, 1)))


def test_a_vacation_status_drops_the_whole_month_today():
    """**قرارٌ معلَّق**: «في إجازة» تُخرج من المسيّر. فإن صارت تُدفَع سقط هذا."""
    db = SessionLocal()
    try:
        emp = _paid_employee(db)
        assert emp is not None
        assert _in_run(db, emp.id, emp.company_id), "النشطُ خارج المسيّر — تغيّر شيءٌ أعمق"
        emp.status = "vacation"
        db.flush()
        assert not _in_run(db, emp.id, emp.company_id), (
            "صار «في إجازة» يُدفَع — يُرفَع هذا الحارس ويُكتب بدله ما يقيس الأجر")
    finally:
        db.rollback()
        db.close()


def test_a_settled_employee_misses_the_final_partial_month_today():
    """والتسويةُ قبل المسيّر تُسقط الشهرَ الأخير — والتناسبُ يعمل لو بقي نشطًا."""
    db = SessionLocal()
    try:
        emp = _paid_employee(db)
        emp.termination_date = date(2026, 9, 20)
        db.flush()
        rows = [r for r in P.compute_payroll(db, emp.company_id, 2026, 9)["payslips"]
                if r["employee_id"] == emp.id]
        assert rows and rows[0]["partial_month"], "التناسبُ نفسُه لا يعمل"
        expected = round(float(emp.basic_salary) / 30 * 20, 3)
        assert abs(rows[0]["earned_basic"] - expected) < 0.01, (rows[0]["earned_basic"], expected)

        emp.status = "terminated"
        db.flush()
        assert not _in_run(db, emp.id, emp.company_id), (
            "صار الشهرُ الأخير يُدفَع بعد التسوية — يُرفَع هذا الحارس")
    finally:
        db.rollback()
        db.close()


def test_the_status_filter_is_still_the_only_gate():
    """والبوّابةُ نصٌّ واحد — فإن تغيّرت عُلم."""
    import inspect

    src = inspect.getsource(P.compute_payroll)
    assert 'models.Employee.status == "active"' in src, (
        "تغيّرت بوّابةُ الحالة في المسيّر — يُراجَع هذا البند")
