# -*- coding: utf-8 -*-
"""سباق الاعتماد والرفض — نتيجٌة عملية واحدة لا اثنتان.

**العطل المقيس على الإنتاج**: يصل اعتماٌد ورفض على المرحلة نفسها في
اللحظة نفسها، فيعود **كلاهما 200**، ويُسجَّل في الخطّ الزمني اعتماٌد
ورفض معًا، وتصير الحال النهائية «مكتمل» — **ويُولَّد مستٌند رسمي رغم
وجود رفض**. أي ورقٌة تُقدَّم إلى جهة وقد رُفض أصلها.

**والسبب بنيوي لا عرَضي**: كل حرّاس القرار «اقرأ ثم افحص» — الحالة،
والمرحلة، والقرار المكرَّر، والمعتمِد الفعلي — وكلها تقرأ قبل أن يكتب
أحد. فطلبان يقرآن الحال نفسها ويمرّان معًا. وزيادة فحص سادس لا تُصلح
شيًئا: العلّة أن الفحص والكتابة ليسا فعًلا واحًدا.

**والعلاج مطالبٌة ذرّية**: تحديٌث مشروط بالقيمة التي قُرئت. يفوز واحد،
ويجد الثاني شرطه كاذًبا.

**ولا يُستعمل قفل الصفّ**: SQLite — قاعدة الاختبارات — تتجاهل
``FOR UPDATE``، فتعمل الحماية في الإنتاج وتغيب عن القياس. وحمايٌة لا
تُقاس ليست حماية.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
SUP = ("100000000005", "sup12345")
HR = ("100000000002", "hr12345")


@pytest.fixture
def pending_leave(client):
    """طلب إجازة قائم عند مرحلته الأولى — ويُزال بعد القياس."""
    hdr = auth_headers(login(client, *EMP))
    start = date.today() + timedelta(days=20)
    r = client.post("/api/requests", headers=hdr, json={
        "request_type_code": "leave",
        "payload_json": {"leave_type": "unpaid", "days": 1,
                         "start_date": start.isoformat(),
                         "end_date": start.isoformat(),
                         "reason": "قياس السباق"}})
    assert r.status_code in (200, 201), r.text
    rid = r.json()["id"]
    yield rid

    db = SessionLocal()
    try:
        db.execute(sa_delete(models.RequestApproval).where(
            models.RequestApproval.request_id == rid))
        db.execute(sa_delete(models.Request).where(models.Request.id == rid))
        db.commit()
    finally:
        db.close()


def _state(rid: int):
    db = SessionLocal()
    try:
        req = db.get(models.Request, rid)
        decisions = db.scalars(select(models.RequestApproval).where(
            models.RequestApproval.request_id == rid,
            models.RequestApproval.decision.in_(("approved", "rejected", "returned")),
        )).all()
        return req.status, req.current_stage, [d.decision for d in decisions]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# المطالبة نفسها
# ---------------------------------------------------------------------------

def test_only_one_claim_wins_on_the_same_state(pending_leave):
    """**جوهر الإصلاح**: اثنان يقرآن الحال نفسها، ويفوز واحد."""
    db = SessionLocal()
    try:
        req = db.get(models.Request, pending_leave)
        seen_stage, seen_seq = req.current_stage, req.decision_seq
        first = workflow.claim_decision(db, req, seen_stage=seen_stage, seen_seq=seen_seq)
        db.commit()
        # الثاني يحمل **نفس** ما قرأه قبل فوز الأول — وهو حال السباق بالضبط.
        second = workflow.claim_decision(db, req, seen_stage=seen_stage, seen_seq=seen_seq)
        db.commit()
    finally:
        db.close()
    assert first is True, "لم يفز أحد"
    assert second is False, "فاز الاثنان — السباق قائم"


def test_a_claim_on_a_moved_stage_fails(pending_leave):
    """وقراٌر بُني على مرحلة تقدّمت لا يُكتب — ولو كان العدّاد يطابق."""
    db = SessionLocal()
    try:
        req = db.get(models.Request, pending_leave)
        ok = workflow.claim_decision(db, req, seen_stage=req.current_stage + 5,
                                     seen_seq=req.decision_seq)
        db.rollback()
    finally:
        db.close()
    assert ok is False


def test_a_claim_after_the_request_closed_fails(pending_leave):
    """وطلٌب أُغلق لا يقبل قراًرا متأخًرا مهما كان العدّاد."""
    db = SessionLocal()
    try:
        req = db.get(models.Request, pending_leave)
        req.status = "rejected"
        db.commit()
        ok = workflow.claim_decision(db, req, seen_stage=req.current_stage,
                                     seen_seq=req.decision_seq)
        db.rollback()
        req = db.get(models.Request, pending_leave)
        req.status = "pending"
        db.commit()
    finally:
        db.close()
    assert ok is False


# ---------------------------------------------------------------------------
# السباق الحقيقي عبر المسار
# ---------------------------------------------------------------------------

def test_approve_and_reject_together_produce_one_outcome(client, pending_leave):
    """**النتيجة العملية واحدة**: لا اعتماٌد ورفٌض على الطلب نفسه.

    ويُحاكى السباق كما يقع: طرٌف قرأ الحال، ثم قرّر الآخر وكُتب قراره،
    ثم جاء الأول يكتب على حاٍل لم تعد قائمة.
    """
    sup = auth_headers(login(client, *SUP))

    # الطرف «البطيء» يقرأ الحال ويحتفظ بها.
    db = SessionLocal()
    try:
        req = db.get(models.Request, pending_leave)
        stale_stage, stale_seq = req.current_stage, req.decision_seq
    finally:
        db.close()

    # الطرف الأسرع يقرّر فعًلا عبر المسار.
    first = client.post(f"/api/requests/{pending_leave}/decide", headers=sup,
                        json={"decision": "approved", "note": "الأسرع"})
    assert first.status_code == 200, first.text

    # ثم يحاول الأول الكتابة بما قرأه — وهذا هو الخاسر في السباق.
    db = SessionLocal()
    try:
        req = db.get(models.Request, pending_leave)
        late = workflow.claim_decision(db, req, seen_stage=stale_stage,
                                       seen_seq=stale_seq)
        db.rollback()
    finally:
        db.close()
    assert late is False, "قراٌر متأخّر كُتب فوق قرار سابق"

    status, _stage, decisions = _state(pending_leave)
    assert decisions.count("approved") <= 1
    assert "rejected" not in decisions, f"اجتمع اعتماٌد ورفض: {decisions}"


def test_the_late_decision_is_refused_through_the_endpoint(client, pending_leave):
    """وقراٌر ثاٍن على مرحلة أُغلقت يُردّ بـ409 لا بـ200."""
    sup = auth_headers(login(client, *SUP))
    assert client.post(f"/api/requests/{pending_leave}/decide", headers=sup,
                       json={"decision": "rejected", "note": "رفض"}).status_code == 200

    again = client.post(f"/api/requests/{pending_leave}/decide", headers=sup,
                        json={"decision": "approved", "note": "متأخّر"})
    assert again.status_code == 409, again.text

    status, _s, decisions = _state(pending_leave)
    assert status == "rejected"
    assert decisions == ["rejected"], decisions


def test_the_loser_of_a_race_is_written_in_the_audit(client, pending_leave):
    """**وسباٌق بلا أثر لا يُحقَّق فيه** — فالخاسر يُسجَّل."""
    import inspect

    from app.routers import requests as R

    src = inspect.getsource(R.decide)
    assert "request_decision_conflict" in src, "الخاسر يُهمَل بلا تسجيل"
    assert "claim_decision" in src, "لا مطالبة ذرّية في المسار"
    # والمطالبة **بعد** كل الفحوص وقبل أي أثر.
    assert src.index("claim_decision") < src.index("workflow.decide(")


def test_no_row_lock_is_relied_upon():
    """**وحمايٌة تعمل في الإنتاج وتغيب عن الاختبار ليست حماية.**

    ``FOR UPDATE`` تتجاهله SQLite، فلو بُني عليه الإصلاح لمرّت
    الاختبارات خضراء والسباق حيّ في القياس المحلّي.
    """
    import inspect

    src = inspect.getsource(workflow.claim_decision)
    # **الشرح يذكر ما لا يُستعمَل** — فيُفصَل عن الكود قبل القياس، وإلا
    # أمسك الاختبارُ نصَّه هو. (وقع ذلك فعًلا في أول تشغيل.)
    body = src.replace(workflow.claim_decision.__doc__ or "", "")
    assert "with_for_update" not in body and "FOR UPDATE" not in body
    assert "rowcount" in body, "لا يُقاس فوز المطالبة"
