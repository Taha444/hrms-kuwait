# -*- coding: utf-8 -*-
"""البندان 9 و22 — نطاق الصندوق، والخلاصات المنقضية.

**9 — رقٌم لا يتغيّر بتغيّر الشركة يُقرأ خطًأ.** ``inbox_query`` كانت
تصفّي بالمكلَّف وحده. فالمندوب الذي يخدم شركتين يرى العدد نفسه في
كلتيهما، **بجانب عدادات مقصورة على المختارة** — فيقرأ الرقم على أنه
لها. قِيس في التقرير: 7 مهام على شركة، و7 على أخرى ليس فيها معاملة.

**والمجموع لا يختفي**: يُعرَض باسمه الصريح، فالعمل يُنسَب إلى مكانه لا
يُحجَب. ومن يخدم شركة واحدة يتساوى الرقمان.

**22 — وخلاصة يوم مضى لا معنى لبقائها مفتوحة.** عشرة ملخّصات من يوم
واحد ظلّت مفتوحة تسعة أيام. وهي مصنَّفة إشعاًرا فلا تُضخّم عدّاد
المهام — لكنها تُغرق الصندوق وتُعلّم قارئه ألّا يقرأه.

**ولا تشمل القاعدة كل إشعار**: خبر نتيجة طلب يُقرأ متى فُتح الملف.
الدورية وحدها هي التي تنقضي بانقضاء يومها.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import models, task_cleanup
from app.database import SessionLocal
from app.task_kinds import inbox_query, is_notification
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")


def _mk_task(db, *, company_id: int, user_id: int, type_: str = "config_gap",
             age_days: int = 0) -> models.Task:
    row = models.Task(
        company_id=company_id, type=type_, title="قياس النطاق",
        detail="نصّ", status="open", assignee_user_id=user_id)
    db.add(row)
    db.flush()
    if age_days:
        row.created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    return row


def _hr_user_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.User.id).where(
            models.User.civil_id == HR[0]))
    finally:
        db.close()


def test_the_inbox_can_be_scoped_to_a_company():
    """**جوهر البند 9**: الصندوق يعرف الشركة."""
    uid = _hr_user_id()
    db = SessionLocal()
    try:
        _mk_task(db, company_id=1, user_id=uid)
        _mk_task(db, company_id=2, user_id=uid)
        db.commit()
        n_all = len(db.scalars(inbox_query(uid, "open", "task")).all())
        n_one = len(db.scalars(inbox_query(uid, "open", "task", company_id=1)).all())
        n_two = len(db.scalars(inbox_query(uid, "open", "task", company_id=2)).all())
    finally:
        db.close()
    assert n_one + n_two <= n_all
    assert n_one != n_all or n_two == 0, (n_all, n_one, n_two)
    assert n_two >= 1, "لم يُحسب صفّ الشركة الثانية"


def test_the_count_reports_both_the_scope_and_the_total(client):
    """**والمجموع لا يختفي**: يُعرَض باسمه فلا يُحجَب عمٌل."""
    uid = _hr_user_id()
    db = SessionLocal()
    try:
        _mk_task(db, company_id=2, user_id=uid)
        db.commit()
    finally:
        db.close()

    body = client.get("/api/tasks/count",
                      headers=auth_headers(login(client, *HR))).json()
    for key in ("open_tasks", "open_tasks_all_companies",
                "unread_notifications", "total_inbox_items"):
        assert key in body, sorted(body)
    assert body["open_tasks_all_companies"] >= body["open_tasks"], body


def test_the_list_is_scoped_by_default_with_an_explicit_escape(client):
    """والافتراض شركة الفاعل، والكلّ **بطلب صريح** لا بسلوك ضمني."""
    hdr = auth_headers(login(client, *HR))
    scoped = client.get("/api/tasks/my", headers=hdr,
                        params={"kind": "task"}).json()
    everything = client.get("/api/tasks/my", headers=hdr,
                            params={"kind": "task", "all_companies": True}).json()
    assert len(everything) >= len(scoped), (len(scoped), len(everything))
    assert all(t.get("id") for t in scoped)


def test_a_stale_digest_is_closed(client):
    """**جوهر البند 22**: خلاصة يوم مضى تُغلَق."""
    uid = _hr_user_id()
    db = SessionLocal()
    try:
        old = _mk_task(db, company_id=1, user_id=uid, type_="digest", age_days=30)
        db.commit()
        oid = old.id
        task_cleanup.run(db, company_id=1, apply=True)
        status = db.get(models.Task, oid).status
        detail = db.get(models.Task, oid).detail
    finally:
        db.close()
    assert status == "dismissed", status
    assert "انقضى" in (detail or ""), detail


def test_todays_digest_is_left_alone(client):
    """ولا تُكنَس خلاصة اليوم: القياس على تاريخها لا على نوعها."""
    uid = _hr_user_id()
    db = SessionLocal()
    try:
        fresh = _mk_task(db, company_id=1, user_id=uid, type_="digest")
        db.commit()
        fid = fresh.id
        task_cleanup.run(db, company_id=1, apply=True)
        status = db.get(models.Task, fid).status
    finally:
        db.close()
    assert status in task_cleanup.OPEN, status


def test_a_result_notification_is_never_swept(client):
    """**ولا تشمل القاعدة كل إشعار**: خبر النتيجة يُقرأ متى فُتح الملف."""
    assert is_notification("request_update")
    assert "request_update" not in task_cleanup.PERIODIC_TYPES

    uid = _hr_user_id()
    db = SessionLocal()
    try:
        news = _mk_task(db, company_id=1, user_id=uid,
                        type_="request_update", age_days=90)
        db.commit()
        nid = news.id
        task_cleanup.run(db, company_id=1, apply=True)
        status = db.get(models.Task, nid).status
    finally:
        db.close()
    assert status in task_cleanup.OPEN, "كُنس خبر نتيجة"
