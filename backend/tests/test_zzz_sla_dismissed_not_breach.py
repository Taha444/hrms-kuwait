# -*- coding: utf-8 -*-
"""SW-012 — مهمةٌ مسحوبة (dismissed) لا تُحسب خرقًا لـSLA.

تنظيف المهام اليتيمة يُقفلها بحالة ``dismissed`` وبوقت التنظيف. وتقرير سير العمل كان يحسب
``completed_at > sla_due_at`` خرقًا، فيقول 100% خرق في فترةٍ بلا طلب واحد على الإنتاج.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete as sa_delete

from app import models, workflow_metrics
from app.database import SessionLocal


def _sla(db):
    return workflow_metrics.workflow_operations(db, 1)["sla"]


def test_dismissed_tasks_are_outside_the_sla_measure():
    db = SessionLocal()
    ids = []
    try:
        base = _sla(db)
        due = datetime.now() - timedelta(days=2)
        dismissed = models.Task(company_id=1, type="request_stage", title="M-SLA dismissed",
                                status="dismissed", sla_due_at=due,
                                completed_at=datetime.now())
        db.add(dismissed)
        db.commit()
        ids.append(dismissed.id)
        after_dismissed = _sla(db)
        assert after_dismissed["tasks_with_sla"] == base["tasks_with_sla"], "المسحوبة دخلت القياس"
        assert after_dismissed["breached"] == base["breached"], "المسحوبة حُسبت خرقًا"

        overdue = models.Task(company_id=1, type="request_stage", title="M-SLA overdue",
                              status="open", sla_due_at=due)
        db.add(overdue)
        db.commit()
        ids.append(overdue.id)
        after_open = _sla(db)
        assert after_open["tasks_with_sla"] == base["tasks_with_sla"] + 1
        assert after_open["breached"] == base["breached"] + 1, "المهملة المفتوحة لا تُحسب خرقًا"
    finally:
        db.execute(sa_delete(models.Task).where(models.Task.id.in_(ids)))
        db.commit()
        db.close()
