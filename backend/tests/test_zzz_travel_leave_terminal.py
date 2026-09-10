# -*- coding: utf-8 -*-
"""إجازة السفر تصل إلى نهايتها — لا تقف عند المندوب.

**العطل المقيس**: توجيه السفر صار صحيًحا (``WF-002``)، لكن الطلب يقف عند
``awaiting_delegate``. المندوب يراه في صندوقه و:

    can_current_user_decide: false
    allowed_actions: []
    decide → 409

ولا الموارد ولا المدير ولا الإدارة العليا يكملونه.

**والسبب**: المرحلة ``delegate_exit`` **تُنفَّذ ولا تُقرَّر** — تكتمل برفع
إذن المغادرة لا بضغط «اعتماد». والخادم يعرف ذلك ويردّ الاعتماد صراحًة.
لكن ``allowed_actions`` تُبنى من ``step_type`` وحده، وهذه المرحلة بلا
``step_type`` — فتسقط إلى أفعال القرار، ثم يمنعها الحارس، فتعود فارغة.

فالنتيجة: **مرحلٌة لها مخرٌج واحد، والشاشة لا تذكره**. والمستخدم أمام
صندوق فيه طلب لا يملك له فعًلا، ورسالة تقول «لست المعتمِد» وهو المعتمِد.
"""
from __future__ import annotations

import io
import pathlib
from datetime import date, timedelta

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models, workflow
from app.database import SessionLocal
from app.task_kinds import is_notification
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
SUP = ("100000000005", "sup12345")
HR = ("100000000002", "hr12345")
PRO = ("100000000003", "deleg123")


def _pdf():
    return {"file": ("exit.pdf", io.BytesIO(b"%PDF-1.4 exit permit"), "application/pdf")}


@pytest.fixture
def travel(client):
    """إجازة سفر مقدَّمة ومعتمَدة حتى مرحلة المندوب."""
    hdr = auth_headers(login(client, *EMP))
    start = date.today() + timedelta(days=25)
    r = client.post("/api/requests", headers=hdr, json={
        "request_type_code": "leave",
        "payload_json": {"leave_type": "unpaid", "days": 2,
                         "start_date": start.isoformat(),
                         "end_date": (start + timedelta(days=1)).isoformat(),
                         "travel_required": True, "destination": "القاهرة",
                         "reason": "قياس مسار السفر"}})
    assert r.status_code in (200, 201), r.text
    rid = r.json()["id"]

    for creds in (SUP, HR):
        h = auth_headers(login(client, *creds))
        d = client.post(f"/api/requests/{rid}/decide", headers=h,
                        json={"decision": "approved", "note": "تمّ"})
        assert d.status_code == 200, (creds[0], d.text)

    yield rid

    db = SessionLocal()
    try:
        # الإجازة المكتملة تُنشئ صف رصيد، والموعد يشير إلى الطلب أيًضا. فيُزال
        # ما يشير إليه قبله، وإلا سقط التنظيف بقيد مفتاح أجنبي وترك القاعدة
        # ملوَّثة لما بعده.
        db.execute(sa_delete(models.Leave).where(models.Leave.request_id == rid))
        db.execute(sa_delete(models.Appointment).where(
            models.Appointment.request_id == rid))
        db.execute(sa_delete(models.RequestDocument).where(
            models.RequestDocument.request_id == rid))
        db.execute(sa_delete(models.RequestApproval).where(
            models.RequestApproval.request_id == rid))
        db.execute(sa_delete(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid))
        db.execute(sa_delete(models.Request).where(models.Request.id == rid))
        db.commit()
    finally:
        db.close()


def _stage_kind(rid: int) -> str:
    db = SessionLocal()
    try:
        req = db.get(models.Request, rid)
        rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
        chain = workflow._chain(rt, req)
        if not (0 <= req.current_stage < len(chain)):
            return f"(خارج السلسلة: {req.current_stage}/{len(chain)})"
        return chain[req.current_stage].get("kind") or "?"
    finally:
        db.close()


