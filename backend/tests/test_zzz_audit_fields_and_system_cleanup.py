# -*- coding: utf-8 -*-
"""سجلّ التدقيق يعرض ما يحفظه، والتنظيف الآليّ يُسجَّل باسم النظام (M22، 2026-09-24)."""
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.notifications import daily_scan
from tests.conftest import login, purge


def test_the_audit_list_exposes_role_result_reason_before_after_and_correlation(client):
    h = {"Authorization": f"Bearer {login(client, '000000000000', 'admin123')}"}
    rows = client.get("/api/audit", params={"limit": 5}, headers=h).json()
    assert rows, "لا سجلّات"
    for k in ("actor_role", "result", "reason", "before", "after", "correlation_id",
              "user_agent", "company_id", "branch_id"):
        assert k in rows[0], f"الحقل {k} مخزَّن ولا يُعرض"


def test_the_automatic_cleanup_is_audited_as_the_system():
    db = SessionLocal()
    t = models.Task(type="request_stage", title="x", status="open", severity="info",
                    related_entity_type="request", related_entity_id=987654321, dedup_key="aud:1")
    db.add(t)
    db.commit()
    tid = t.id
    try:
        daily_scan(db)
        row = db.scalar(select(models.AuditLog).where(
            models.AuditLog.action == "task_cleanup_auto").order_by(models.AuditLog.id.desc()))
        assert row is not None and row.user_id is None, "التنظيف الآليّ بلا سجلّ باسم النظام"
        assert "orphans=" in (row.detail or ""), row.detail
    finally:
        db.rollback()
        purge(db, "tasks", [tid])
        db.commit()
        db.close()
