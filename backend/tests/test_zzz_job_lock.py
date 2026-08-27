# -*- coding: utf-8 -*-
"""AWS-02 — المهمة المجدولة تعمل مرة واحدة مهما تعدّدت النسخ.

المجدول يعمل داخل التطبيق، فمع أكثر من instance يعمل على كل واحدة:
تنبيهات ومهامّ مكرّرة، وإشعارات مضاعفة. والاختبارات هنا تحاكي الحالات
الثلاث التي يطلبها الكيت: تشغيل مرتين، وتشغيل متزامن على نسختين، وسقوط
نسخة أثناء التنفيذ.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app import models
from app.clock import now as kuwait_now
from app.database import SessionLocal
from app.job_lock import STALE_AFTER, daily_key, hourly_key, purge_old, run_once

JOB = "test_job"


@pytest.fixture(autouse=True)
def _clean():
    db = SessionLocal()
    try:
        db.query(models.JobRun).filter(models.JobRun.job.like("test_%")).delete()
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        db.query(models.JobRun).filter(models.JobRun.job.like("test_%")).delete()
        db.commit()
    finally:
        db.close()


def _attempt(job: str, key: str, work: list) -> bool:
    """جولة واحدة كما تجري في نسخة واحدة. يعيد هل نُفِّذت."""
    db = SessionLocal()
    try:
        with run_once(db, job, key) as granted:
            if not granted:
                return False
            work.append(1)
            return True
    finally:
        db.close()


def test_running_twice_executes_once():
    """تشغيل يدويّ مرتين — لا تكرار."""
    work: list = []
    assert _attempt(JOB, "2026-08-27", work) is True
    assert _attempt(JOB, "2026-08-27", work) is False
    assert len(work) == 1, f"نُفِّذت {len(work)} مرة بدل مرة واحدة"


def test_two_instances_same_round_execute_once():
    """نسختان على الجولة نفسها — واحدة تعمل والأخرى تتخطّى.

    كل نسخة بجلستها الخاصة كما هي في الواقع: النسختان لا تتشاركان ذاكرة،
    والقاعدة وحدها هي ما يتشاركانه — ولهذا القفل فيها.
    """
    work: list = []
    a = SessionLocal()
    b = SessionLocal()
    try:
        with run_once(a, JOB, "round-1") as ga:
            with run_once(b, JOB, "round-1") as gb:
                assert not (ga and gb), "النسختان نفّذتا الجولة نفسها"
                if ga:
                    work.append("a")
                if gb:
                    work.append("b")
        assert len(work) == 1
    finally:
        a.close()
        b.close()


def test_different_rounds_both_execute():
    """القفل يمنع التكرار لا التنفيذ: جولة اليوم وجولة الغد كلتاهما تعمل."""
    work: list = []
    assert _attempt(JOB, "2026-08-27", work) is True
    assert _attempt(JOB, "2026-08-28", work) is True
    assert len(work) == 2


def test_crashed_instance_does_not_block_forever():
    """نسخة سقطت أثناء التنفيذ تترك صًفا «يعمل» — لا يجوز أن يوقف المهمة أبًدا.

    التوقّف الصامت أسوأ من التكرار: تنتهي إقامات بلا تنبيه لأن المُنبِّه
    نفسه متعطّل، ولا أحد يلاحظ لأن كل شيء يبدو هادًئا.
    """
    db = SessionLocal()
    try:
        stale = (kuwait_now().replace(tzinfo=None) - STALE_AFTER - timedelta(minutes=5))
        db.add(models.JobRun(job=JOB, run_key="stuck", status="running",
                             started_at=stale, holder="نسخة-سقطت"))
        db.commit()
    finally:
        db.close()

    work: list = []
    assert _attempt(JOB, "stuck", work) is True, "الجولة العالقة أوقفت المهمة"
    assert len(work) == 1

    db = SessionLocal()
    try:
        row = db.get(models.JobRun, (JOB, "stuck"))
        assert row.status == "done"
        assert row.recovered == 1, "الاسترداد لم يُسجَّل — تكراره علامة عطل"
    finally:
        db.close()


def test_fresh_running_row_is_respected():
    """صفّ «يعمل» حديث يعني نسخة تعمل الآن — لا يُؤخذ منها."""
    db = SessionLocal()
    try:
        db.add(models.JobRun(job=JOB, run_key="active", status="running",
                             started_at=kuwait_now().replace(tzinfo=None),
                             holder="نسخة-تعمل"))
        db.commit()
    finally:
        db.close()
    work: list = []
    assert _attempt(JOB, "active", work) is False, "قُطع القفل على نسخة تعمل"
    assert not work


def test_failure_is_recorded_not_erased():
    """الفشل يُترك مرئيًّا: حذف الصفّ يعني إعادة تنفيذ صامتة في الجولة التالية."""
    db = SessionLocal()
    try:
        with pytest.raises(RuntimeError):
            with run_once(db, JOB, "boom") as granted:
                assert granted
                raise RuntimeError("عطل مفتعل")
    finally:
        db.close()

    db = SessionLocal()
    try:
        row = db.get(models.JobRun, (JOB, "boom"))
        assert row is not None, "صفّ الجولة الفاشلة حُذف — الفشل يجب أن يُرى"
        assert row.status == "failed"
    finally:
        db.close()


def test_keys_separate_rounds_correctly():
    """المفتاح هو الجولة: اليوم للمهمة اليومية، واليوم+الساعة للساعية."""
    assert daily_key("x") == kuwait_now().date().isoformat()
    assert hourly_key("x").startswith(kuwait_now().date().isoformat() + "T")
    assert len(hourly_key("x")) == len(kuwait_now().date().isoformat()) + 3


def test_old_rows_are_purged():
    """سجلّ الجولات دليل تنفيذ لا أرشيف دائم."""
    db = SessionLocal()
    try:
        old = kuwait_now().replace(tzinfo=None) - timedelta(days=400)
        db.add(models.JobRun(job=JOB, run_key="ancient", status="done", started_at=old))
        db.commit()
        purge_old(db)
        assert db.get(models.JobRun, (JOB, "ancient")) is None
    finally:
        db.close()


def test_scheduler_jobs_all_go_through_the_lock():
    """الحارس: مهمة مجدولة جديدة بلا قفل تعيد العيب كاملًا."""
    import re
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "app" / "scheduler.py").read_text(
        encoding="utf-8")
    runners = re.findall(r"^def (_run_\w+)\(\):(.*?)(?=^def |\Z)", src, re.S | re.M)
    assert runners, "لم يُعثر على مهام مجدولة — تغيّرت بنية الملف"
    for name, body in runners:
        assert "run_once(" in body, (
            f"{name} لا يمرّ بقفل الجولة — سيعمل مرة على كل instance"
        )
