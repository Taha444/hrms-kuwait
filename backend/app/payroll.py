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

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from . import models
from .holidays import holiday_dates, holiday_rate
from .clock import today as kuwait_today

PAYROLL_DAY_DIVISOR = 30
OVERTIME_RATE = 1.25


#: رموزُ طلب العمل الإضافي (الحالي والقديم).
OVERTIME_REQUEST_CODES = ("REQOT", "overtime")


def _kuwait_date(moment):
    from datetime import timezone as _tz

    from .clock import KUWAIT_TZ
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_tz.utc)
    return moment.astimezone(KUWAIT_TZ).date()


def approved_overtime_minutes(db, employee_id: int, start, end) -> dict:
    """دقائقُ الإضافي المعتمَدة لكل يوم في ``[start, end)`` — من طلباتٍ مكتملة."""
    out: dict = {}
    for req in db.scalars(select(models.Request).where(
            models.Request.employee_id == employee_id,
            models.Request.request_type_code.in_(OVERTIME_REQUEST_CODES),
            models.Request.status == "completed")).all():
        p = req.payload_json or {}
        try:
            d = date.fromisoformat(str(p.get("overtime_date"))[:10])
            minutes = int(round(float(p.get("hours") or 0) * 60))
        except (TypeError, ValueError):
            continue
        if start <= d < end and minutes > 0:
            out[d] = out.get(d, 0) + minutes
    return out


