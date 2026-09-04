# -*- coding: utf-8 -*-
"""P11-35 — الإقرار ليس اعتماًدا، والمعنى لا يُقاس بالـenum.

**ما ظهر بالقياس:**

``RequestApproval.decision`` ثلاث قيم (approved/rejected/returned) يفرّع
عليها المحرّك. والأفعال المعروضة على الأزرار **تسعة**: «اعتماد» و«رفض»
و«إرجاع» و«البيانات صحيحة» و«غير صحيحة» و«بدء التنفيذ» و«تمّ التنفيذ»
و«تعذّر» و«علمت» و«اعتراض».

والواجهة كانت ترسل ``a.decision`` وحده — فما فعله الإنسان يُهمَل لحظة
الضغط. من ضغط «البيانات صحيحة» يُسجَّل «اعتمد»، ويبقى كذلك للأبد.

**ولماذا يهمّ**: في نزاع عمّالي «اعتمدت الشؤون القانونية الخصم» دعوى
غير «تحقّقت من الأرقام». واللفظ الواحد يخلطهما بعد شهور بلا وسيلة
للتمييز — ونظام يُفترَض أن يُحتجّ بسجلّه.

**ولم تُوسَّع القيم**: توسيعها يكسر كل تفريع في المحرّك. الفعل يُحفَظ
إلى جانب أثره، ويُعرَض بلفظه.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models, request_actions, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")

# الحمولة من تعريف النموذج نفسه: نقصُ حقل يردّ 400 على التحقّق، فيبدو
# القياس ناجًحا في الرفض وهو لم يبلغ ما يقيسه.
BANK = {"bank_name": "بنك الخليج", "iban": "KW81CBKU0000000000001234560101",
        "account_holder": "الموظف الأول", "effective_month": "2026-11",
        "reason": "تغيير البنك", "_attachments": ["bank_letter"]}


def _stage_types() -> set[str]:
    return {st.get("step_type") or "DECISION"
            for rt in workflow.DEFAULT_REQUEST_TYPES
            for st in (rt.get("approval_chain_json") or [])}


def test_the_action_vocabulary_is_wider_than_the_decision_enum():
    """خطّ الأساس: المشكلة قائمة أصًلا — تسعة معانٍ في ثلاث قيم."""
    actions = set(request_actions.ACTION_DECISION)
    decisions = set(request_actions.ACTION_DECISION.values())
    assert len(actions) > len(decisions) + 3, (
        f"الأفعال {len(actions)} والقرارات {len(decisions)} — لا انهيار يُقاس"
    )
    # وأوضح موضع للانهيار: ثلاثة أفعال مختلفة المعنى تصير «اعتماد».
    to_approved = {a for a, d in request_actions.ACTION_DECISION.items()
                   if d == "approved"}
    assert {"approve", "valid", "complete"} <= to_approved, to_approved


def test_a_validation_step_is_not_recorded_as_an_approval(client):
    """**جوهر البند**: من تحقّق من البيانات لا يُسجَّل أنه اعتمد."""
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()

    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQBANK",
        "payload_json": BANK})
    assert r.status_code == 201, r.text[:250]
    rid = r.json()["id"]

    hh = auth_headers(login(client, *HR))
    body = client.get(f"/api/requests/{rid}", headers=hh).json()
    acts = body.get("allowed_actions") or []
    valid = [a for a in acts if a["action"] == "valid"]
    assert valid, f"المرحلة الأولى ليست تحقًّقا: {[a['action'] for a in acts]}"

    d = client.post(f"/api/requests/{rid}/decide", headers=hh,
                    json={"decision": "approved", "action": "valid"})
    assert d.status_code == 200, d.text[:200]

    db = SessionLocal()
    try:
        ap = db.scalar(select(models.RequestApproval).where(
            models.RequestApproval.request_id == rid))
    finally:
        db.close()
    assert ap.decision == "approved", "أثر المسار تغيّر — لم يكن المطلوب"
    assert ap.action == "valid", (
        f"ضاع الفعل ولم يبقَ إلا «اعتمد»: action={ap.action}"
    )


def test_the_screen_says_what_was_actually_done(client):
    """والشاشة تقول لفظ الفعل، لا لفظ أثره."""
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()
    hdr = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQBANK",
        "payload_json": BANK}).json()["id"]
    hh = auth_headers(login(client, *HR))
    client.post(f"/api/requests/{rid}/decide", headers=hh,
                json={"decision": "approved", "action": "valid"})

    body = client.get(f"/api/requests/{rid}", headers=hh).json()
    done = [s for s in body.get("stages", []) if s.get("action")]
    assert done, f"لا مرحلة تحمل فعًلا: {body.get('stages')}"
    assert done[0]["action_label"] == "البيانات صحيحة", done[0]


def test_a_forged_action_is_refused(client):
    """ولا يُصدَّق الفعل كما وصل: «علمت» على مرحلة قرار تحريف للمعنى."""
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()
    hdr = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQBANK",
        "payload_json": BANK}).json()["id"]

    hh = auth_headers(login(client, *HR))
    r = client.post(f"/api/requests/{rid}/decide", headers=hh,
                    json={"decision": "approved", "action": "acknowledge"})
    assert r.status_code == 400, (
        f"قُبل فعل ليس من أفعال المرحلة: {r.status_code}"
    )
    r2 = client.post(f"/api/requests/{rid}/decide", headers=hh,
                     json={"decision": "rejected", "action": "valid"})
    assert r2.status_code == 400, "قُبل فعل لا يطابق القرار المرسَل"


def test_omitting_the_action_still_works(client):
    """ومن يرسل القرار وحده لا يُكسر: الحقل اختياري."""
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()
    hdr = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQBANK",
        "payload_json": BANK}).json()["id"]
    hh = auth_headers(login(client, *HR))
    r = client.post(f"/api/requests/{rid}/decide", headers=hh,
                    json={"decision": "approved"})
    assert r.status_code == 200, r.text[:200]


def test_acknowledgement_is_unused_and_its_meaning_unsettled():
    """**الحارس**: أول سلسلة تستعمل الإقرار تُوقظ سؤاًلا غير محسوم.

    ``dispute`` مربوط بـ``rejected``: معناه أن اعتراض موظف على إنذار
    **يُسقط الطلب كلّه**. وقد يكون ذلك مقصوًدا وقد يكون العكس —
    والجواب قرار عمل لا استنتاج شيفرة.

    فيُحسم يوم يصير حقيقًيا، لا يوم يعترض موظف فيجد إنذاره قد أُلغي.
    """
    assert "ACKNOWLEDGEMENT" not in _stage_types(), (
        "سلسلة صارت تستعمل ACKNOWLEDGEMENT — احسم أوًلا: هل «اعتراض» "
        "يُسقط الطلب (dispute→rejected) أم يُسجَّل ويمضي المسار؟"
    )


def test_the_warning_flow_keeps_receipt_apart_from_agreement():
    """والإقرار الحيّ فعًلا مُحكَم: الاستلام ليس إقراًرا بالمضمون.

    ادّعاء المنع أعلاه بلا هذا يكون نصف قياس — قد يكون المعنى مفقوًدا
    في كل موضع لا في الميّت وحده.
    """
    from app import form_schemas

    schema = form_schemas.SCHEMAS["REQWARN"]
    # مفتاح الحقل ``code`` لا ``name`` — قرأتُه من التعريف بعد أن سقط الفحص.
    field = next(f for f in schema["fields"] if f["code"] == "acknowledgment")
    values = {o["value"] for o in field["options"]}
    assert {"acknowledge", "acknowledge_disagree", "dispute"} <= values, values

    text = workflow.REQUEST_OFFICIAL_TEXT["REQWARN"]
    assert "لا يعد" in text or "لا يعني" in text, text
