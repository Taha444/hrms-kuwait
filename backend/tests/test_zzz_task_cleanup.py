# -*- coding: utf-8 -*-
"""تنظيف ما خلّفه تكرار المهام (البندان 3 و12).

**منع التكرار الجديد لا يزيل ما تراكم.** حماية SLA من التكرار مبنيّة
منذ TSK-06، ومع ذلك بقي في القاعدة ما أنتجه العطل قبلها: قِيس على قاعدة
التطوير **28 نسخة مكرَّرة** من مهام مفتوحة.

وصندوق فيه أربعون بلاًغا عن ثمانية أشياء يُعلّم قارئه ألّا يقرأه —
فيضيع البلاغ الحقيقي بين نسخه، وهو أسوأ من غياب البلاغ.

**ولا يُحذف صفٌّ واحد**: تُغلَق بحالة ``dismissed`` وسبب مكتوب، فالسجل
يبقى للتفتيش. وهذا شرط التقرير صراحًة: «بدون حذف Audit History».
"""
from __future__ import annotations

from sqlalchemy import func, select

from app import models, task_cleanup
from app.database import SessionLocal


def _mk(db, entity_id: int = 999_001, **over) -> models.Task:
    """مهمة قياس لقاعدة **التكرار** وحدها.

    ونوع الكيان خارج جدول اليتيمة بقصد: أول كتابة استعملت ``permit``
    بمعرّف لا وجود له، فأمسكتها قاعدة «الكيان لم يعد موجوًدا» وأُغلقت
    الثلاث — سلوٌك صحيح وتجهيز خاطئ.
    """
    fields = {"company_id": 1, "type": "doc_expiring", "title": "بلاغ قياس",
              "detail": "نصٌّ أصلي", "status": "open", "assignee_user_id": 1,
              "related_entity_type": "probe", "related_entity_id": entity_id}
    fields.update(over)
    row = models.Task(**fields)
    db.add(row)
    return row


def test_duplicates_are_closed_and_one_survives(client):
    """**جوهر التنظيف**: نسخة واحدة تبقى، والباقي يُغلَق.

    ومعرّف كيان خاصٌّ بهذا الاختبار: أول كتابة استعملت المعرّف المشترك
    فوجدت مهمًة رابعة سبقتها في القاعدة، فأُغلقت الثلاث — والعيب في
    دعوى الاختبار لا في التنظيف.
    """
    db = SessionLocal()
    try:
        made = [_mk(db, entity_id=999_010) for _ in range(3)]
        db.commit()
        ids = [t.id for t in made]
        task_cleanup.run(db, company_id=1, apply=True)
        rows = db.scalars(select(models.Task).where(
            models.Task.id.in_(ids))).all()
    finally:
        db.close()
    alive = [t for t in rows if t.status in task_cleanup.OPEN]
    assert len(alive) == 1, [(t.id, t.status) for t in rows]
    assert alive[0].id == max(ids), "أُبقيت النسخة الأقدم بدل الأحدث"


def test_nothing_is_deleted(client):
    """**والسجل لا يُمسّ**: الإغلاق تصنيف لا حذف — شرط التقرير صراحًة."""
    db = SessionLocal()
    try:
        before = db.scalar(select(func.count()).select_from(models.Task))
        for _ in range(2):
            _mk(db, entity_id=999_002)
        db.commit()
        task_cleanup.run(db, company_id=1, apply=True)
        after = db.scalar(select(func.count()).select_from(models.Task))
    finally:
        db.close()
    assert after == before + 2, f"اختفت صفوف: {before} → {after}"


def test_the_reason_is_written_on_the_row(client):
    """و«أُغلقت» بلا سبب سؤال بلا جواب — فالسبب في الصفّ نفسه."""
    db = SessionLocal()
    try:
        for _ in range(2):
            _mk(db, entity_id=999_003)
        db.commit()
        task_cleanup.run(db, company_id=1, apply=True)
        closed = db.scalars(select(models.Task).where(
            models.Task.related_entity_id == 999_003,
            models.Task.status == "dismissed")).all()
    finally:
        db.close()
    assert closed, "لم يُغلق شيء"
    for t in closed:
        assert "مكرَّرة" in (t.detail or ""), t.detail
        # والنصّ الأصلي يبقى — يُلحَق به ولا يُستبدَل.
        assert "نصٌّ أصلي" in (t.detail or ""), t.detail
        assert t.completed_at is not None


def test_a_dry_run_writes_nothing(client):
    """**وجافٌّ افتراضًيا**: من يشغّله على الإنتاج يرى الأثر قبل وقوعه."""
    db = SessionLocal()
    try:
        for _ in range(2):
            _mk(db, entity_id=999_004)
        db.commit()
        rep = task_cleanup.run(db, company_id=1, apply=False)
        still = db.scalar(select(func.count()).select_from(models.Task).where(
            models.Task.related_entity_id == 999_004,
            models.Task.status.in_(task_cleanup.OPEN)))
    finally:
        db.close()
    assert rep["apply"] is False and rep["total"] >= 1
    assert still == 2, "التقرير الجافّ كتب في القاعدة"


def test_running_twice_changes_nothing_more(client):
    """وقابل لإعادة التشغيل: التشغيل الثاني لا يجد ما يُغلقه."""
    db = SessionLocal()
    try:
        for _ in range(3):
            _mk(db, entity_id=999_005)
        db.commit()
        first = task_cleanup.run(db, company_id=1, apply=True)["total"]
        second = task_cleanup.run(db, company_id=1, apply=True)["total"]
    finally:
        db.close()
    assert first >= 2 and second == 0, (first, second)


def test_a_notification_on_a_closed_request_is_kept(client):
    """**ولا يُكنَس الإشعار**: خبر النتيجة يُقرأ بعد إغلاق الطلب.

    وإغلاقه مع المهام يمحو إخطار الموظف بما جرى بطلبه — وهو الدرس
    المكتوب في ``_close_open_tasks`` نفسها.
    """
    from app.task_kinds import is_notification

    kind = "request_update"
    assert is_notification(kind), "تغيّر تصنيف النوع — أعد النظر"

    db = SessionLocal()
    try:
        req = db.scalar(select(models.Request).where(
            models.Request.closed_at.is_not(None)))
        if req is None:
            return  # لا طلب مغلق في هذه القاعدة — لا شيء يُقاس
        t = models.Task(company_id=req.company_id, type=kind,
                        title="خبر", status="open", assignee_user_id=1,
                        related_entity_type="request", related_entity_id=req.id)
        db.add(t); db.commit()
        tid = t.id
        task_cleanup.run(db, company_id=req.company_id, apply=True)
        after = db.get(models.Task, tid)
        status = after.status
    finally:
        db.close()
    assert status in task_cleanup.OPEN, "كُنس إشعار النتيجة"


def test_a_task_on_a_closed_request_is_swept(client):
    """أما المهمة القابلة للتنفيذ على طلب منتهٍ فتُغلَق: لا إجراء بعده."""
    db = SessionLocal()
    try:
        req = db.scalar(select(models.Request).where(
            models.Request.closed_at.is_not(None)))
        if req is None:
            return
        t = models.Task(company_id=req.company_id, type="request_stage",
                        title="مرحلة", status="open", assignee_user_id=1,
                        related_entity_type="request", related_entity_id=req.id)
        db.add(t); db.commit()
        tid = t.id
        task_cleanup.run(db, company_id=req.company_id, apply=True)
        status = db.get(models.Task, tid).status
    finally:
        db.close()
    assert status == "dismissed", status
