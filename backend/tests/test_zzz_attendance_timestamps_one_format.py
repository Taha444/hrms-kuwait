# -*- coding: utf-8 -*-
"""M23 SW-025 — سجلُّ الحضور يُرجع حقليه الزمنيين بصيغةٍ واحدة (UTC صريح)، لا أحدهما بمنطقةٍ والآخر بلا."""
from datetime import datetime, timezone

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.routers.attendance import as_utc
from tests.conftest import auth_headers, login, plain_employee_clause


def test_as_utc_normalises_naive_and_aware_moments_to_the_same_instant_and_format():
    naive = datetime(2026, 9, 24, 14, 1, 25)
    aware = datetime(2026, 9, 24, 14, 1, 25, tzinfo=timezone.utc)
    assert as_utc(naive) == aware and as_utc(aware) == aware and as_utc(None) is None
    assert as_utc(naive).isoformat().endswith("+00:00") and as_utc(aware).isoformat().endswith("+00:00")


def test_the_records_lists_never_mix_formats_inside_one_record(client):
    db = SessionLocal()
    emp = db.scalar(select(models.Employee).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        plain_employee_clause(models), models.Employee.branch_id.isnot(None)))
    bid = emp.branch_id
    rec = models.AttendanceRecord(company_id=1, employee_id=emp.id, branch_id=bid, status="present",
                                  check_in_at=datetime(2031, 5, 5, 6, 0),
                                  check_out_at=datetime(2031, 5, 5, 14, 0, tzinfo=timezone.utc))
    db.add(rec)
    db.commit()
    rid = rec.id
    db.close()
    try:
        hr = auth_headers(login(client, "100000000002", "hr12345"))
        rows = client.get(f"/api/attendance/branch/{bid}", headers=hr).json()
        mine = next(r for r in rows if r["id"] == rid)
        for k in ("check_in_at", "check_out_at"):
            assert mine[k].endswith("Z") or mine[k].endswith("+00:00"), (k, mine[k])
    finally:
        db = SessionLocal()
        db.delete(db.get(models.AttendanceRecord, rid))
        db.commit()
        db.close()
