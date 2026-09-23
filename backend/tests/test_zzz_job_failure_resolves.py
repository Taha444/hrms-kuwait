# -*- coding: utf-8 -*-
"""تنبيه فشل المهمة المجدولة يُقفل عند نجاح جولتها (SW-005، 2026-09-23).

قيس على الإنتاج: 62 مهمة «حرجة» ``job_failure`` بقيت مفتوحة بعد أن زال العطل بثلاثة
أيام، فدُفنت المهام الحقيقية وبدا النظام معطَّلًا وهو يعمل.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models, scheduler
from app.database import SessionLocal
from tests.conftest import purge


def _fail_task(db, job, key):
    t = models.Task(type="job_failure", title=f"فشل مهمة مجدولة: {job}", severity="critical",
                    status="open", dedup_key=key)
    db.add(t)
    db.flush()
    return t


def test_a_successful_run_closes_only_its_own_jobs_failures():
    db = SessionLocal()
    a = _fail_task(db, "sla_scan", "job_fail:sla_scan:2026-09-20:u9001")
    b = _fail_task(db, "sla_scan", "job_fail:sla_scan:2026-09-21:u9001")
    c = _fail_task(db, "digest_scan", "job_fail:digest_scan:2026-09-21:u9001")
    db.commit()
    ids = (a.id, b.id, c.id)
    try:
        assert scheduler._resolve_job_failures(db, "sla_scan") == 2
        db.expire_all()
        assert db.get(models.Task, ids[0]).status == "done"
        assert db.get(models.Task, ids[1]).status == "done"
        assert db.get(models.Task, ids[1]).completed_at is not None
        assert db.get(models.Task, ids[2]).status == "open", "أُغلق فشلُ job آخر لم ينجح"
        # وتشغيله ثانيةً لا يجد شيئًا.
        assert scheduler._resolve_job_failures(db, "sla_scan") == 0
    finally:
        purge(db, "tasks", list(ids))
        db.commit()
        db.close()
