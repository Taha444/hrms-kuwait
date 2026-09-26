# -*- coding: utf-8 -*-
"""M11 #9 — أثرُ طلب تصحيح الحضور المعتمَد يطابق باب التصحيح المباشر: توقيتُ الكويت، القفل، الترتيب، إعادة الاحتساب."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app import models, workflow
from app.database import SessionLocal
from tests.conftest import plain_employee_clause, purge

DAY = date(2031, 6, 10)


def _setup(db):
    emp = db.scalar(select(models.Employee).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        plain_employee_clause(models),
        # فهرسٌ فريد يمنع سجلَّين مفتوحَين لموظف — فموظفٌ بلا أيّ سجلٍّ يُغني عن تلوّث اختباراتٍ أخرى
        ~models.Employee.id.in_(select(models.AttendanceRecord.employee_id))))
    assert emp is not None, "لا موظف بلا سجلّ حضور لهذا القياس"
    rec = models.AttendanceRecord(
        company_id=1, employee_id=emp.id, status="absent",
        check_in_at=datetime(2031, 6, 10, 6, 0), check_out_at=None)
    db.add(rec)
    db.flush()
    return emp, rec


def _req(emp, payload):
    return models.Request(company_id=1, employee_id=emp.id, request_type_code="REQATT",
                          status="in_execution", payload_json=payload)


def test_a_corrected_time_is_kuwait_time_and_an_absent_day_becomes_present():
    db = SessionLocal()
    try:
        emp, rec = _setup(db)
        ok, note = workflow._apply_attendance_correction(db, _req(emp, {
            "date": str(DAY), "check_in": "08:00", "check_out": "16:00"}))
        assert ok, note
        assert rec.check_in_at.replace(tzinfo=None) == datetime(2031, 6, 10, 5, 0), rec.check_in_at
        assert rec.check_out_at.replace(tzinfo=None) == datetime(2031, 6, 10, 13, 0), rec.check_out_at
        assert rec.status != "absent" and rec.worked_minutes == 8 * 60, (rec.status, rec.worked_minutes)
    finally:
        db.rollback()
        db.close()


def test_a_reversed_pair_and_a_closed_month_are_refused():
    db = SessionLocal()
    cid = None
    try:
        emp, rec = _setup(db)
        ok, note = workflow._apply_attendance_correction(db, _req(emp, {
            "date": str(DAY), "check_in": "16:00", "check_out": "08:00"}))
        assert not ok and "بعد وقت الحضور" in note, note
        c = models.AttendanceMonthClose(company_id=1, period="2031-06", status="closed", closed_by=1)
        db.add(c)
        db.flush()
        cid = c.id
        ok, note = workflow._apply_attendance_correction(db, _req(emp, {
            "date": str(DAY), "check_in": "08:00", "check_out": "16:00"}))
        assert not ok and "مُقفل" in note, note
    finally:
        db.rollback()
        db.close()
