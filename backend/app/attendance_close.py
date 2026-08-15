# -*- coding: utf-8 -*-
"""ATT-07 / DLV-01 — إغلاق فترة الحضور: مصدر واحد للسؤال "هل يجوز تشغيل الرواتب؟"

ROOT CAUSE: الرواتب كانت تُشغَّل على أي شهر في أي لحظة، فتُحسب على حضور لم
يُراجَع: أيام بلا سجل، وتصحيحات معلّقة، وإجازات لم تُعتمَد. ثم يُصرف المسيّر
ويُكتشف الخطأ في راتب موظف — والتصحيح بعد الصرف أصعب من منعه بكثير.

الإغلاق ليس زًرا شكلًيا: يوثّق **من** أقرّ و**متى** و**على كم يوم غير مسجَّل**.
فبعد شهور، حين يُسأل عن راتب، يوجد جواب مكتوب لا ذاكرة.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


def get_close(db: Session, company_id: int, period: str):
    """صفّ الإغلاق الفعّال لهذه الفترة — أو لا شيء إن كانت مفتوحة."""
    row = db.scalar(select(models.AttendanceMonthClose).where(
        models.AttendanceMonthClose.company_id == company_id,
        models.AttendanceMonthClose.period == period,
    ))
    # صفّ أُعيد فتحه = فترة مفتوحة، لكن سجلّه يبقى للمراجعة.
    # الجدول القائم (AttendanceMonthClose) يعبّر عن ذلك بـstatus لا بعمود منفصل.
    if not row:
        return None
    return row if (row.status or '').lower() in ('closed', 'locked') else None


def is_closed(db: Session, company_id: int, period: str) -> bool:
    return get_close(db, company_id, period) is not None


def unrecorded_day_count(db: Session, company_id: int, period: str) -> int:
    """أيام العمل بلا سجل حضور في الفترة — الرقم الذي يُقرّ عليه المُغلِق.

    يُحسب لكل موظف نشط غير مُعفى من الحضور، ضمن مدة عمله فقط: من قبل تعيينه
    أو بعد إنهاء خدمته لا يُحسب غياًبا (QA-04).
    """
    import calendar
    from datetime import datetime

    y, m = (int(x) for x in period.split("-"))
    days_in_month = calendar.monthrange(y, m)[1]
    first, last = date(y, m, 1), date(y, m, days_in_month)

    employees = db.scalars(select(models.Employee).where(
        models.Employee.company_id == company_id,
        models.Employee.status == "active",
    )).all()

    # لا عمود date على السجل — اليوم مشتقّ من check_in_at، وهو المصدر الذي
    # يستخدمه حساب الحضور نفسه فلا ينحرف العدّان.
    start_dt = datetime.combine(first, datetime.min.time())
    end_dt = datetime.combine(last, datetime.max.time())
    recorded = {
        (r.employee_id, r.check_in_at.date())
        for r in db.scalars(select(models.AttendanceRecord).where(
            models.AttendanceRecord.company_id == company_id,
            models.AttendanceRecord.check_in_at.isnot(None),
            models.AttendanceRecord.check_in_at >= start_dt,
            models.AttendanceRecord.check_in_at <= end_dt,
        )).all()
        if r.check_in_at
    }

    total = 0
    for emp in employees:
        if getattr(emp, "attendance_exempt", False):
            continue
        start = max(first, emp.hire_date or first)
        end = min(last, emp.termination_date or last)
        d = start
        while d <= end:
            if (emp.id, d) not in recorded:
                total += 1
            d = date.fromordinal(d.toordinal() + 1)
    return total
