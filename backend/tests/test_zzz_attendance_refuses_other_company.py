# -*- coding: utf-8 -*-
"""M11 #4 — أبواب الحضور ترفض شركةً صريحة تخالف شركة الجلسة بدل أن تستبدلها صامتةً (وفي الكتابة تُنفّذ على غير المطلوب)."""
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
PERIOD = "2031-07"


def test_a_mismatched_company_is_refused_and_nothing_is_closed(client):
    hr = auth_headers(login(client, *HR))
    for method, path, params in (
            ("get", "review", {"month": "2026-08", "company_id": 2}),
            ("get", "close-status", {"period": PERIOD, "company_id": 2}),
            ("post", "close-month", {"period": PERIOD, "company_id": 2}),
            ("post", "reopen-month", {"period": PERIOD, "company_id": 2, "reason": "x"})):
        r = getattr(client, method)(f"/api/attendance/{path}", headers=hr, params=params)
        assert r.status_code == 403, (path, r.status_code, r.text[:100])
    db = SessionLocal()
    closed = db.scalar(select(models.AttendanceMonthClose).where(
        models.AttendanceMonthClose.period == PERIOD))
    db.close()
    assert closed is None, "طلبُ إقفال شركةٍ أخرى أقفل شهرَ شركة الجلسة"
    own = client.get("/api/attendance/review", headers=hr, params={"month": "2026-08", "company_id": 1})
    assert own.status_code == 200
    bare = client.get("/api/attendance/review", headers=hr, params={"month": "2026-08"})
    assert bare.status_code == 200


def test_other_write_doors_that_take_a_company_refuse_a_mismatch_too(client):
    hr = auth_headers(login(client, *HR))
    mgr = auth_headers(login(client, "100000000001", "manager123"))
    r = client.post("/api/employees/backfill-employee-no", headers=mgr, params={"company_id": 2})
    assert r.status_code == 403, (r.status_code, r.text[:100])
    r = client.put("/api/archive/company/info", headers=mgr, params={"company_id": 2, "file_number": "ZZ-1"})
    assert r.status_code == 403, (r.status_code, r.text[:100])
    # ولئلا يكون الـ403 نقصَ صلاحيةٍ لا رفضَ نطاق: الطلبُ لشركتهما نفسها يمرّ
    ok1 = client.post("/api/employees/backfill-employee-no", headers=mgr, params={"company_id": 1})
    ok2 = client.put("/api/archive/company/info", headers=mgr, params={"company_id": 1})
    assert ok1.status_code == 200 and ok2.status_code in (200, 400), (ok1.status_code, ok2.status_code, ok2.text[:80])
