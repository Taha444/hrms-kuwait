# -*- coding: utf-8 -*-
"""TSK-03 — فصل ما يحتاج إجراًء عمّا يُقرأ.

**القياس الموثَّق**: أربعة وأربعون عنصًرا مفتوًحا عند شؤون الموظفين، ستة
منها مهام وثمانية وثلاثون إشعار/ملخّص/تنبيه تأخّر.

ورقم بهذا الحجم لا يُقرأ كصندوق فيه ستّ مهام، بل كعمل متأخّر ضخم —
فيُهمَل كلّه وتضيع الستة التي تُعطّل العمل فعًلا.

معيار الفصل واحد: **لو لم يفعل المستخدم شيًئا، هل يتعطّل عمل؟**

والتصنيف لا الحذف: الأخبار تبقى في مكانها بمرشّح صريح، ولا تُمحى من
التاريخ.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.task_kinds import NOTIFICATION_TYPES, inbox_query, is_notification
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
#: لوحة HR تعرض العدّاد باسم open_tasks لا my_open_tasks — الاسمان
#: لرقم واحد، وهذا نفسه ما يُصلحه TSK-07.
DASH_KEYS = ("my_open_tasks", "open_tasks")

#: مكتوبة هنا مستقلّة عن الوحدة عمًدا: قراءتها من الوحدة تجعل تفريغها
#: يُفرغ الاختبار فيمرّ أخضر وهو لا يفحص شيًئا.
KNOWN_NOTICES = ("request_update", "digest", "sla_escalation")


@pytest.fixture
def hr_inbox(client):
    hdr = auth_headers(login(client, *HR))
    db = SessionLocal()
    try:
        uid = db.scalar(select(models.User.id).where(
            models.User.civil_id == HR[0]))
    finally:
        db.close()
    return hdr, uid


def test_the_definition_still_covers_the_known_notices():
    """لو أُفرغت القائمة لصار كل شيء مهمة — والفصل بلا معنى."""
    for kind in KNOWN_NOTICES:
        assert is_notification(kind), f"«{kind}» لم يعد يُعدّ خبًرا"


def test_the_counter_separates_actions_from_news(client, hr_inbox):
    """**جوهر البند**: رقمان لا رقم واحد."""
    hdr, _ = hr_inbox
    r = client.get("/api/tasks/count", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("open", "tasks", "notifications"):
        assert key in body, f"العدّاد بلا «{key}»: {body}"
    assert body["tasks"] + body["notifications"] == body["open"], (
        f"الفصل لا يجمع إلى الكل: {body}"
    )


def test_each_number_equals_the_list_it_opens(client, hr_inbox):
    """القاعدة العامة: العدّاد يُشتقّ من الاستعلام الذي يغذّي قائمته."""
    hdr, _ = hr_inbox
    counts = client.get("/api/tasks/count", headers=hdr).json()
    for kind, key in (("task", "tasks"), ("notification", "notifications")):
        rows = client.get("/api/tasks/my", headers=hdr,
                          params={"status": "open", "kind": kind}).json()
        assert len(rows) == counts[key], (
            f"«{kind}»: العدّاد {counts[key]} والقائمة {len(rows)}"
        )


def test_the_action_list_contains_no_news(client, hr_inbox):
    """صندوق المهام يعرض الإجراءات المطلوبة فقط."""
    hdr, _ = hr_inbox
    rows = client.get("/api/tasks/my", headers=hdr,
                      params={"status": "open", "kind": "task"}).json()
    intruders = [x["type"] for x in rows if x["type"] in KNOWN_NOTICES]
    assert not intruders, f"أخبار داخل صندوق الإجراءات: {set(intruders)}"
    assert all(x["kind"] == "task" for x in rows)


def test_the_news_list_contains_no_actions(client, hr_inbox):
    """والاتجاه المعاكس — وإلا كان المرشّح يُخفي عمًلا مطلوًبا."""
    hdr, _ = hr_inbox
    rows = client.get("/api/tasks/my", headers=hdr,
                      params={"status": "open", "kind": "notification"}).json()
    assert all(x["type"] in NOTIFICATION_TYPES for x in rows), (
        f"مهام داخل قائمة الأخبار: {[x['type'] for x in rows][:5]}"
    )


def test_nothing_is_hidden_only_sorted(client, hr_inbox):
    """تصنيف لا حذف: مجموع القائمتين هو الصندوق كامًلا."""
    hdr, _ = hr_inbox
    everything = client.get("/api/tasks/my", headers=hdr,
                            params={"status": "open"}).json()
    a = client.get("/api/tasks/my", headers=hdr,
                   params={"status": "open", "kind": "task"}).json()
    b = client.get("/api/tasks/my", headers=hdr,
                   params={"status": "open", "kind": "notification"}).json()
    assert {x["id"] for x in a} | {x["id"] for x in b} == {x["id"] for x in everything}


def test_the_split_is_not_vacuous(client, hr_inbox):
    """الادّعاء لا يمرّ على صندوق فارغ.

    اختبار فصل على صفر عنصر يمرّ دائًما ولا يقيس شيًئا — فيُبنى العنصران
    هنا إن لم يوجدا.
    """
    hdr, uid = hr_inbox
    db = SessionLocal()
    made = []
    try:
        for typ, key in (("renew_residency", "test:split:action"),
                         ("request_update", "test:split:news")):
            if not db.scalar(select(models.Task).where(
                    models.Task.dedup_key == key)):
                tk = models.Task(company_id=1, type=typ, title="فحص الفصل",
                                 assignee_user_id=uid, dedup_key=key,
                                 status="open")
                db.add(tk)
                made.append(key)
        db.commit()
    finally:
        db.close()

    try:
        counts = client.get("/api/tasks/count", headers=hdr).json()
        assert counts["tasks"] >= 1 and counts["notifications"] >= 1, (
            f"لا عيّنة من النوعين — الاختبارات السابقة كانت تمرّ فراًغا: {counts}"
        )
    finally:
        db = SessionLocal()
        try:
            for key in made:
                for tk in db.scalars(select(models.Task).where(
                        models.Task.dedup_key == key)).all():
                    db.delete(tk)
            db.commit()
        finally:
            db.close()


# ==========================================================================
# TSK-07 — القاعدة نفسها على كل العدادات، لا على واحد
# ==========================================================================
def test_the_dashboard_number_matches_the_box_it_opens(client, hr_inbox):
    """**العيب نفسه في موضع ثانٍ**: اللوحة كانت تعدّ الصندوق كله.

    فتقول «44» ويعرض الصندوق ستة. ولم يكن ذلك عيًبا جديًدا بل القاعدة
    نفسها مكتوبة في موضعين — أُصلح أحدهما وبقي الآخر.
    """
    hdr, _ = hr_inbox
    dash = client.get("/api/dashboard", headers=hdr)
    assert dash.status_code == 200, dash.text
    body = dash.json()
    reported = next((body[k] for k in DASH_KEYS if k in body), None)
    assert reported is not None, "اللوحة بلا عدّاد مهام"

    rows = client.get("/api/tasks/my", headers=hdr,
                      params={"status": "open", "kind": "task"}).json()
    assert reported == len(rows), (
        f"اللوحة {reported} والصندوق {len(rows)}"
    )


def test_the_dashboard_and_the_badge_agree(client, hr_inbox):
    """ورقما الشاشتين واحد: من يرى اختلاًفا بينهما لا يثق بأيّهما."""
    hdr, _ = hr_inbox
    dash = client.get("/api/dashboard", headers=hdr).json()
    count = client.get("/api/tasks/count", headers=hdr).json()
    reported = next((dash[k] for k in DASH_KEYS if k in dash), None)
    assert reported == count["tasks"], (
        f"اللوحة {reported} والشارة {count['tasks']}"
    )


def test_this_comparison_is_not_run_on_an_empty_box(client, hr_inbox):
    """مقارنة صفر بصفر تمرّ دائًما ولا تفحص شيًئا."""
    hdr, uid = hr_inbox
    key = "test:counter:sweep"
    db = SessionLocal()
    try:
        if not db.scalar(select(models.Task).where(
                models.Task.dedup_key == key)):
            db.add(models.Task(company_id=1, type="renew_residency",
                               title="عيّنة عدّاد", assignee_user_id=uid,
                               dedup_key=key, status="open"))
            db.commit()
    finally:
        db.close()
    try:
        dash = client.get("/api/dashboard", headers=hdr).json()
        reported = next((dash[k] for k in DASH_KEYS if k in dash), None)
        assert (reported or 0) >= 1, "الصندوق فارغ — المقارنات فراغ"
    finally:
        db = SessionLocal()
        try:
            for tk in db.scalars(select(models.Task).where(
                    models.Task.dedup_key == key)).all():
                db.delete(tk)
            db.commit()
        finally:
            db.close()
