# -*- coding: utf-8 -*-
"""الإضافيُّ باعتماد، والانصرافُ المنسيُّ يُغلق بقاعدته — قرار المالك (2026-09-17).

كان ``_finalize_out`` يحسب الإضافيَّ فرقَ اللحظتين بلا سقف، و``payroll``
يدفعه كلَّه. ومسارُ الانصراف يُغلق أحدثَ سجلٍّ مفتوحٍ بـ``now`` أيًّا كان
يومُه: نسيانٌ يُغلق بعد يوم = خمس عشرة ساعة إضافي مدفوعة. و
``Branch.auto_checkout_minutes`` معلَنٌ لا يقرؤه شيء.

**والقرار**:

- الإضافيُّ يُدفع بالأقلّ من المسجَّل وطلب «عمل إضافي» (REQOT) **مكتمل**
  لذلك اليوم. وما سواه يُعرض «غير معتمد» ولا يُدفع.
- السجلُّ الباقي مفتوحًا بعد يوم حضوره يُغلق عند نهاية الوردية + مهلة
  الفرع — عند الحضور التالي، وعند الانصراف، وفي المسح اليومي. ومن ينصرف
  متأخرًا في يومه يُسجَّل بساعته.

**ودرسُ قياس**: ``SessionLocal`` بـ``autoflush=False`` — ``flush`` صريح.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import select

from app import models, payroll as P
from app.clock import KUWAIT_TZ
from app.database import SessionLocal
from app.routers import attendance as A
from tests.conftest import auth_headers, login

DAY = date(2026, 9, 7)          # أحد — يوم عمل


def _k(d: date, h: int, m: int = 0) -> datetime:
    """لحظةٌ بتوقيت الكويت مخزَّنةً UTC بلا منطقة، كما يحفظها SQLite."""
    return (datetime.combine(d, time(h, m)).replace(tzinfo=KUWAIT_TZ)
            .astimezone(timezone.utc).replace(tzinfo=None))


@pytest.fixture
def world():
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            models.Employee.basic_salary.isnot(None),
            models.Employee.hire_date < date(2026, 1, 1)))
        shift = models.Shift(company_id=1, name="قياس", start_time=time(8, 0),
                             end_time=time(17, 0), work_days="0,1,2,3,4")
        branch = db.scalar(select(models.Branch).where(models.Branch.company_id == 1))
        db.add(shift)
        db.flush()
        emp.shift_id = shift.id
        emp.attendance_exempt = False
        branch.auto_checkout_minutes = 15
        db.execute(models.AttendanceRecord.__table__.delete().where(
            models.AttendanceRecord.employee_id == emp.id))
        db.flush()
        yield db, emp, branch
    finally:
        db.rollback()
        db.close()


def _record(db, emp, branch, start, end=None, overtime=0):
    rec = models.AttendanceRecord(company_id=emp.company_id, employee_id=emp.id,
                                  branch_id=branch.id, check_in_at=start,
                                  check_out_at=end, status="present",
                                  worked_minutes=0, overtime_minutes=overtime)
    db.add(rec)
    db.flush()
    return rec


def _ot_request(db, emp, hours, status="completed", d=DAY):
    req = models.Request(company_id=emp.company_id, employee_id=emp.id,
                         request_type_code="REQOT", status=status,
                         payload_json={"overtime_date": d.isoformat(), "hours": hours,
                                       "from_time": "17:00", "to_time": "20:00"})
    db.add(req)
    db.flush()
    return req


def _slip(db, emp):
    return next(r for r in P.compute_payroll(db, emp.company_id, 2026, 9)["payslips"]
                if r["employee_id"] == emp.id)


# ---------------------------------------------------------------------------
# المسيّر
# ---------------------------------------------------------------------------

def test_unapproved_overtime_is_shown_but_not_paid(world):
    db, emp, branch = world
    _record(db, emp, branch, _k(DAY, 8), _k(DAY, 20), overtime=180)
    s = _slip(db, emp)
    assert s["overtime_pay"] == 0, s["overtime_pay"]
    assert s["overtime_recorded_minutes"] == 180
    assert s["overtime_unapproved_minutes"] == 180


def test_approved_overtime_pays_the_lesser_of_recorded_and_approved(world):
    db, emp, branch = world
    _record(db, emp, branch, _k(DAY, 8), _k(DAY, 20), overtime=180)
    _ot_request(db, emp, 2)
    s = _slip(db, emp)
    assert s["overtime_minutes"] == 120
    hourly = float(emp.basic_salary) / P.PAYROLL_DAY_DIVISOR / 8
    assert s["overtime_pay"] == pytest.approx(round(hourly * P.OVERTIME_RATE * 2, 3))
    assert s["overtime_unapproved_minutes"] == 60


def test_approval_does_not_pay_hours_that_were_not_worked(world):
    db, emp, branch = world
    _record(db, emp, branch, _k(DAY, 8), _k(DAY, 18), overtime=60)
    _ot_request(db, emp, 5)
    assert _slip(db, emp)["overtime_minutes"] == 60


@pytest.mark.parametrize("status", ["pending", "rejected", "cancelled", "returned"])
def test_an_unfinished_request_approves_nothing(world, status):
    db, emp, branch = world
    _record(db, emp, branch, _k(DAY, 8), _k(DAY, 20), overtime=180)
    _ot_request(db, emp, 3, status=status)
    assert _slip(db, emp)["overtime_pay"] == 0


def test_approval_for_another_day_does_not_count(world):
    db, emp, branch = world
    _record(db, emp, branch, _k(DAY, 8), _k(DAY, 20), overtime=180)
    _ot_request(db, emp, 3, d=DAY + timedelta(days=1))
    assert _slip(db, emp)["overtime_pay"] == 0


# ---------------------------------------------------------------------------
# الانصراف المنسيّ
# ---------------------------------------------------------------------------

def test_a_forgotten_record_closes_at_shift_end_plus_grace(world):
    db, emp, branch = world
    rec = _record(db, emp, branch, _k(DAY, 8))
    now = datetime.combine(DAY + timedelta(days=1), time(9, 0)).replace(tzinfo=KUWAIT_TZ)
    assert A.close_forgotten(db, rec, now)
    closed = rec.check_out_at
    if closed.tzinfo is None:
        closed = closed.replace(tzinfo=timezone.utc)
    assert closed.astimezone(KUWAIT_TZ).time() == time(17, 15)
    assert rec.worked_minutes == 9 * 60 + 15
    assert A.AUTO_CLOSE_NOTE in (rec.notes or "")


def test_a_late_checkout_on_the_same_day_keeps_its_hour(world):
    db, emp, branch = world
    rec = _record(db, emp, branch, _k(DAY, 8))
    now = datetime.combine(DAY, time(21, 0)).replace(tzinfo=KUWAIT_TZ)
    assert A.forgotten_close_at(db, rec, now) is None


def test_the_grace_is_read_from_the_branch(world):
    db, emp, branch = world
    branch.auto_checkout_minutes = 60
    db.flush()
    rec = _record(db, emp, branch, _k(DAY, 8))
    now = datetime.combine(DAY + timedelta(days=1), time(9, 0)).replace(tzinfo=KUWAIT_TZ)
    assert A.forgotten_close_at(db, rec, now).time() == time(18, 0)


def test_a_night_shift_is_not_guessed(world):
    db, emp, branch = world
    shift = db.get(models.Shift, emp.shift_id)
    shift.start_time, shift.end_time = time(22, 0), time(6, 0)
    db.flush()
    rec = _record(db, emp, branch, _k(DAY, 22))
    now = datetime.combine(DAY + timedelta(days=2), time(9, 0)).replace(tzinfo=KUWAIT_TZ)
    assert A.forgotten_close_at(db, rec, now) is None


def test_the_daily_scan_closes_forgotten_records(world):
    db, emp, branch = world
    rec = _record(db, emp, branch, _k(DAY, 8))
    assert A.close_all_forgotten(
        db, datetime.combine(DAY + timedelta(days=1), time(1, 0)).replace(tzinfo=KUWAIT_TZ)) >= 1
    assert rec.check_out_at is not None
    import inspect

    from app import scheduler
    assert "close_all_forgotten" in inspect.getsource(scheduler._run_daily_scan)


def test_check_in_and_check_out_both_apply_the_rule():
    import inspect

    src = inspect.getsource(A.check_in)
    assert src.count("close_forgotten(") == 2, "الحضورُ أو الانصراف لا يطبّق القاعدة"


def test_the_branch_screen_can_set_the_grace(client):
    hdr = auth_headers(login(client, "100000000001", "manager123"))
    db = SessionLocal()
    try:
        bid, old = db.scalar(select(models.Branch.id).where(models.Branch.company_id == 1)), None
        old = db.get(models.Branch, bid).auto_checkout_minutes
    finally:
        db.close()
    try:
        r = client.put(f"/api/branches/{bid}", headers=hdr, json={"auto_checkout_minutes": 30})
        assert r.status_code == 200, r.text[:200]
        bad = client.put(f"/api/branches/{bid}", headers=hdr, json={"auto_checkout_minutes": -5})
        assert bad.status_code == 422
    finally:
        db = SessionLocal()
        try:
            db.get(models.Branch, bid).auto_checkout_minutes = old
            db.commit()
        finally:
            db.close()
