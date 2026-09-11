# -*- coding: utf-8 -*-
"""ثلاُث ساعات — وردٌية تُقاس بساعٍة غير ساعتها.

**العطل المقيس**: ``shift.start_time`` ساعٌة محلّية يكتبها موظف الشؤون
(«تبدأ الوردية السابعة»). والحضور يُسجَّل لحظًة بتوقيت UTC. ثم يُقارَن
الاثنان هكذا::

    cutoff = datetime.combine(now.date(), shift.start_time).replace(
        tzinfo=timezone.utc)          # ← 07:00 تُقرأ UTC وهي كويتية

فمن يحضر السابعة صباًحا بتوقيت الكويت لحظتُه ``04:00 UTC``، وتُقارَن
بـ«السابعة UTC» — أي **العاشرة بتوقيت الكويت**. والنتيجة خطٌأ ذو وجهين:

- **التأخير لا يُرصَد أبًدا**: من يصل التاسعة والنصف (06:30 UTC) ما زال
  قبل «السابعة UTC»، فيُسجَّل «حاضر». والمهلة كلّها منزاحٌة ثلاث ساعات
  لصالح المتأخّر.
- **والانصراف المبكر يُرصَد ظلًما**: من ينصرف الثالثة عصًرا (12:00 UTC)
  يُقارَن بنهاية وردية «الرابعة UTC»، فيُوسَم «انصراف مبكر» وقد أتمّ يومه.

**وحدُّ اليوم ينزاح معه**: ``now.date()`` تاريٌخ بتوقيت UTC، فحضوٌر بين
منتصف الليل والثالثة فجًرا بتوقيت الكويت يُنسَب إلى **اليوم السابق** —
وعليه تُبنى أيام الحضور والغياب في كشف الراتب.

و``clock.py`` موجوٌد في النظام لهذا بعينه، ويقول في شرحه: «النظام يحمل
ساعتين». وهذا الموضع ما زال يحمل الثانية.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy import select

from app import models
from app.clock import KUWAIT_TZ
from app.database import SessionLocal
from app.routers import attendance as A

EMP = ("100000000101", "emp12345")


class _Shift:
    """وردٌية بساعاٍت محلّية — كما يكتبها موظف الشؤون."""

    def __init__(self, start=time(7, 0), end=time(16, 0), grace=15):
        self.start_time, self.end_time, self.grace_minutes = start, end, grace


class _Emp:
    shift_id = 1

    def __init__(self, shift):
        self._shift = shift


class _DB:
    """قاعدٌة صغيرة تعيد الوردية — القياس على الحساب لا على التخزين."""

    def __init__(self, shift):
        self._shift = shift

    def get(self, model, _id):
        return self._shift


def _kuwait(hh: int, mm: int = 0) -> datetime:
    """لحظٌة بتوقيت الكويت، مُعبًَّرا عنها كما يسجّلها النظام (UTC)."""
    local = datetime(2035, 5, 14, hh, mm, tzinfo=KUWAIT_TZ)
    return local.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# التأخير يُرصَد
# ---------------------------------------------------------------------------

def test_arriving_on_time_is_present():
    """خطّ الأساس: من يصل في موعده حاضر."""
    shift = _Shift()
    assert A._compute_in_status(_DB(shift), _Emp(shift), _kuwait(7, 0)) == "present"


def test_arriving_within_grace_is_present():
    """ومن يصل داخل المهلة حاضر — المهلة محفوظة لا مُلغاة."""
    shift = _Shift(grace=15)
    assert A._compute_in_status(_DB(shift), _Emp(shift), _kuwait(7, 10)) == "present"


def test_arriving_late_is_actually_flagged():
    """**جوهر العطل**: من يصل التاسعة والنصف متأخٌّر — وكان «حاضًرا».

    لحظتُه ``06:30 UTC`` وهي قبل «السابعة UTC»، فالمقارنة كانت تمرّ.
    """
    shift = _Shift(grace=15)
    got = A._compute_in_status(_DB(shift), _Emp(shift), _kuwait(9, 30))
    assert got == "late", f"تأخٌّر ساعتان ونصف وسُجِّل «{got}»"


def test_arriving_just_past_the_grace_is_late():
    """وحدُّ المهلة يُقاس بالدقيقة لا بالساعة."""
    shift = _Shift(grace=15)
    assert A._compute_in_status(_DB(shift), _Emp(shift), _kuwait(7, 16)) == "late"


# ---------------------------------------------------------------------------
# والانصراف المبكر لا يُرصَد ظلًما
# ---------------------------------------------------------------------------

def _record(check_in: datetime) -> models.AttendanceRecord:
    return models.AttendanceRecord(company_id=1, employee_id=1,
                                   check_in_at=check_in, status="present")


def test_leaving_at_the_end_of_the_shift_is_not_early():
    """**والوجه الآخر**: من أتمّ يومه لا يُوسَم «انصراًفا مبكًرا».

    كان ينصرف الرابعة عصًرا (13:00 UTC) فيُقارَن بـ«الرابعة UTC» — أي
    السابعة مساًء بتوقيت الكويت — فيُوسَم مبكًرا وقد أوفى.
    """
    shift = _Shift()
    rec = _record(_kuwait(7, 0))
    A._finalize_out(_DB(shift), _Emp(shift), rec, _kuwait(16, 0))
    assert rec.status != "early_leave", rec.status


def test_leaving_genuinely_early_is_still_flagged():
    """ومن ينصرف قبل نهاية ورديته يُوسَم — الحارس لا يُلغي القاعدة."""
    shift = _Shift()
    rec = _record(_kuwait(7, 0))
    A._finalize_out(_DB(shift), _Emp(shift), rec, _kuwait(13, 0))
    assert rec.status == "early_leave", rec.status


def test_worked_minutes_are_unaffected_by_the_zone():
    """وفرُق لحظتين لا يتأثّر بالمنطقة — فلا يُمسّ ما كان صحيًحا."""
    shift = _Shift()
    rec = _record(_kuwait(7, 0))
    A._finalize_out(_DB(shift), _Emp(shift), rec, _kuwait(16, 0))
    assert rec.worked_minutes == 9 * 60, rec.worked_minutes


# ---------------------------------------------------------------------------
# وحدُّ اليوم
# ---------------------------------------------------------------------------

def test_a_shift_starting_after_midnight_belongs_to_its_own_day():
    """**وحدُّ اليوم ينزاح ثلاث ساعات.**

    حضوٌر الواحدة فجًرا بتوقيت الكويت لحظتُه ``22:00 UTC`` من **اليوم
    السابق**. فلو نُسب باليوم الميلادي للحظة لعُدّ في يوٍم غير يومه —
    وعليه تُبنى أيام الحضور والغياب في كشف الراتب.
    """
    instant = _kuwait(1, 0)                       # 2035-05-14 بتوقيت الكويت
    assert instant.date().isoformat() == "2035-05-13", "افتراض القياس"
    assert instant.astimezone(KUWAIT_TZ).date().isoformat() == "2035-05-14"


def test_the_status_is_computed_against_the_local_day():
    """ولا تُقارَن وردٌية بيوٍم غير يومها."""
    shift = _Shift(start=time(1, 0), end=time(9, 0), grace=10)
    # الواحدة وخمس دقائق فجًرا بتوقيت الكويت — داخل المهلة.
    assert A._compute_in_status(_DB(shift), _Emp(shift), _kuwait(1, 5)) == "present"


# ---------------------------------------------------------------------------
# والقاعدة في موضع واحد
# ---------------------------------------------------------------------------

def test_the_attendance_clock_comes_from_the_one_source():
    """**والنظام لا يحمل ساعتين.**

    ``clock.py`` كُتب لهذا بعينه ويقول في شرحه: «النظام يحمل ساعتين:
    واحدة تقرّر متى يُرسَل التنبيه، وأخرى تقرّر كم يوًما تبقّى». وهذا
    الموضع كان ما زال يحمل الثانية.
    """
    import inspect

    src = inspect.getsource(A._compute_in_status) + inspect.getsource(A._finalize_out)
    assert "KUWAIT_TZ" in src, "الوردية ما زالت تُقاس بتوقيت الخادم"
    assert "replace(tzinfo=timezone.utc)" not in src, \
        "ساعٌة محلّية ما زالت تُختَم UTC"


# ---------------------------------------------------------------------------
# V-G — ومن انتهت خدمته لا يبصم
# ---------------------------------------------------------------------------

def test_an_archived_employee_cannot_record_attendance(client):
    """**حضوٌر على ملٍّف انتهت خدمته.**

    الحضور كان بلا حارس حالة إطلاًقا، ولا شيء في النظام يعطّل الحساب عند
    الأرشفة. فمن أُنهيت خدمته يبقى حساُبه نشًطا فيبصم — وتُبنى عليه أياُم
    حضوٍر في كشف راتٍب لمن لم يعد على رأس العمل.

    وهو ``V-G`` بنصّه: «تأكد أن الـbackend POST نفسه يرفض — لا الواجهة
    فقط». وباٌب يُغلَق في الشاشة ويبقى مفتوًحا في المسار ليس حماية.
    """
    from tests.conftest import auth_headers, login

    db = SessionLocal()
    try:
        user = db.scalar(select(models.User).where(
            models.User.civil_id == EMP[0]))
        emp = db.get(models.Employee, user.employee_id)
        was = emp.status
        emp.status = "archived"
        db.commit()
    finally:
        db.close()

    try:
        hdr = auth_headers(login(client, *EMP))
        r = client.post("/api/attendance/validate-qr", headers=hdr,
                        json={"qr_token": "أيًّا كان", "lat": 29.3, "lng": 47.9})
        assert r.status_code == 403, (r.status_code, r.text[:200])
        assert "انتهت خدمته" in r.text, r.text[:200]
    finally:
        db = SessionLocal()
        try:
            u = db.scalar(select(models.User).where(
                models.User.civil_id == EMP[0]))
            db.get(models.Employee, u.employee_id).status = was
            db.commit()
        finally:
            db.close()


def test_an_active_employee_is_not_blocked(client):
    """والحارس لا يمنع من هو على رأس العمل — يُقاس الاتجاهان."""
    from tests.conftest import auth_headers, login

    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/attendance/validate-qr", headers=hdr,
                    json={"qr_token": "رمٌز غير صالح", "lat": 29.3, "lng": 47.9})
    # يُردّ لسبب الرمز لا لسبب الحالة — وهو المقصود.
    assert r.status_code != 403 or "انتهت خدمته" not in r.text, r.text[:200]


def test_the_status_list_is_read_from_its_one_source():
    """**وقائمتان لحالٍة واحدة تنحرف إحداهما.**

    القاعدة مستعملٌة في إنشاء الطلبات (``BLOCKED_EMPLOYEE_STATUSES``)،
    فتُقرأ من موضعها لا تُكتب ثانيًة في الحضور.
    """
    import inspect

    src = inspect.getsource(A._resolve_employee)
    assert "BLOCKED_EMPLOYEE_STATUSES" in src, "قائمٌة ثانية للحالات المحجوبة"
