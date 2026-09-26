# -*- coding: utf-8 -*-
"""M22 #2 — ما لم يشمله قرارُ الاستثناءات القائم يُدقَّق: تشغيلُ المسوحات يدويًا (تعمل على كل الشركات) وحسبةُ نهاية الخدمة للموظف.

قائمةُ ``test_zzz_audit_coverage._DELIBERATELY_UNAUDITED`` قرارٌ معلَّل (نقراتُ الصندوق، ``GovLog``…) ولا يُمسّ. وهذه مواضعُ لم تكن فيها:
- المسحُ اليدويّ يعمل على **كل** الشركات بصلاحيةٍ بمستوى الشركة — فمن شغّله يُقيَّد.
- حسبةُ المكافأة تكشف قيمًا مشتقّة من راتب موظفٍ بعينه — من حسبها ولمن.
"""
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login


def _actions(*names):
    db = SessionLocal()
    try:
        return {a.action for a in db.scalars(select(models.AuditLog).where(
            models.AuditLog.action.in_(names))).all()}
    finally:
        db.close()


def test_manual_scans_record_who_ran_them(client):
    mgr = auth_headers(login(client, "100000000001", "manager123"))
    for path in ("run-sla-scan", "run-digest"):
        r = client.post(f"/api/tasks/{path}", headers=mgr)
        assert r.status_code == 200, (path, r.status_code, r.text[:100])
    seen = _actions("run_sla_scan_manual", "run_digest_manual")
    assert seen == {"run_sla_scan_manual", "run_digest_manual"}, seen


def test_an_eos_calculation_for_an_employee_leaves_a_trace(client):
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    db = SessionLocal()
    emp = db.scalar(select(models.Employee).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        models.Employee.hire_date.isnot(None), models.Employee.basic_salary > 0))
    eid = emp.id
    db.close()
    r = client.post("/api/eos/for-employee", headers=hr, json={
        "employee_id": eid, "end_date": "2031-01-01", "reason": "termination", "used_leave_days": 0})
    assert r.status_code == 200, r.text[:100]
    assert "eos_calculation_previewed" in _actions("eos_calculation_previewed")
