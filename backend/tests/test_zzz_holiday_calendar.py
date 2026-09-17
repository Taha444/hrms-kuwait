# -*- coding: utf-8 -*-
"""تقويمُ العطل الرسمية — قرار المالك (2026-09-17).

كان النظامُ بلا تقويم: يومُ العيد يوم عملٍ في الوردية. فالقياسُ قبل البناء:

- لمن لم يحضر: **«غير مسجَّل»** في شاشة المراجعة وعدّاد الإقفال (لا يُخصم —
  لكنه يُعرض على HR ويُقَرّ عليه الإقفال).
- تنبيهُ أيام الإجازة يعدّه يومَ عمل.
- والعملُ فيه يُحسب إضافيًّا بعد نهاية الوردية وحدها.

**والقرار**: تقويمٌ يُدخله HR؛ العطلةُ لا تُعدّ «غير مسجَّل» ولا يومَ إجازة،
والعملُ فيها كلُّه إضافيٌّ بنسبة ``overtime.holiday_rate`` بعد الاعتماد.

**ومعه**: عدّادُ الإقفال كان يعدّ **كلَّ يومٍ في التقويم** — عطلةَ الأسبوع
معه — بخلاف المسيّر. فصار بقاعدته.
"""
from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from sqlalchemy import delete as sa_delete, select

from app import attendance_close, models, payroll as P
from app.database import SessionLocal
from tests.conftest import auth_headers, login
from tests.test_zzz_overtime_approval import _k, _ot_request, _record, _slip, world  # noqa: F401

HOL = date(2026, 9, 8)          # اثنين — يوم عمل في الوردية
HR = ("100000000002", "hr12345")


def _holiday(db, emp, d=HOL, name="عطلة قياس"):
    h = models.Holiday(company_id=emp.company_id, date=d, name=name)
    db.add(h)
    db.flush()
    return h


def test_work_on_a_holiday_is_all_overtime_at_the_holiday_rate(world):
    db, emp, branch = world
    _holiday(db, emp)
    _record(db, emp, branch, _k(HOL, 8), _k(HOL, 12), overtime=0)
    rec = db.scalar(select(models.AttendanceRecord).where(
        models.AttendanceRecord.employee_id == emp.id))
    rec.worked_minutes = 240
    db.flush()
    assert _slip(db, emp)["overtime_pay"] == 0, "بلا اعتماد لا يُدفع — ولو في عطلة"
    _ot_request(db, emp, 4, d=HOL)
    s = _slip(db, emp)
    assert s["holiday_overtime_minutes"] == 240
    hourly = float(emp.basic_salary) / P.PAYROLL_DAY_DIVISOR / 8
    assert s["overtime_pay"] == pytest.approx(round(hourly * 1.5 * 4, 3))


def test_the_holiday_rate_comes_from_policy(world):
    db, emp, branch = world
    _holiday(db, emp)
    db.add(models.PolicyRule(company_id=emp.company_id, key="overtime.holiday_rate",
                             value_json={"rate": 2.0}, version=99, is_active=True))
    rec = _record(db, emp, branch, _k(HOL, 8), _k(HOL, 10))
    rec.worked_minutes = 120
    _ot_request(db, emp, 2, d=HOL)
    hourly = float(emp.basic_salary) / P.PAYROLL_DAY_DIVISOR / 8
    assert _slip(db, emp)["overtime_pay"] == pytest.approx(round(hourly * 2.0 * 2, 3))


def test_an_ordinary_day_keeps_the_ordinary_rate(world):
    db, emp, branch = world
    _holiday(db, emp)
    _record(db, emp, branch, _k(HOL + timedelta(days=1), 8),
            _k(HOL + timedelta(days=1), 19), overtime=120)
    _ot_request(db, emp, 2, d=HOL + timedelta(days=1))
    s = _slip(db, emp)
    hourly = float(emp.basic_salary) / P.PAYROLL_DAY_DIVISOR / 8
    assert s["holiday_overtime_minutes"] == 0
    assert s["overtime_pay"] == pytest.approx(round(hourly * P.OVERTIME_RATE * 2, 3))


def test_a_holiday_is_not_an_unrecorded_day(world):
    db, emp, branch = world
    period = HOL.strftime("%Y-%m")
    before = attendance_close.unrecorded_day_count(db, emp.company_id, period)
    _holiday(db, emp)
    after = attendance_close.unrecorded_day_count(db, emp.company_id, period)
    tracked = [e for e in db.scalars(select(models.Employee).where(
        models.Employee.company_id == emp.company_id,
        models.Employee.status == "active")).all()
        if not e.attendance_exempt and e.attendance_mode != "none"
        and (not e.hire_date or e.hire_date <= HOL)]
    assert before - after == len(tracked), (before, after, len(tracked))


