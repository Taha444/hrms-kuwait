# -*- coding: utf-8 -*-
"""TSK-06 — تذكير واحد لكل حدث، يُحدَّث ولا يُضاف.

**العطل**: حارس التكرار كان يفحص المفتاح «``sla_escalation:{id}``»
مجرًَّدا، بينما ``notify_roles`` تكتب «``...:u{user_id}``» لكل مستلم.
فالفحص لا يطابق صًفا أبًدا — حارس لا يحرس شيًئا.

ولم يظهر أثره فورًا لأن ``create_task`` تمنع التكرار ما دام التذكير
مفتوًحا. فإذا أغلقه أحد، عاد المسح الساعيّ يُنشئ غيره — وكل ساعة صفّ
جديد لحدث واحد.

**والتأخّر يزداد بمرور الوقت**، فالتذكير القائم يُحدَّث برقمه الجديد بدل
أن يُضاف بجانبه: صفٌّ ثانٍ لا يحمل معلومة جديدة ويُغرق الصندوق.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete as sa_delete, func, select

from app import models
from app.database import SessionLocal
from app.notifications import sla_scan

TEMPLATE_CODE = "TST-SLA-01"


@pytest.fixture
def overdue_task():
    """قالب بمهلة ساعة، ومهمة تجاوزتها — الموقف كامًلا بلا انتظار البذرة."""
    db = SessionLocal()
    created = {}
    try:
        company_id = db.scalar(select(models.Company.id).order_by(
            models.Company.id))
        tpl = db.scalar(select(models.NotificationTemplate).where(
            models.NotificationTemplate.code == TEMPLATE_CODE))
        if tpl is None:
            tpl = models.NotificationTemplate(
                code=TEMPLATE_CODE, name="قالب فحص المهلة",
                category="system", event_type="request_stage",
                channel_default="in_app", sla_hours=1,
                body_text="مهمة تجاوزت مهلتها.")
            db.add(tpl)
        task = models.Task(
            company_id=company_id, type="renew_residency",
            title="مهمة فحص المهلة", status="open",
            template_code=TEMPLATE_CODE,
            dedup_key="test:sla:subject",
            created_at=(datetime.now(timezone.utc)
                        - timedelta(hours=5)).replace(tzinfo=None))
        db.add(task)
        db.commit()
        created = {"task_id": task.id, "company_id": company_id}
        yield created
    finally:
        tid = created.get("task_id")
        if tid:
            db.execute(sa_delete(models.Task).where(
                models.Task.dedup_key.like(f"sla_escalation:{tid}:%")))
            db.execute(sa_delete(models.Task).where(models.Task.id == tid))
        db.execute(sa_delete(models.NotificationTemplate).where(
            models.NotificationTemplate.code == TEMPLATE_CODE))
        db.commit()
        db.close()


def _escalations(task_id: int):
    db = SessionLocal()
    try:
        return db.scalars(select(models.Task).where(
            models.Task.dedup_key.like(f"sla_escalation:{task_id}:%"))).all()
    finally:
        db.close()


def test_an_overdue_task_is_escalated_once(overdue_task):
    """خطّ الأساس: يُنشأ تذكير فعًلا — وإلا كان الفحص التالي بلا معنى."""
    db = SessionLocal()
    try:
        result = sla_scan(db)
    finally:
        db.close()
    assert result["escalated"] >= 1, f"لم يُصعَّد شيء: {result}"
    assert _escalations(overdue_task["task_id"]), "لا تذكير في القاعدة"


def test_running_the_scan_again_adds_nothing(overdue_task):
    """**جوهر البند**: المسح الثاني لا يضيف صًفا."""
    db = SessionLocal()
    try:
        sla_scan(db)
        first = len(_escalations(overdue_task["task_id"]))
        sla_scan(db)
        sla_scan(db)
    finally:
        db.close()
    assert len(_escalations(overdue_task["task_id"])) == first, (
        "المسح المتكرر أضاف تذكيرات لنفس الحدث"
    )


def test_the_existing_reminder_is_refreshed_not_duplicated(overdue_task):
    """التأخّر يزداد، والرقم في التذكير يتبعه."""
    db = SessionLocal()
    try:
        sla_scan(db)
        before = [(r.id, r.detail) for r in _escalations(overdue_task["task_id"])]
        assert before, "لا تذكير للتحديث"

        # نُشيخ المهمة أكثر، فيتغيّر رقم التأخّر
        task = db.get(models.Task, overdue_task["task_id"])
        task.created_at = (datetime.now(timezone.utc)
                           - timedelta(hours=20)).replace(tzinfo=None)
        db.commit()
        result = sla_scan(db)
    finally:
        db.close()

    after = [(r.id, r.detail) for r in _escalations(overdue_task["task_id"])]
    assert [r[0] for r in after] == [r[0] for r in before], (
        "تبدّلت الصفوف — أُنشئ تذكير جديد بدل تحديث القائم"
    )
    assert [r[1] for r in after] != [r[1] for r in before], (
        "التذكير لم يُحدَّث برقم التأخّر الجديد — «يُحدَّث» اسم بلا فعل"
    )
    assert result.get("refreshed", 0) >= 1


def test_a_closed_reminder_does_not_come_back_every_hour(overdue_task):
    """**السبب الذي أخفى العطل**: الحارس كان يعمل بالمصادفة.

    ``create_task`` تمنع التكرار ما دام التذكير مفتوًحا، فإذا أُغلق عاد
    المسح يُنشئ غيره كل ساعة. والفحص هنا على الحالة التي كانت تنكشف
    فيها.
    """
    db = SessionLocal()
    try:
        sla_scan(db)
        rows = _escalations(overdue_task["task_id"])
        assert rows, "لا تذكير"
        for r in rows:
            obj = db.get(models.Task, r.id)
            obj.status = "done"
        db.commit()
        count_before = db.scalar(select(func.count()).select_from(
            models.Task).where(models.Task.dedup_key.like(
                f"sla_escalation:{overdue_task['task_id']}:%")))
        sla_scan(db)
        count_after = db.scalar(select(func.count()).select_from(
            models.Task).where(models.Task.dedup_key.like(
                f"sla_escalation:{overdue_task['task_id']}:%")))
    finally:
        db.close()
    assert count_after == count_before, (
        "أُنشئ تذكير جديد بعد إغلاق السابق — عادت الساعة تُنتج صًفا"
    )


def test_a_task_within_its_deadline_is_not_escalated(overdue_task):
    """والاتجاه المعاكس: ما لم يتأخّر لا يُصعَّد."""
    db = SessionLocal()
    try:
        task = db.get(models.Task, overdue_task["task_id"])
        task.created_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        db.execute(sa_delete(models.Task).where(
            models.Task.dedup_key.like(
                f"sla_escalation:{overdue_task['task_id']}:%")))
        db.commit()
        sla_scan(db)
    finally:
        db.close()
    assert not _escalations(overdue_task["task_id"]), (
        "صُعِّدت مهمة داخل مهلتها"
    )
