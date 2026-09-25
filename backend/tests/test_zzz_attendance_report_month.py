# -*- coding: utf-8 -*-
"""M21 — تقرير الحضور الشهري يحمل شهرَه وحده، ويرفض شهرًا لا يُفهم.

قيس: ``GET /reports/attendance?month=2026-06`` يعيد سجلات يونيو **ويوليو وأغسطس وسبتمبر**
(الفلتر ``>= أول الشهر`` بلا حدٍّ أعلى)، و``month=2026-13`` يسقط ``ValueError`` (500)، و«abc»
يُستبدَل بصمت بالشهر الحالي فيصل تقريرٌ لشهرٍ لم يُطلب.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, plain_employee_clause

MGR = ("100000000001", "manager123")


def _report(client, month):
    hdr = auth_headers(login(client, *MGR))
    return client.get("/api/reports/attendance", headers=hdr,
                      params={"month": month, "fmt": "csv", "reason": "M21"})


def test_a_monthly_report_carries_only_its_own_month(client):
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            plain_employee_clause(models)).limit(1))
        recs = [models.AttendanceRecord(
            company_id=1, employee_id=emp.id, check_in_at=datetime(2026, mo, 10, 6, 0),
            check_out_at=datetime(2026, mo, 10, 14, 0), status="present", method="qr",
            worked_minutes=480) for mo in (6, 7, 8)]
        db.add_all(recs)
        db.commit()
        ids = [r.id for r in recs]
    finally:
        db.close()
    try:
        r = _report(client, "2026-06")
        assert r.status_code == 200, r.text[:150]
        rows = [l for l in r.content.decode("utf-8-sig").splitlines()[1:] if "2026-" in l]
        months = sorted({l.split(",")[1][:7] for l in rows})
        assert months == ["2026-06"], f"تقرير يونيو يحمل: {months}"
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.AttendanceRecord).where(models.AttendanceRecord.id.in_(ids)))
            db.commit()
        finally:
            db.close()


def test_an_unreadable_month_is_refused_not_substituted_or_crashed(client):
    assert _report(client, "2026-13").status_code == 400
    assert _report(client, "abc").status_code == 400
    assert _report(client, "2026-6").status_code == 400