def test_the_travel_request_reaches_the_delegate(client, travel):
    """خطّ الأساس: السفر يصل إلى مرحلة المندوب لا يقف قبلها."""
    assert _stage_kind(travel) == "delegate_exit", _stage_kind(travel)
    d = client.get(f"/api/requests/{travel}",
                   headers=auth_headers(login(client, *PRO))).json()
    assert d["status"] == "awaiting_delegate", d["status"]


def test_the_delegate_is_told_what_this_stage_needs(client, travel):
    """**جوهر العطل**: مرحلٌة لها مخرٌج واحد والشاشة لا تذكره.

    فالمندوب أمام طلب في صندوقه بلا فعل، ورسالٍة تقول «لست المعتمِد»
    وهو المعتمِد — والمخرج رفع إذن المغادرة لا الاعتماد.
    """
    d = client.get(f"/api/requests/{travel}",
                   headers=auth_headers(login(client, *PRO))).json()
    actions = [a["action"] for a in (d.get("allowed_actions") or [])]
    reason = d.get("no_actions_reason") or ""
    # إمّا فعٌل صريح، وإمّا سبٌب يدلّ على ما يلزم — لا فراغ صامت.
    assert actions or "إذن" in reason or "مغادرة" in reason, (
        f"لا فعل ولا دلالة: actions={actions} reason={reason!r}")


def test_uploading_the_exit_permit_completes_the_stage(client, travel):
    """**والمخرج يعمل**: رفع إذن المغادرة يتقدّم بالطلب."""
    pro = auth_headers(login(client, *PRO))
    r = client.post(f"/api/requests/{travel}/documents", headers=pro,
                    data={"kind": "exit_permit"}, files=_pdf())
    assert r.status_code == 200, r.text
    assert _stage_kind(travel) != "delegate_exit", "بقي عند المندوب بعد الرفع"


def test_only_the_delegate_may_upload_the_exit_permit(client, travel):
    """وإذن المغادرة عمٌل حكومي: لا يرفعه من ليس مندوًبا."""
    emp = auth_headers(login(client, *EMP))
    r = client.post(f"/api/requests/{travel}/documents", headers=emp,
                    data={"kind": "exit_permit"}, files=_pdf())
    assert r.status_code == 403, r.text


def test_the_request_reaches_a_terminal_state(client, travel):
    """**والرحلة تُقطَع إلى آخرها**: مندوب ← استلام ← إغلاق."""
    pro = auth_headers(login(client, *PRO))
    assert client.post(f"/api/requests/{travel}/documents", headers=pro,
                       data={"kind": "exit_permit"}, files=_pdf()).status_code == 200

    hr = auth_headers(login(client, *HR))
    rec = client.post(f"/api/requests/{travel}/received", headers=hr)
    assert rec.status_code == 200, rec.text

    db = SessionLocal()
    try:
        req = db.get(models.Request, travel)
        status, closed = req.status, req.closed_at
    finally:
        db.close()
    assert status in ("completed", "done", "closed"), status
    assert closed is not None, "بلغ نهايته ولم يُغلَق"


def test_no_open_task_survives_completion(client, travel):
    """ومهامّه تُقفَل: مهمٌة مفتوحة على طلب منتهٍ عمٌل وهمي في الصندوق."""
    pro = auth_headers(login(client, *PRO))
    client.post(f"/api/requests/{travel}/documents", headers=pro,
                data={"kind": "exit_permit"}, files=_pdf())
    client.post(f"/api/requests/{travel}/received",
                headers=auth_headers(login(client, *HR)))

    db = SessionLocal()
    try:
        open_tasks = db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == travel,
            models.Task.status.in_(("open", "in_progress")),
        )).all()
        # **الإخطار يُقرأ ولا يُنجَز** (TSK-03): «اكتمل طلبك» يبقى مفتوًحا
        # بحقّ، وكنسُه يحرم الموظف من معرفة ما جرى بطلبه. والمقيس هنا العمل
        # وحده: مهمة المندوب التي وقع عملها فعًلا.
        titles = [f"{t.type}:{t.title}" for t in open_tasks
                  if not is_notification(t.type)]
    finally:
        db.close()
    assert not titles, f"مهام مفتوحة بعد الإغلاق: {titles}"


