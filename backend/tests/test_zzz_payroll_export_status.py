# -*- coding: utf-8 -*-
"""M21 #4 — تصدير المسيّر يذكر حالته؛ غير المقفل لا يُقرأ رقمًا نهائيًا."""
import csv
import io

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, purge

ACC = ("100000000007", "account123")


def _run(status):
    db = SessionLocal()
    try:
        run = models.PayrollRun(company_id=1, period="2031-05", status=status, totals_json={"payslips": [
            {"name": "م", "job_title": "", "basic_salary": 500, "present_days": 20, "absent_days": 0,
             "overtime_pay": 0, "absence_deduction": 0, "other_deductions": 0, "gross": 500, "net": 500}]})
        db.add(run)
        db.commit()
        return run.id
    finally:
        db.close()


def _drop(rid):
    db = SessionLocal()
    try:
        purge(db, "payroll_runs", [rid])
        db.commit()
    finally:
        db.close()


def _export(client, rid):
    h = auth_headers(login(client, *ACC))
    r = client.get(f"/api/reports/payroll/{rid}", headers=h, params={"fmt": "csv", "reason": "M21"})
    assert r.status_code == 200, r.text
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8").lstrip("\ufeff"))))
    return r.headers.get("content-disposition", ""), rows


def test_a_draft_run_is_labelled_and_a_locked_run_is_not_marked(client):
    draft, locked = _run("prepared"), _run("locked")
    try:
        disp, rows = _export(client, draft)
        assert "_DRAFT" in disp and rows[0][-1] == "حالة المسيّر" and "مسودة" in rows[1][-1]
        disp, rows = _export(client, locked)
        assert "_DRAFT" not in disp and "مقفل" in rows[1][-1]
    finally:
        _drop(draft)
        _drop(locked)