def compute_payroll(db: Session, company_id: int, year: int, month: int) -> dict:
    """يحسب مسيّر رواتب الشركة لشهر معيّن ويُرجع قسائم الموظفين والإجماليات."""
    days_in_month = calendar.monthrange(year, month)[1]
    first = datetime(year, month, 1)
    nxt = datetime(year, month, days_in_month) + timedelta(days=1)

    # QA-18 — سجلات الوصول/الصلاحية ليست وظائف على الكشف: المندوب الذي يخدم
    # شركتين له سجل في كل منهما وراتب في واحدة، فكان يدخل كشف الثانية براتب صفر.
    # **قراران للمالك (2026-09-17)** — وكان المسيّر يختار ``status == "active"``
    # وحده:
    #
    # 1. **«في إجازة» و«موقوف» يُدفعان** (``PAYABLE_STATUSES``): الخدمةُ قائمة،
    #    والحالةُ من شاشة الملف كانت تُسقط راتبَ الشهر كلّه.
    # 2. **ومن انتهت خدمته يبقى في مسيّر شهر إنهائه** حتى تاريخ الإنهاء:
    #    ``settle_case`` يكتب ``terminated`` مع ``termination_date``، فإن سُوِّيت
    #    الخدمةُ قبل المسيّر سقط الموظف من شهره الأخير كلّه — ومنطقُ التناسب
    #    أدناه كُتب لهذا الشهر بعينه ولم يكن يبلغه. ويبقى شرطُ التداخل
    #    (``termination_date < p_start``) مانعًا لما بعده. ومن انتهت خدمته بلا
    #    تاريخٍ مُسجَّل لا يُتناسَب له فلا يُدرَج.
    from .deps import INACTIVE_EMPLOYMENT, PAYABLE_STATUSES

    employees = db.scalars(select(models.Employee).where(
        models.Employee.company_id == company_id,
        models.Employee.status.in_(PAYABLE_STATUSES + INACTIVE_EMPLOYMENT),
        or_(models.Employee.non_payroll.is_(False),
            models.Employee.non_payroll.is_(None)))).all()
    employees = [e for e in employees
                 if e.status in PAYABLE_STATUSES or e.termination_date is not None]

    # **الأهلية تُقاس بمدة التوظيف لا بالحالة وحدها.**
    #
    # كانت التصفية على الشركة والحالة فقط، فيدخل الموظف كشف **أي** شهر
    # بكامل راتبه — بما فيه شهور تسبق تعيينه بسنوات. قِيس فعًلا: مسيّر
    # 2010 و2018 و2026 يعطي الأسماء نفسها والإجمالي نفسه.
    #
    # والشرط تداخل بسيط: من بدأ بعد نهاية الفترة، أو انتهت خدمته قبل
    # بدايتها، لم يعمل فيها يوًما.
    p_start = date(year, month, 1)
    p_end = date(year, month, days_in_month)
    employees = [e for e in employees
                 if not (e.hire_date and e.hire_date > p_end)
                 and not (e.termination_date and e.termination_date < p_start)]

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
        # قرار المالك (2026-09-17) — الإضافيُّ لا يُدفع إلا معتمَدًا: طلبُ
        # «عمل إضافي» (REQOT) مكتملٌ لذلك اليوم، وبالأقلّ من المسجَّل والمعتمَد
        # (قالبُ الطلب نفسه: «لا تحتسب الساعات إلا بعد التحقق من الحضور»).
        # والعطلةُ الرسمية (قرار المالك نفسه): العملُ فيها كلُّه إضافيٌّ بنسبة
        # ``overtime.holiday_rate`` — ومعلَّقٌ على الاعتماد كغيره.
        holidays = holiday_dates(db, company_id, date(year, month, 1),
                                 date(year, month, days_in_month))
        recorded_by_day: dict = {}
        for r in recs:
            if not r.check_in_at or (r.status or "").lower() == "absent":
                continue
            d = _kuwait_date(r.check_in_at)
            m = int(r.worked_minutes or 0) if d in holidays else int(r.overtime_minutes or 0)
            if m:
                recorded_by_day[d] = recorded_by_day.get(d, 0) + m
        approved_by_day = approved_overtime_minutes(db, e.id, first.date(), nxt.date())
        overtime_recorded_minutes = sum(recorded_by_day.values())
        paid_by_day = {d: min(m, approved_by_day.get(d, 0))
                       for d, m in recorded_by_day.items()}
        overtime_minutes = sum(paid_by_day.values())
        holiday_minutes = sum(m for d, m in paid_by_day.items() if d in holidays)

        # QA-03/QA-04 — أيام العمل بلا سجل حضور.
        #
        # ROOT CAUSE: كانت الحلقة تعدّ كل يوم عمل بلا سجل "غيابًا" وتخصمه. أمران
        # غلط في ذلك:
        #  1) غياب السجل ليس غيابًا (QA-03). قد يكون الجهاز معطًلا أو الموظف في
        #     مهمة أو النظام لم يكن مُفعًَّلا بعد. الخصم على شيء لم يُثبَت عقوبة
        #     بلا واقعة. صارت حالة ثالثة: unrecorded_days تُعرَض لـHR ولا تُخصم.
        #  2) الفترة لم تكن مقصوصة على مدة التوظيف (QA-04)، فأيام ما قبل التعيين
        #     تُحسب غيابًا — موظف عُيّن في 05/08 يُخصم منه أول أربعة أيام الشهر.
        #
        # الغياب المخصوم = ما سُجّل صراحة كغياب في سجل الحضور. أي يوم بلا سجل
        # يبقى "غير مسجَّل" حتى يقرر HR فيه.
        unrecorded_days = 0
        absent_days = 0
        # الموظف المُعفى من الحضور لا يُحسب عليه شيء أصًلا
        if e.attendance_mode != "none" and not e.attendance_exempt:
            shift = db.get(models.Shift, e.shift_id) if e.shift_id else None
            workset = set((shift.work_days if shift else "0,1,2,3,4").split(","))
            leaves = db.scalars(select(models.Leave).where(
                models.Leave.employee_id == e.id, models.Leave.status == "approved")).all()
            # غياب مُثبَت في سجل الحضور (status='absent') — هذا وحده يُخصم
            absent_dates = {r.check_in_at.date() for r in recs
                            if (r.status or "").lower() == "absent"}
            # سجل الغياب يحمل check_in_at أيًضا، فلولا استثناؤه هنا لعُدّ اليوم
            # حضوًرا وسقط قبل أن يُفحص
            present_dates = {r.check_in_at.date() for r in recs
                             if (r.status or "").lower() != "absent"}
            today = kuwait_today()
            # QA-04 — قصّ الفترة على مدة التوظيف الفعلية:
            #   [hire_date, termination_date ?? اليوم]
            period_start = date(year, month, 1)
            period_end = min(date(year, month, days_in_month), today)
            if e.hire_date:
                period_start = max(period_start, e.hire_date)
            if e.termination_date:
                period_end = min(period_end, e.termination_date)

            day = period_start
            while day <= period_end:
                if str((day.weekday() + 1) % 7) in workset \
                        and day not in holidays \
                        and day not in present_dates \
                        and not any(lv.start_date <= day <= lv.end_date for lv in leaves):
                    if day in absent_dates:
                        absent_days += 1
                    else:
                        unrecorded_days += 1
                day += timedelta(days=1)

        deductions = db.scalars(select(models.Deduction).where(
            models.Deduction.employee_id == e.id,
            models.Deduction.date >= first.date(),
            models.Deduction.date < nxt.date())).all()
        other_deductions = sum(float(x.amount or 0) for x in deductions)

        overtime_pay = round(
            hourly * OVERTIME_RATE * ((overtime_minutes - holiday_minutes) / 60)
            + hourly * (holiday_rate(db, company_id) if holiday_minutes else 0)
            * (holiday_minutes / 60), 3)
        absence_deduction = round(daily * absent_days, 3)

        # **والشهر الجزئي يُحسب بالتناسب**: من عُيّن يوم 28 لا يستحق راتب
        # شهر كامل، ومن انتهت خدمته يوم 5 كذلك. المعدّل اليومي هو نفسه
        # المستعمل في خصم الغياب (basic/30) — فلا معياران للقيمة نفسها.
        emp_from = max(p_start, e.hire_date) if e.hire_date else p_start
        emp_to = min(p_end, e.termination_date) if e.termination_date else p_end
        employed_days = (emp_to - emp_from).days + 1
        partial = employed_days < days_in_month
        earned_basic = (round(daily * employed_days, 3) if partial else basic)

        # **والبدلات مكوٌَّن ثالث في الأجر.**
        #
        # كان ``gross`` أساسًيا وإضافًيا فقط، فبدٌل يُعتمد بمرحلتين لا
        # يُصرَف منه فلس. والصفوف تُقرأ بسريانها لا بتاريخ إنشائها: بدٌل
        # لمرٍّة واحدة يُصرَف في شهره، والمتكرّر في كل شهر يقع داخل مدّته.
        #
        # **ولا يمسّ هذا أساًسا قانونًيا**: نهايُة الخدمة تُحسب من
        # ``basic_salary`` وأجُر الإضافي من ``basic/divisor`` — كلاهما على
        # الأساسي لا على الإجمالي. وهل ينبغي أن تدخلهما البدلات سؤاٌل
        # قانوني قائٌم قبل هذا العمل ولم يُحدِثه.
        allowance_rows = db.scalars(select(models.Allowance).where(
            models.Allowance.employee_id == e.id,
            models.Allowance.effective_from < nxt.date(),
            or_(models.Allowance.effective_to.is_(None),
                  models.Allowance.effective_to >= first.date()),
        )).all()
        allowances = 0.0
        for a in allowance_rows:
            if a.is_recurring:
                allowances += float(a.amount or 0)
            elif first.date() <= a.effective_from < nxt.date():
                allowances += float(a.amount or 0)
        allowances = round(allowances, 3)

        gross = round(earned_basic + overtime_pay + allowances, 3)
        total_ded = round(absence_deduction + other_deductions, 3)
        net = round(gross - total_ded, 3)

        payslips.append({
            "employee_id": e.id,
            # **الرقم الوظيفي لا معرّف القاعدة.**
            #
            # ``employee_id`` رقم داخلي يتغيّر بين البيئات ولا يعرفه أحد
            # خارج القاعدة. والورقة التي يقرأها الموظف أو المدقّق تُنسَب
            # برقمه الوظيفي. ويبقى الأول للربط البرمجي لا للعرض.
            "employee_no": e.employee_no,
            "name": e.name, "job_title": e.job_title,
            "basic_salary": round(basic, 3),
            # الراتب المستحق وعدد أيام التوظيف في الفترة: رقٌم يخالف
            # الراتب الأساسي يحتاج تفسيًرا في الورقة نفسها لا في الذاكرة.
            "earned_basic": round(earned_basic, 3),
            "employed_days": employed_days,
            "partial_month": partial,
            "present_days": present_days,
            "absent_days": absent_days, "overtime_minutes": overtime_minutes,
            "overtime_recorded_minutes": overtime_recorded_minutes,
            "overtime_unapproved_minutes": overtime_recorded_minutes - overtime_minutes,
            "holiday_overtime_minutes": holiday_minutes,
            # QA-03 — أيام عمل بلا سجل حضور: تُعرَض لـHR ولا تُخصم. وجودها بعدد
            # كبير يعني خلًلا في التسجيل يستحق مراجعة، لا خصًما من الراتب.
            "unrecorded_days": unrecorded_days,
            "overtime_pay": overtime_pay, "allowances": allowances,
            "absence_deduction": absence_deduction,
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