# ---------------------------------------------------------------------------
# P11-36 — الشاشة تعرض ما يقبله الخادم، في ما يُنفَّذ كما في ما يُقرَّر
# ---------------------------------------------------------------------------

def test_the_delegate_is_offered_the_upload_not_a_decision(client, travel):
    """المخرج يُوصَف بحقيقته: مستنٌد يُرفَع، لا قراٌر يُرسَل إلى /decide."""
    d = client.get(f"/api/requests/{travel}",
                   headers=auth_headers(login(client, *PRO))).json()
    acts = d["allowed_actions"]
    assert [a["action"] for a in acts] == ["upload_exit_permit"], acts
    assert acts[0]["via"] == "upload" and acts[0]["doc_kind"] == "exit_permit"
    assert acts[0]["decision"] is None, "وُصف كقرار وهو ليس قراًرا"


def test_direct_approval_is_refused_and_says_why(client, travel):
    """ولا يُفتَح باٌب جديد — **والردّ يقول ما يُفعل**.

    كان يردّ «لا يمكن اتخاذ قرار في هذه الحالة»: لا يقول ما الحال ولا ما
    يُفعل. وكانت الجملة الصحيحة مكتوبًة أسفل ذلك الحارس فلا يبلغها نداء.
    """
    r = client.post(f"/api/requests/{travel}/decide",
                    headers=auth_headers(login(client, *PRO)),
                    json={"decision": "approved", "note": "محاولة"})
    assert r.status_code == 409, r.text
    assert "إذن المغادرة" in r.json()["detail"], r.json()


def test_whoever_is_not_offered_the_action_is_refused_by_the_server(client, travel):
    """**والعكس محروٌس**: من لا يُعرَض له الفعل يردّه الخادم.

    وهذا هو شرط APP-01: لا زٌر بلا صلاحية ولا صلاحيٌة بلا زر. ولو انحرف
    الطرفان لعاد العطل مقلوًبا — زٌر يُعرَض ويُردّ.
    """
    emp = auth_headers(login(client, *EMP))
    d = client.get(f"/api/requests/{travel}", headers=emp).json()
    assert d["allowed_actions"] == []
    assert client.post(f"/api/requests/{travel}/documents", headers=emp,
                       data={"kind": "exit_permit"}, files=_pdf()).status_code == 403


def test_a_stage_that_is_executed_says_so_instead_of_falling_silent(client, travel):
    """ومن ليس المنفّذ يُقرأ له السبب — لا فراٌغ يُقرأ كشاشة معطَّلة."""
    d = client.get(f"/api/requests/{travel}",
                   headers=auth_headers(login(client, *EMP))).json()
    reason = d.get("no_actions_reason") or ""
    assert "إذن المغادرة" in reason, reason


def test_the_pickup_stage_offers_its_own_action(client, travel):
    """ومرحلة الاستلام مثلها: نداُء مساٍر لا قرار."""
    client.post(f"/api/requests/{travel}/documents",
                headers=auth_headers(login(client, *PRO)),
                data={"kind": "exit_permit"}, files=_pdf())
    assert _stage_kind(travel) == "pickup", _stage_kind(travel)
    d = client.get(f"/api/requests/{travel}",
                   headers=auth_headers(login(client, *HR))).json()
    acts = d["allowed_actions"]
    assert [a["action"] for a in acts] == ["confirm_received"], acts
    assert acts[0]["via"] == "post" and acts[0]["path"] == "received"


def test_the_screen_computes_no_permission_of_its_own(client):
    """**ولا قاعدة ثانية في الواجهة.**

    كان حقل إذن المغادرة مشروًطا بـ``role === "delegate"`` نًصّا، وزرّ
    الاستلام بـ``approve_request`` — وهي موصوفة في ``request_actions``
    نفسه بأنها مهجورة. فمن يملك الاستلام بصلاحية مجاله لم يجد زًرا.
    وشرٌط محلّي هنا اليوم ينحرف عن الخادم غًدا.
    """
    src = (pathlib.Path(__file__).resolve().parents[2]
           / "frontend" / "src" / "pages" / "RequestDetail.tsx").read_text(encoding="utf-8")
    assert 'status === "awaiting_delegate"' not in src, "شرط دور محلّي عاد"
    assert 'status === "ready_for_pickup"' not in src, "شرط صلاحية محلّي عاد"
    assert 'a.via === "upload"' in src and 'a.via === "post"' in src, \
        "الواجهة لا تقرأ «كيف» يقع الفعل من الخادم"


