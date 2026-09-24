# -*- coding: utf-8 -*-
"""M11 — تصحيح سجلّ الحضور له حدود كانت مفتوحة (والحضور أساس الرواتب).

قيس (200 لكلٍّ) على ``PUT /attendance/{id}/correct``: حالة نصّية حرّة، انصرافٌ قبل الحضور،
نقل سجلٍّ إلى شهرٍ مقفل (فيُلتفّ على القفل)، وتصحيح HR لسجلّه هو ولسجلّ مدير الشركة.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete as sa_delete, inspect, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
T0 = datetime(2026, 7, 5, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
def world():
    db = SessionLocal()
    hr_u = db.scalar(select(models.User).where(models.User.civil_id == HR[0]))
    mgr_u = db.scalar(select(models.User).where(models.User.civil_id == "100000000001"))
    plain = db.scalar(select(models.Employee).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        ~models.Employee.id.in_([hr_u.employee_id, mgr_u.employee_id])).limit(1))

    def mk(eid):
        return models.AttendanceRecord(company_id=1, employee_id=eid, check_in_at=T0,
                                       check_out_at=T0 + timedelta(hours=8),
                                       status="present", method="qr")
    recs = {"plain": mk(plain.id), "self": mk(hr_u.employee_id), "mgr": mk(mgr_u.employee_id)}
    db.add_all(recs.values())
    db.flush()
    cols = {c.key for c in inspect(models.AttendanceMonthClose).mapper.column_attrs}
    kw = dict(company_id=1, period="2026-06", status="closed")
    if "closed_by" in cols:
        kw["closed_by"] = hr_u.id
    close = models.AttendanceMonthClose(**kw)
    db.add(close)
    db.commit()
    ids = {k: v.id for k, v in recs.items()}
    close_id = close.id
    db.close()
    yield ids
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.AttendanceRecord).where(
            models.AttendanceRecord.id.in_(list(ids.values()))))
        db.execute(sa_delete(models.AttendanceMonthClose).where(
            models.AttendanceMonthClose.id == close_id))
        db.commit()
    finally:
        db.close()


def _put(client, rid, **params):
    hr = auth_headers(login(client, *HR))
    return client.put(f"/api/attendance/{rid}/correct", headers=hr,
                      params={"reason": "M11", **params})


def test_status_must_be_a_known_record_status(client, world):
    assert _put(client, world["plain"], status="zzz-hacked").status_code == 400


def test_checkout_cannot_precede_checkin(client, world):
    assert _put(client, world["plain"], check_out_at="2026-07-05T01:00:00").status_code == 400


def test_a_record_cannot_be_moved_into_a_closed_month(client, world):
    r = _put(client, world["plain"], check_in_at="2026-06-10T06:00:00",
             check_out_at="2026-06-10T14:00:00")
    assert r.status_code == 409, f"التفّ التصحيح على قفل الشهر: {r.status_code}"


def test_hr_cannot_correct_her_own_or_the_managers_record(client, world):
    assert _put(client, world["self"], status="present").status_code == 403
    assert _put(client, world["mgr"], status="present").status_code == 403


def test_a_normal_correction_still_works(client, world):
    r = _put(client, world["plain"], status="late", check_out_at="2026-07-05T15:00:00")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "late"
