# -*- coding: utf-8 -*-
"""SW-040 — إتمام التجديد يمدّد تصريح إذن العمل الفعّال إلى تاريخ الإقامة الجديد ويغلق تنبيهاته."""
from datetime import date, timedelta

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.routers import renewals
from tests.conftest import plain_employee_clause, purge


def test_a_completed_renewal_extends_the_active_work_permit():
    db = SessionLocal()
    ids = {}
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            plain_employee_clause(models)))
        new_exp = date.today() + timedelta(days=365)
        wp = models.Permit(company_id=1, employee_id=emp.id, kind="work_permit", number="WP-1",
                           start_date=date.today() - timedelta(days=300),
                           expiry_date=date.today() + timedelta(days=20), status="active")
        db.add(wp); db.flush()
        alert = models.Task(company_id=1, type="renew_work_permit", title="x", status="open",
                            related_entity_type="permit", related_entity_id=wp.id)
        db.add(alert); db.flush()
        rn = models.ResidencyRenewal(company_id=1, employee_id=emp.id, permit_id=None,
                                     renewal_type="normal", status="completed", created_by=1,
                                     new_expiry_date=new_exp)
        db.add(rn); db.flush()
        ids.update(wp=wp.id, alert=alert.id, rn=rn.id)

        renewals._extend_work_permit(db, rn)
        db.flush()
        assert db.get(models.Permit, ids["wp"]).expiry_date == new_exp
        assert db.get(models.Task, ids["alert"]).status == "done"

        rn.new_expiry_date = date.today() + timedelta(days=100)   # لا يُقصَّر تصريحٌ أطول
        renewals._extend_work_permit(db, rn)
        assert db.get(models.Permit, ids["wp"]).expiry_date == new_exp
    finally:
        db.rollback()
        for table, key in (("tasks", "alert"), ("residency_renewals", "rn"), ("permits", "wp")):
            if key in ids:
                purge(db, table, [ids[key]])
        db.commit()
        db.close()