def test_the_close_count_skips_the_weekend():
    """والعدّادُ بقاعدة المسيّر: شهرٌ بلا سجلّات يُعدّ بأيام الوردية لا بالتقويم.

    مارس 2031: واحدٌ وثلاثون يومًا، منها ثلاثةٌ وعشرون من الأحد إلى الخميس.
    والعدُّ القديم كان يعطي كلَّ موظفٍ واحدًا وثلاثين.
    """
    db = SessionLocal()
    try:
        tracked = [e for e in db.scalars(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active")).all()
            if not e.attendance_exempt and e.attendance_mode != "none"]
        n = attendance_close.unrecorded_day_count(db, 1, "2031-03")
        assert tracked
        assert n <= len(tracked) * 23, (n, len(tracked))
    finally:
        db.close()


def test_the_review_grid_marks_the_holiday(client):
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Holiday).where(models.Holiday.company_id == 1))
        db.commit()
    finally:
        db.close()
    hdr = auth_headers(login(client, *HR))
    try:
        r = client.post("/api/attendance/holidays", headers=hdr,
                        params={"on": "2026-09-08", "name": "عطلة قياس", "days": 2})
        assert r.status_code == 201, r.text[:200]
        assert [x["date"] for x in r.json()] == ["2026-09-08", "2026-09-09"]
        dup = client.post("/api/attendance/holidays", headers=hdr,
                          params={"on": "2026-09-09", "name": "مكرّرة"})
        assert dup.status_code == 409
        grid = client.get("/api/attendance/review", headers=hdr,
                          params={"month": "2026-09"}).json()
        assert grid["holidays"].get("2026-09-08") == "عطلة قياس"
        tracked = [e for e in grid["employees"] if not e.get("exempt")]
        assert tracked and all(e["cells"].get("2026-09-08") in ("holiday", "present", "late",
                                                                 "absent", "not_employed")
                               for e in tracked)
        assert any(e["cells"].get("2026-09-08") == "holiday" for e in tracked)
        listed = client.get("/api/attendance/holidays", headers=hdr,
                            params={"year": 2026}).json()
        assert len(listed) == 2
        rm = client.delete(f"/api/attendance/holidays/{listed[0]['id']}", headers=hdr)
        assert rm.status_code == 200
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.Holiday).where(models.Holiday.company_id == 1))
            db.commit()
        finally:
            db.close()


def test_a_closed_month_locks_its_holidays(client):
    db = SessionLocal()
    try:
        row = models.AttendanceMonthClose(company_id=1, period="2031-01", status="closed")
        db.add(row)
        db.commit()
        rid = row.id
    finally:
        db.close()
    try:
        r = client.post("/api/attendance/holidays", headers=auth_headers(login(client, *HR)),
                        params={"on": "2031-01-01", "name": "رأس السنة"})
        assert r.status_code == 409, r.text[:200]
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.AttendanceMonthClose).where(
                models.AttendanceMonthClose.id == rid))
            db.commit()
        finally:
            db.close()


def test_an_employee_cannot_edit_the_calendar(client):
    r = client.post("/api/attendance/holidays",
                    headers=auth_headers(login(client, "100000000101", "emp12345")),
                    params={"on": "2026-12-01", "name": "x"})
    assert r.status_code == 403


def test_the_leave_warning_does_not_count_a_holiday():
    from app.routers import requests as RQ

    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active"))
        emp.shift_id = None             # الوردية الافتراضية: الأحد..الخميس
        db.flush()
        req = models.Request(company_id=1, employee_id=emp.id, request_type_code="leave",
                             payload_json={"leave_type": "annual", "start_date": "2026-09-06",
                                           "end_date": "2026-09-10", "days": 4})
        code_ok = "leave" in RQ._LEAVE_CODES
        if not code_ok:
            req.request_type_code = next(iter(RQ._LEAVE_CODES))
        assert RQ._leave_days_warning(db, req) is not None     # خمسة أيام عمل، أُعلن أربعة
        _holiday(db, emp)
        assert RQ._leave_days_warning(db, req) is None         # العطلةُ ليست منها
    finally:
        db.rollback()
        db.close()
