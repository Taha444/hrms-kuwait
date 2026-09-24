# -*- coding: utf-8 -*-
"""إلغاء مسيّرٍ مجهَّز لم يُعتمَد — لا حذف (قرار المالك 2026-09-24).

لم يكن للمسيّر المجهَّز مخرجٌ إلا الاعتماد، فتجربةٌ أو شهرٌ خاطئ يبقيان في القائمة وتبقى
إشعاراتهما مفتوحةً عند المعتمدين. الإلغاء يُبقي الصفّ ``cancelled`` بسببه.
"""
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import login, purge

PERIOD = "2019-03"


def _admin(client):
    return {"Authorization": f"Bearer {login(client, '000000000000', 'admin123')}"}


def test_a_prepared_run_is_cancelled_with_a_reason_and_its_notices_close(client):
    h = _admin(client)
    r = client.post("/api/payroll/run", params={"period": PERIOD, "company_id": 1,
                                                "allow_open_attendance": True}, headers=h)
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    db = SessionLocal()
    try:
        notice = models.Task(type="payroll_ready", title="مسيّر جاهز", status="open",
                             related_entity_type="payroll_run", related_entity_id=run_id)
        db.add(notice)
        db.commit()
        nid = notice.id

        # بلا سببٍ لا يُلغى.
        assert client.post(f"/api/payroll/runs/{run_id}/cancel", params={"reason": " "},
                           headers=h).status_code == 400
        rows = client.get("/api/payroll/runs", params={"company_id": 1}, headers=h).json()
        assert next(x for x in rows if x["id"] == run_id)["can_cancel"] is True

        ok = client.post(f"/api/payroll/runs/{run_id}/cancel",
                         params={"reason": "تجربة فحص شامل"}, headers=h)
        assert ok.status_code == 200 and ok.json()["status"] == "cancelled", ok.text
        db.expire_all()
        assert db.get(models.PayrollRun, run_id).status == "cancelled", "حُذف الصفّ أو لم يُلغَ"
        assert db.get(models.Task, nid).status == "dismissed", "إشعار المعتمدين بقي مفتوحًا"
        assert db.scalar(select(models.AuditLog).where(
            models.AuditLog.action == "payroll_run_cancelled", models.AuditLog.entity_id == run_id))

        # ولا يُلغى مرتين، ولا ما بعد «مجهَّز».
        assert client.post(f"/api/payroll/runs/{run_id}/cancel", params={"reason": "x"},
                           headers=h).status_code == 409
        # ويُعاد تجهيز الفترة نفسها بعد الإلغاء.
        again = client.post("/api/payroll/run", params={"period": PERIOD, "company_id": 1,
                                                        "allow_open_attendance": True}, headers=h)
        assert again.status_code == 200 and again.json()["run_id"] == run_id, again.text
        assert db.get(models.PayrollRun, run_id) is not None
    finally:
        db.rollback()
        purge(db, "tasks", [nid])
        purge(db, "payroll_runs", [run_id])
        db.commit()
        db.close()


def test_only_the_preparer_or_the_top_admin_may_cancel(client):
    h = _admin(client)
    run_id = client.post("/api/payroll/run", params={"period": "2019-04", "company_id": 1,
                                                     "allow_open_attendance": True},
                         headers=h).json()["run_id"]
    try:
        mgr = {"Authorization": f"Bearer {login(client, '100000000001', 'manager123')}"}
        r = client.post(f"/api/payroll/runs/{run_id}/cancel", params={"reason": "x"}, headers=mgr)
        assert r.status_code in (403,), r.text      # المدير لا يملك run_payroll ولم يُجهِّزه
    finally:
        db = SessionLocal()
        try:
            purge(db, "payroll_runs", [run_id])
            db.commit()
        finally:
            db.close()


def test_the_run_list_names_a_preparer_who_has_no_company(client):
    """المحاسب متعدّد الشركات (company_id فارغ) كان يظهر «جهّزه: —» — فصل السلطات بلا أسماء."""
    h = _admin(client)          # super_admin: company_id فارغ كالمحاسب المتعدّد
    run_id = client.post("/api/payroll/run", params={"period": "2019-05", "company_id": 1,
                                                     "allow_open_attendance": True},
                         headers=h).json()["run_id"]
    try:
        rows = client.get("/api/payroll/runs", params={"company_id": 1}, headers=h).json()
        row = next(x for x in rows if x["id"] == run_id)
        assert row["prepared_by"], "اسم المجهِّز غائب"
    finally:
        db = SessionLocal()
        try:
            purge(db, "payroll_runs", [run_id])
            db.commit()
        finally:
            db.close()
