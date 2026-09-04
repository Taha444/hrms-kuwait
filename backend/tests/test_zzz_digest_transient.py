# -*- coding: utf-8 -*-
"""P2-08 — الملخّص اليومي عابر ولا يبني تراكًما.

**العطل**: المفتاح اليومي يمنع تكرار الملخّص داخل اليوم، ولا يغلق ملخّص
الأمس. فبعد شهر ثلاثون صًفا مفتوًحا لكل مستخدم، كلها تقول «لديك كذا
مهمة» بأرقام بائدة.

وصندوق يمتلئ بملخّصات قديمة يُقرأ كعمل متأخّر فيُهمَل — ومعه الملخّص
الصحيح. وهذا نقيض الغرض: الملخّص وُجد ليقلّل الضجيج لا ليصنعه.

**والملخّص ملخّص لا سجلّ**: قيمته في يومه، وما بعده يُعاد حسابه من
المهام نفسها.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete as sa_delete, func, select

from app import models
from app.database import SessionLocal
from app.notifications import digest_scan


def _open_digests(user_id: int):
    db = SessionLocal()
    try:
        return db.scalars(select(models.Task).where(
            models.Task.type == "digest",
            models.Task.assignee_user_id == user_id,
            models.Task.status.in_(("open", "in_progress")))).all()
    finally:
        db.close()


@pytest.fixture
def user_with_open_work():
    """مستخدم له مهمة مفتوحة — بلا عمل لا ملخّص."""
    db = SessionLocal()
    made = []
    try:
        user = db.scalar(select(models.User).where(
            models.User.role == "hr", models.User.is_active == True))  # noqa: E712
        task = models.Task(company_id=user.company_id, type="renew_residency",
                           title="مهمة لفحص الملخّص", status="open",
                           assignee_user_id=user.id,
                           dedup_key="test:digest:subject")
        db.add(task)
        db.commit()
        made.append(task.id)
        yield user.id
    finally:
        db.execute(sa_delete(models.Task).where(
            models.Task.dedup_key == "test:digest:subject"))
        db.execute(sa_delete(models.Task).where(
            models.Task.type == "digest",
            models.Task.assignee_user_id.isnot(None)))
        db.commit()
        db.close()


def test_a_digest_is_produced_at_all(user_with_open_work):
    """خطّ الأساس: بلا ملخّص لا معنى لما بعده."""
    db = SessionLocal()
    try:
        digest_scan(db)
    finally:
        db.close()
    assert _open_digests(user_with_open_work), "لم يُنشأ ملخّص"


def test_running_twice_in_one_day_does_not_add_a_second(user_with_open_work):
    """المفتاح اليومي يمنع التكرار داخل اليوم — وهذا كان يعمل."""
    db = SessionLocal()
    try:
        digest_scan(db)
        first = len(_open_digests(user_with_open_work))
        digest_scan(db)
    finally:
        db.close()
    assert len(_open_digests(user_with_open_work)) == first


def test_todays_digest_supersedes_yesterdays(user_with_open_work):
    """**جوهر البند**: ملخّص اليوم يُلغي ما قبله.

    وبدونه يتراكم صفّ لكل يوم: بعد شهر ثلاثون ملخًّصا مفتوًحا بأرقام
    قديمة، وكلها تدّعي وصف الحال.
    """
    uid = user_with_open_work
    db = SessionLocal()
    try:
        digest_scan(db)
        # نُشيخ ملخّص اليوم كأنه من الأمس
        yesterday = date.today() - timedelta(days=1)
        for d in db.scalars(select(models.Task).where(
                models.Task.type == "digest",
                models.Task.assignee_user_id == uid)).all():
            d.dedup_key = f"digest:{uid}:{yesterday}"
        db.commit()

        digest_scan(db)          # ملخّص اليوم
    finally:
        db.close()

    open_now = _open_digests(uid)
    assert len(open_now) == 1, (
        f"ملخّصات متراكمة بدل واحد: {[(d.id, d.dedup_key) for d in open_now]}"
    )
    assert str(date.today()) in (open_now[0].dedup_key or ""), (
        "الباقي هو القديم لا الجديد"
    )


def test_the_superseded_digest_is_dismissed_not_deleted(user_with_open_work):
    """ويُوسَم مُلًغى لا يُحذف: من يفتّش يرى أنه كان ثم استُبدل."""
    uid = user_with_open_work
    db = SessionLocal()
    try:
        digest_scan(db)
        yesterday = date.today() - timedelta(days=1)
        for d in db.scalars(select(models.Task).where(
                models.Task.type == "digest",
                models.Task.assignee_user_id == uid)).all():
            d.dedup_key = f"digest:{uid}:{yesterday}"
        db.commit()
        digest_scan(db)

        total = db.scalar(select(func.count()).select_from(models.Task).where(
            models.Task.type == "digest",
            models.Task.assignee_user_id == uid))
        dismissed = db.scalar(select(func.count()).select_from(models.Task).where(
            models.Task.type == "digest",
            models.Task.assignee_user_id == uid,
            models.Task.status == "dismissed"))
    finally:
        db.close()
    assert total >= 2, "اختفى القديم بدل أن يُوسَم"
    assert dismissed >= 1, "لم يُوسَم القديم مُلًغى"


def test_the_digest_stays_out_of_the_actionable_count(user_with_open_work):
    """وهو خبر لا إجراء — فلا يدخل عدّاد ما يحتاج عمًلا (P2-07)."""
    from app.task_kinds import is_notification

    assert is_notification("digest"), "الملخّص يُعدّ مهمة قابلة للتنفيذ"
