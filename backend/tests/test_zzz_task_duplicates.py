# -*- coding: utf-8 -*-
"""TSK-01/TSK-05 — التكرار يُمنع في القاعدة لا في الشيفرة وحدها.

**العطل الموثَّق**: ``QA Renewal Window`` ×3 و``QA Retest Aug14`` ×2 —
مهام مكرّرة لنفس المعاملة.

**الجذر**: ``create_task`` يبحث عن مهمة مفتوحة بنفس ``dedup_key`` ويتخطّى.
وهذا يكفي في المسار الواحد، ويُخترق عند التزامن: نسختان تقرآن «لا يوجد»
في اللحظة نفسها فتكتب كلٌّ منهما صًفا. ومصادر التزامن قائمة فعًلا — الفحص
اليومي يعمل أكثر من مرة، والنشر على AWS بأكثر من نسخة.

ولهذا يجب أن يكون الفحص **قيًدا في القاعدة**: ما لا تحرسه القاعدة
تحرسه النوايا.

والمصدر الثاني للتكرار مختلف: تغيير المرحلة يُنشئ مهمة جديدة ولا يغلق
سابقتها، فتتراكم على المعاملة الواحدة مهام لمراحل انتهت.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import models
from app.database import SessionLocal
from app.notifications import create_task, was_created


@pytest.fixture
def company_id():
    db = SessionLocal()
    try:
        return db.scalar(select(models.Company.id).order_by(models.Company.id))
    finally:
        db.close()


def _cleanup(keys: list[str]) -> None:
    db = SessionLocal()
    try:
        for k in keys:
            for t in db.scalars(select(models.Task).where(
                    models.Task.dedup_key == k)).all():
                db.delete(t)
        db.commit()
    finally:
        db.close()


def test_the_database_itself_refuses_a_second_open_task(company_id):
    """**جوهر البند**: الرفض من القاعدة، بلا مرور بمنطق التطبيق.

    الإدراج هنا يلتفّ على ``create_task`` عمًدا: لو فُحص عبرها لقاس
    الاختبار فحص الشيفرة — وهو الفحص الذي نعرف أنه يُخترق. والمقيس هنا
    هو ما يبقى صحيًحا حين يُخترق: القيد.
    """
    key = "test:dup:db-level"
    _cleanup([key])
    db = SessionLocal()
    try:
        db.add(models.Task(company_id=company_id, type="renew_residency",
                           title="الأولى", dedup_key=key, status="open"))
        db.commit()

        db.add(models.Task(company_id=company_id, type="renew_residency",
                           title="الثانية", dedup_key=key, status="open"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()
    _cleanup([key])


def test_a_closed_task_does_not_block_a_new_one(company_id):
    """القيد جزئي عمًدا: المنتهي يتكرّر بطبيعته.

    التجديد السنوي يُنشئ المهمة نفسها كل سنة. قيد شامل يمنع العمل لا
    التكرار.
    """
    key = "test:dup:reopen"
    _cleanup([key])
    db = SessionLocal()
    try:
        first = models.Task(company_id=company_id, type="renew_residency",
                            title="سنة أولى", dedup_key=key, status="open")
        db.add(first)
        db.commit()
        first.status = "done"
        db.commit()

        db.add(models.Task(company_id=company_id, type="renew_residency",
                           title="سنة ثانية", dedup_key=key, status="open"))
        db.commit()            # لا يُرفض
        n = db.scalar(select(func.count()).select_from(models.Task).where(
            models.Task.dedup_key == key))
        assert n == 2
    finally:
        db.close()
    _cleanup([key])


def test_create_task_survives_the_constraint_instead_of_failing(company_id):
    """الشيفرة تحتمل حكم القاعدة.

    لو صعد ``IntegrityError`` لأسقط طلب المستخدم كلَّه بسبب مهمة موجودة
    فعًلا — وهو أسوأ من التكرار الذي جئنا نمنعه.
    """
    key = "test:dup:graceful"
    _cleanup([key])
    db = SessionLocal()
    try:
        a = create_task(db, company_id=company_id, type="renew_residency",
                        title="الأولى", dedup_key=key)
        db.commit()
        b = create_task(db, company_id=company_id, type="renew_residency",
                        title="الثانية", dedup_key=key)
        db.commit()
        assert a.id == b.id, "أُنشئ صفّ ثانٍ لنفس المفتاح"
        assert was_created(b) is False, "التخطّي حُسب إنشاًء"
    finally:
        db.close()
    _cleanup([key])


def test_no_duplicate_open_tasks_anywhere(client):
    """مسح شامل على القاعدة كلها بعد كل ما أنشأته الاختبارات."""
    db = SessionLocal()
    try:
        rows = db.execute(
            select(models.Task.dedup_key, func.count())
            .where(models.Task.status.in_(("open", "in_progress")),
                   models.Task.dedup_key.isnot(None))
            .group_by(models.Task.dedup_key)
            .having(func.count() > 1)
        ).all()
        assert not rows, f"مفاتيح مكرّرة على مهام مفتوحة: {rows[:5]}"
    finally:
        db.close()
