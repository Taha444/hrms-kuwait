# -*- coding: utf-8 -*-
"""BKL-03 — مهمة واحدة لكل إجراء، وإغلاق تلقائي، ولا يتيمة ولا مكرَّرة.

القياس على بيانات حقيقية كشف أن المهام **لا** تتكرّر — لكن **العدّاد
يكذب**: المسح اليومي كان يقول «وُلّدت 24 مهمة» في تشغيله الثاني وقد أنشأ
صفًرا. لأنه يعدّ ما مرّ عليه لا ما أنشأه، و``create_task`` تعيد المهمة
الموجودة عند التخطّي فلا يميّز المنادي الحالتين.

وهذا هو مصدر البلاغ: المشغّل يشغّل المسح فيقرأ رقًما كبيًرا كل مرة،
فيستنتج أن المهام تتكرّر. الرقم كان العطل لا المهام.
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app import models
from app.database import SessionLocal
from app.notifications import daily_scan
from app.routers.tasks import is_notification

from .conftest import auth_headers, login

EMPLOYEE = ("100000000101", "emp12345")
SUPERVISOR = ("100000000005", "sup12345")

TERMINAL = ("completed", "rejected", "cancelled")

#: عمل يبدأ **بعد** انتهاء الطلب ولا يموت بموته: المستند صدر ويجب أن يُطبع
#: ويُحفَظ في ملف الموظف. إغلاقه مع الطلب يُضيّع عمًلا قائًما — و«أغلِق كل
#: ما يتعلّق بالطلب» قاعدة تبدو نظيفة وتمحو مهامّ حقيقية. واليتيمة هي ما
#: فقد سببه، لا ما جاء بعده.
POST_CLOSURE_TASK_TYPES = {
    # المستند صدر ويجب أن يُطبع ويُحفَظ في ملف الموظف
    "ready_to_print", "file_document", "print_done", "file_done",
    # والأهم: **إخفاقات** تبقى بعد انتهاء الطلب. «فشل توليد مستند» على طلب
    # مكتمل ليست يتيمة بل بلاغ عطل: الطلب اعتُمد ومستنده لم يُولَّد.
    # إغلاقها مع الطلب يُخفي العطل ويجعل السجلّ يبدو نظيًفا وهو ليس كذلك.
    "document", "apply_failed",
}


def _count_tasks(db) -> int:
    return db.scalar(select(func.count()).select_from(models.Task)) or 0


def test_second_scan_creates_nothing_and_says_so():
    """جوهر البلاغ: الرقم يجب أن يصف ما حدث.

    كان يقول «وُلّدت 24» وقد أنشأ صفًرا — فيظنّ المشغّل أن المهام تتكرّر
    كل تشغيل، ويفتح بلاًغا عن تكرار لا وجود له.
    """
    db = SessionLocal()
    try:
        first = daily_scan(db)
        before = _count_tasks(db)
        second = daily_scan(db)
        after = _count_tasks(db)

        assert after == before, (
            f"المسح الثاني أنشأ {after - before} مهمة — تكرار حقيقي"
        )
        assert second["generated"] == 0, (
            f"المسح الثاني يقول «وُلّدت {second['generated']}» وقد أنشأ صفًرا"
        )
        assert first["generated"] >= 0
    finally:
        db.close()


def test_scan_counter_equals_actual_creations():
    """العدّ مشتقّ من الإنشاء لا من المرور.

    ولا يُفرَّغ الجدول لصنع الحالة: اختبارات أخرى تعتمد على المهام
    الموجودة، وتفريغه يُسقطها لسبب لا يخصّها ويشير إلى المكان الخطأ.
    والفرق بين قبل وبعد يقيس الشيء نفسه بلا هدم.
    """
    db = SessionLocal()
    try:
        before = _count_tasks(db)
        result = daily_scan(db)
        after = _count_tasks(db)
        assert result["generated"] == after - before, (
            f"العدّاد {result['generated']} والمُنشأ فعًلا {after - before}"
        )
    finally:
        db.close()


def test_no_duplicate_open_task_for_the_same_action():
    """مهمة واحدة لكل إجراء — على ما يُنتجه المسح، لا على الجدول كلّه.

    الجدول يحمل صفوًفا تُدرجها اختبارات أخرى مباشرًة بلا مفاتيح، وادّعاء
    يشملها يقيس بياناتها لا سلوك المنتج، ويسقط لسبب لا يخصّه.
    """
    db = SessionLocal()
    try:
        before = {i for (i,) in db.execute(select(models.Task.id)).all()}
        daily_scan(db)
        daily_scan(db)
        made = [t for t in db.scalars(select(models.Task)).all()
                if t.id not in before]
        seen = {}
        for tk in made:
            key = (tk.type, tk.assignee_user_id,
                   tk.related_entity_type, tk.related_entity_id)
            seen[key] = seen.get(key, 0) + 1
        dupes = {k: v for k, v in seen.items() if v > 1}
        assert not dupes, f"المسح أنشأ مهامّ مكرَّرة: {list(dupes.items())[:5]}"
    finally:
        db.close()


def test_scan_gives_every_task_it_creates_a_dedup_key():
    """بلا مفتاح لا يوجد ما يمنع التكرار — والمنع يصير صدفة.

    والقياس على ما يُنشئه المسح: صفوف الاختبارات الأخرى تُدرَج مباشرًة
    وليست من مسؤولية المنتج.
    """
    db = SessionLocal()
    try:
        db.query(models.Task).filter(models.Task.type == "__probe__").delete()
        before = {i for (i,) in db.execute(select(models.Task.id)).all()}
        daily_scan(db)
        made = [t for t in db.scalars(select(models.Task)).all()
                if t.id not in before]
        bad = [t for t in made if not t.dedup_key]
        assert not bad, (
            "المسح أنشأ مهامّ بلا مفتاح منع تكرار: "
            + str([(t.type, t.related_entity_type) for t in bad[:6]])
        )
    finally:
        db.close()


@pytest.fixture
def pending_request(client):
    hdr = auth_headers(login(client, *EMPLOYEE))
    r = client.post("/api/requests", headers=hdr, json={
        "request_type_code": "leave",
        "payload_json": {"leave_type": "annual", "start_date": "2027-03-01",
                         "end_date": "2027-03-02", "days": 2,
                         "reason": "اختبار نظافة المهام"}})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"], hdr


def _open_actionable(rid: int):
    """المهام المفتوحة التي تطلب إجراًء — لا الإشعارات."""
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid,
            models.Task.status.in_(("open", "in_progress")))).all()
        return [t for t in rows if not is_notification(t.type)]
    finally:
        db.close()


def test_rejecting_closes_the_open_action_tasks(client, pending_request):
    """طلب انتهى لا يترك مهمة تطلب إجراًء عليه."""
    rid, _ = pending_request
    assert _open_actionable(rid), "لا مهمة إجراء قبل القرار — لا شيء يُقاس"
    sup = auth_headers(login(client, *SUPERVISOR))
    r = client.post(f"/api/requests/{rid}/decide", headers=sup,
                    json={"decision": "rejected", "note": "غير موافق"})
    assert r.status_code == 200, r.text
    left = _open_actionable(rid)
    assert not left, f"مهام يتيمة بعد الرفض: {[t.type for t in left]}"


def test_the_rejection_notice_survives_the_cleanup(client, pending_request):
    """الحدّ المقابل: الإشعار خبر للموظف، وإغلاقه يحرمه من معرفة النتيجة.

    «أغلِق كل ما يتعلّق بالطلب» حلٌّ يمحو الإخطار مع المهمة.
    """
    rid, emp_hdr = pending_request
    sup = auth_headers(login(client, *SUPERVISOR))
    client.post(f"/api/requests/{rid}/decide", headers=sup,
                json={"decision": "rejected", "note": "غير موافق"})
    db = SessionLocal()
    try:
        notices = db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid,
            models.Task.type == "request_update")).all()
        assert notices, "لا إخطار للموظف بنتيجة طلبه"
        assert any(n.status == "open" for n in notices), (
            "أُغلق إخطار النتيجة مع المهام — الموظف لا يعرف ماذا جرى"
        )
    finally:
        db.close()


def test_no_progress_task_points_at_a_finished_request():
    """مسح شامل: لا يتيمة في القاعدة كلها."""
    db = SessionLocal()
    try:
        orphans = []
        for tk in db.scalars(select(models.Task).where(
                models.Task.status.in_(("open", "in_progress")),
                models.Task.related_entity_type == "request")).all():
            if is_notification(tk.type) or tk.type in POST_CLOSURE_TASK_TYPES:
                continue
            req = db.get(models.Request, tk.related_entity_id or 0)
            if req is None or req.status in TERMINAL:
                orphans.append(
                    f"مهمة #{tk.id} ({tk.type}) على طلب "
                    f"{req.status if req else 'محذوف'}")
        assert not orphans, "مهام مفتوحة لطلبات منتهية:\n" + "\n".join(orphans[:8])
    finally:
        db.close()


def test_open_counter_reflects_the_open_tasks(client):
    """العدّاد يتغيّر فوًرا: ما يُعدّ هو ما يُعرَض."""
    hdr = auth_headers(login(client, *SUPERVISOR))
    r = client.get("/api/tasks/count", headers=hdr)
    assert r.status_code == 200, r.text
    reported = r.json().get("open")
    listing = client.get("/api/tasks/my", headers=hdr, params={"status": "open"})
    assert listing.status_code == 200
    assert reported == len(listing.json()), (
        f"العدّاد {reported} والقائمة {len(listing.json())}"
    )


def test_post_closure_work_is_not_swept_away():
    """الحدّ المقابل: تنظيف يمحو مهامّ حقيقية أسوأ من ترك يتيمة.

    «جاهز للطباعة والحفظ» تبدأ بعد اكتمال الطلب لأن المستند صدر ويجب أن
    يُطبع ويُحفَظ في ملف الموظف. واليتيمة هي ما فقد سببه لا ما جاء بعده.
    """
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Task).where(
            models.Task.type.in_(tuple(POST_CLOSURE_TASK_TYPES)))).all()
        assert rows, (
            "لا مهام ما بعد الإغلاق إطلاًقا — إمّا لم تُنشأ أو ابتلعها التنظيف"
        )
        # يكفي أن يبقى بعضها مفتوًحا: بعضها أُنجز فعًلا في مسارات أخرى
        assert any(t.status in ("open", "in_progress") for t in rows), (
            "كل مهام ما بعد الإغلاق مغلقة — يُخشى أن التنظيف يبتلعها"
        )
    finally:
        db.close()
