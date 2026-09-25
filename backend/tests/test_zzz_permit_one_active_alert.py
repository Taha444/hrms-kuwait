# -*- coding: utf-8 -*-
"""M16 #3 — تصريحٌ واحد = تنبيهٌ نشطٌ واحد لكل مستلِم؛ الشريحة الأقرب تحلّ محلّ ما قبلها."""
from datetime import date, timedelta

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.notifications import daily_scan
from tests.conftest import plain_employee_clause, purge


def _open_alerts(db, pid):
    return db.scalars(select(models.Task).where(
        models.Task.related_entity_type == "permit", models.Task.related_entity_id == pid,
        models.Task.status.in_(("open", "in_progress")))).all()


def test_a_closer_bucket_replaces_the_earlier_alerts_of_the_same_permit():
    db = SessionLocal()
    pid = None
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            plain_employee_clause(models)))
        p = models.Permit(company_id=1, employee_id=emp.id, kind="residency", number="M16-ONE",
                          start_date=date.today() - timedelta(days=300),
                          expiry_date=date.today() + timedelta(days=80), status="active")
        db.add(p)
        db.commit()
        pid = p.id
        daily_scan(db)
        db.commit()
        first = {t.dedup_key for t in _open_alerts(db, pid)}
        assert first, "المسح لم يُنشئ تنبيهًا للشريحة الأولى"

        p.expiry_date = date.today() + timedelta(days=20)
        db.commit()
        daily_scan(db)
        db.commit()
        second = _open_alerts(db, pid)
        assert second and all(":30" in t.dedup_key for t in second), [t.dedup_key for t in second]
        assert not ({t.dedup_key for t in second} & first)

        daily_scan(db)                               # مسحٌ ثانٍ في اليوم نفسه: لا تكرار
        db.commit()
        assert len(_open_alerts(db, pid)) == len(second)
    finally:
        db.rollback()
        if pid:
            purge(db, "tasks", [t.id for t in db.scalars(select(models.Task).where(
                models.Task.related_entity_type == "permit", models.Task.related_entity_id == pid)).all()])
            purge(db, "permits", [pid])
            db.commit()
        db.close()
