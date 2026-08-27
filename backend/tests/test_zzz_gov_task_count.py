# -*- coding: utf-8 -*-
"""BKL-06 — الرقم وقائمته يصفان الشيء نفسه.

لوحة المندوب تقول 2 أو 3 والفلتر يقول 0. والقياس على بيانات حقيقية بعد
المسح اليومي كان أوضح: **العدّاد 29 والقائمة 12** — لأن العدّاد على مستوى
الشركة والقائمة على مستوى المستخدم.

ولا أحد الرقمين خاطئ في ذاته؛ الخطأ أنهما يحملان الاسم نفسه ويُعرضان
كأنهما جواب سؤال واحد. فمن يرى 29 ويفتح فيجد 12 لا يعرف أيّهما يصدّق —
وقد يظنّ أن سبع عشرة معاملة ضاعت.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import gov_tasks, models
from app.database import SessionLocal
from app.notifications import daily_scan
from app.routers.tasks import _CATEGORY

from .conftest import auth_headers, login

PRO = ("100000000003", "deleg123")


@pytest.fixture(scope="module")
def scanned():
    """يشغّل المسح اليومي مرة — بلا مهام لا شيء يُقاس."""
    db = SessionLocal()
    try:
        daily_scan(db)
    finally:
        db.close()


def test_government_category_is_derived_not_rewritten():
    """قائمتان للأنواع تنحرفان بنوع يُضاف في إحداهما.

    كانتا متطابقتين بالمصادفة؛ والاشتقاق يجعل التطابق قاعدة لا صدفة.
    """
    from_category = {k for k, v in _CATEGORY.items() if v == "government"}
    assert from_category == set(gov_tasks.GOV_TASK_TYPES), (
        f"تصنيف «حكومي» يخالف التعريف: "
        f"{from_category ^ set(gov_tasks.GOV_TASK_TYPES)}"
    )


def test_count_equals_the_length_of_its_own_list(scanned):
    """جوهر البند: العدّ مشتقّ من استعلام القائمة، فيستحيل اختلافهما."""
    db = SessionLocal()
    try:
        for scope in ({}, {"company_id": 1}, {"company_id": 2}):
            n = gov_tasks.count_gov_tasks(db, **scope)
            rows = gov_tasks.list_gov_tasks(db, **scope)
            assert n == len(rows), (
                f"النطاق {scope}: العدّاد {n} والقائمة {len(rows)}"
            )
    finally:
        db.close()


def test_scope_narrows_both_together(scanned):
    """تضييق النطاق يضيّق الرقم والقائمة معًا — لا أحدهما."""
    db = SessionLocal()
    try:
        pro = db.scalar(select(models.User).where(
            models.User.civil_id == PRO[0]))
        assert pro is not None
        company = gov_tasks.count_gov_tasks(db, company_id=1)
        mine = gov_tasks.count_gov_tasks(db, company_id=1,
                                         assignee_user_id=pro.id)
        assert mine <= company, "مهامي أكثر من مهام الشركة"
        assert len(gov_tasks.list_gov_tasks(
            db, company_id=1, assignee_user_id=pro.id)) == mine
    finally:
        db.close()


def test_operations_endpoint_returns_the_list_behind_its_number(client, scanned):
    """الرقم بلا وجهة تعرضه يبقى ادّعاءً.

    كانت البطاقة تنقل إلى «مهامي» وهي تعدّ مهام الشركة — فيرى المستخدم
    رقًما ثم قائمة أقصر منه بلا تفسير.
    """
    hdr = auth_headers(login(client, *PRO))
    r = client.get("/api/operations/overview", headers=hdr)
    if r.status_code == 404:
        r = client.get("/api/operations", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "gov_tasks" in body, "الوجهة تعيد عدًدا بلا قائمة"
    assert len(body["gov_tasks"]) == body["open_gov_tasks"], (
        f"العدّاد {body['open_gov_tasks']} والقائمة {len(body['gov_tasks'])} "
        "— وهو العطل الأصلي بعينه"
    )


def test_every_listed_task_is_actually_a_government_type(client, scanned):
    """ما يُعرض تحت العنوان هو ما يصفه العنوان."""
    db = SessionLocal()
    try:
        for tk in gov_tasks.list_gov_tasks(db, company_id=1):
            assert tk.type in gov_tasks.GOV_TASK_TYPES
            assert _CATEGORY.get(tk.type) == "government", (
                f"مهمة {tk.type} تُعدّ حكومية ولا تُصنَّف كذلك في الفلتر"
            )
    finally:
        db.close()


def test_closed_tasks_leave_both_the_count_and_the_list(scanned):
    """إغلاق مهمة يُنقص الرقم والقائمة معًا — لا الرقم وحده."""
    db = SessionLocal()
    try:
        rows = gov_tasks.list_gov_tasks(db, company_id=1)
        if not rows:
            pytest.fail("لا مهام حكومية بعد المسح — لا شيء يُقاس")
        before = gov_tasks.count_gov_tasks(db, company_id=1)
        target = rows[0]
        target.status = "done"
        db.commit()
        try:
            after = gov_tasks.count_gov_tasks(db, company_id=1)
            after_rows = gov_tasks.list_gov_tasks(db, company_id=1)
            assert after == before - 1
            assert len(after_rows) == after
            assert all(x.id != target.id for x in after_rows)
        finally:
            target.status = "open"
            db.commit()
    finally:
        db.close()
