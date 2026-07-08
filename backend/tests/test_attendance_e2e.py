# -*- coding: utf-8 -*-
"""دورة الحضور الكاملة (FIX-015): تسجيل → تصحيح (HR) → انعكاسها في التقرير."""
from datetime import datetime, timezone

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login


def _make_record():
    db = SessionLocal()
    emp = db.query(models.Employee).filter_by(civil_id="100000000101").first()
    rec = models.AttendanceRecord(
        company_id=emp.company_id, employee_id=emp.id, branch_id=emp.branch_id,
        check_in_at=datetime(2026, 6, 1, 9, 30, tzinfo=timezone.utc),
        check_out_at=datetime(2026, 6, 1, 17, 0, tzinfo=timezone.utc),
        method="manual", status="late", worked_minutes=450,
    )
    db.add(rec)
    db.commit()
    rid, eid = rec.id, emp.id
    db.close()
    return rid, eid


def test_hr_corrects_record_and_report_reflects_it(client):
    rid, _ = _make_record()
    hr = auth_headers(login(client, "100000000002", "hr12345"))

    # بدون سبب → 400
    r = client.put(f"/api/attendance/{rid}/correct", headers=hr,
                   params={"status": "present"})
    assert r.status_code in (400, 422)

    r = client.put(f"/api/attendance/{rid}/correct", headers=hr,
                   params={"reason": "خطأ في تسجيل ماكينة البصمة", "status": "present"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "present"

    # ينعكس في تقرير الحضور المصدَّر (export_reports صلاحية منفصلة عن manage_attendance)
    mgr = auth_headers(login(client, "100000000001", "manager123"))
    export = client.get("/api/reports/attendance", headers=mgr,
                        params={"month": "2026-06", "fmt": "csv"})
    assert export.status_code == 200
    assert "present".encode() in export.content or "present" in export.text

    # سُجِّل التصحيح في سجل التدقيق
    admin = auth_headers(login(client, "000000000000", "admin123"))
    logs = client.get("/api/audit", headers=admin,
                      params={"company_id": 1, "action": "correct_attendance"}).json()
    assert len(logs) >= 1


def test_branch_supervisor_cannot_correct_attendance(client):
    rid, _ = _make_record()
    sup = auth_headers(login(client, "100000000005", "sup12345"))
    r = client.put(f"/api/attendance/{rid}/correct", headers=sup,
                   params={"reason": "test", "status": "present"})
    assert r.status_code == 403
