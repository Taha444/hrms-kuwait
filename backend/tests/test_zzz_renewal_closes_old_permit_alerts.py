# -*- coding: utf-8 -*-
"""M15 #12 — إتمام التجديد يغلق بلاغات انتهاء **الإقامة القديمة** (كانت تبقى مفتوحة للمندوب والموظف)."""
from datetime import date, timedelta

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.routers import renewals
from tests.conftest import plain_employee_clause, purge


def test_completing_a_renewal_closes_the_old_permits_expiry_alerts():
    db = SessionLocal()
    ids = {}
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            plain_employee_clause(models)))
        old = models.Permit(company_id=1, employee_id=emp.id, kind="residency", number="OLD-1",
                            start_date=date.today() - timedelta(days=300),
                            expiry_date=date.today() + timedelta(days=20), status="renewed")
        db.add(old); db.flush()
        rn = models.ResidencyRenewal(company_id=1, employee_id=emp.id, permit_id=old.id,
                                     renewal_type="normal", status="completed", created_by=1)
        db.add(rn); db.flush()
        alert = models.Task(company_id=1, type="renew_residency", title="x", status="open",
                            related_entity_type="permit", related_entity_id=old.id)
        other = models.Task(company_id=1, type="renew_residency", title="y", status="open",
                            related_entity_type="permit", related_entity_id=old.id + 10_000)
        db.add_all([alert, other]); db.flush()
        ids.update(old=old.id, rn=rn.id, alert=alert.id, other=other.id)

        renewals._close_renewal_tasks(db, rn)
        db.flush()
        assert db.get(models.Task, ids["alert"]).status == "done"
        assert db.get(models.Task, ids["other"]).status == "open"
    finally:
        db.rollback()
        for table, key in (("tasks", "alert"), ("tasks", "other"),
                           ("residency_renewals", "rn"), ("permits", "old")):
            if key in ids:
                purge(db, table, [ids[key]])
        db.commit()
        db.close()