def test_the_delegates_task_closes_when_his_work_is_done(client, travel):
    """**ومهمٌة على عمل وقع تُغلَق حين يقع** — لا حين يُغلَق الطلب.

    مهمة المندوب («إجراءات إذن مغادرة البلاد») تُنشأ عند دخول مرحلته،
    و``_close_open_tasks`` لا تُدعى إلا في الحالات النهائية. فبين رفع
    الإذن وتسجيل الاستلام تبقى في صندوقه مهمٌة لعمٍل أنجزه — وقد يمتدّ
    ذلك أياًما. وصندوٌق فيه عمٌل منتهٍ يُقرأ كتأخّر، فيُهمَل كلّه.
    """
    client.post(f"/api/requests/{travel}/documents",
                headers=auth_headers(login(client, *PRO)),
                data={"kind": "exit_permit"}, files=_pdf())
    assert _stage_kind(travel) == "pickup", "لم يتقدّم فلا يُقاس ما بعده"

    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == travel,
            models.Task.status.in_(("open", "in_progress")),
        )).all()
        stale = [f"{t.type}:{t.dedup_key}" for t in rows
                 if not is_notification(t.type) and t.dedup_key
                 and t.dedup_key.startswith("req_exit:")]
    finally:
        db.close()
    assert not stale, f"مهمة المندوب باقية بعد إنجاز عمله: {stale}"


# ---------------------------------------------------------------------------
# P11-36 — الأخ المجاور: مرحلة التوقيع كانت بلا حارس
# ---------------------------------------------------------------------------

@pytest.fixture
def at_signature(client, travel):
    """يضع الطلب في حال انتظار التوقيع — قياس الحارس لا قياس التقدّم."""
    db = SessionLocal()
    try:
        req = db.get(models.Request, travel)
        was = req.status
        req.status = "awaiting_signature"
        db.commit()
    finally:
        db.close()
    yield travel
    db = SessionLocal()
    try:
        req = db.get(models.Request, travel)
        if req:
            req.status = was
            db.commit()
    finally:
        db.close()


def test_the_owner_of_the_request_cannot_sign_it_through(client, at_signature):
    """**بواٌب كان بلا حارس.**

    رفع «النسخة الموقّعة» يتقدّم بالطلب عبر مرحلة التوقيع، وكان بلا فحص
    فاعٍل أصًلا — بخلاف أخيه المجاور (إذن المغادرة) المحروس. فكل من يرى
    الطلب، **ومنهم صاحبه**، يتخطّى التوقيع برفع أيّ ملف: توقيٌع في السجلّ
    لم يقع في الواقع.
    """
    r = client.post(f"/api/requests/{at_signature}/documents",
                    headers=auth_headers(login(client, *EMP)),
                    data={"kind": "signed_scan"}, files=_pdf())
    assert r.status_code == 403, r.text


def test_the_signature_stage_offers_its_action_to_whoever_owns_it(client, at_signature):
    """ومن يملكها يجدها معروضة — لا مخفيًّة خلف صلاحية مهجورة."""
    d = client.get(f"/api/requests/{at_signature}",
                   headers=auth_headers(login(client, *HR))).json()
    acts = d["allowed_actions"]
    assert [a["action"] for a in acts] == ["upload_signed_scan"], acts
    assert acts[0]["via"] == "upload" and acts[0]["doc_kind"] == "signed_scan"

    # ولصاحب الطلب سبٌب أخصّ: لا نقص صلاحية بل منع اعتماد ذاتي.
    e = client.get(f"/api/requests/{at_signature}",
                   headers=auth_headers(login(client, *EMP))).json()
    assert e["allowed_actions"] == []
    assert "بنفسك" in (e.get("no_actions_reason") or ""), e.get("no_actions_reason")
