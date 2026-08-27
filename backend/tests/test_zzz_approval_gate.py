# -*- coding: utf-8 -*-
"""APP-01 — بوابة أزرار القرار: ما تعرضه الواجهة هو ما يقبله الخادم.

العطل: المعتمِد الحالي لا يرى اعتماد/رفض/إرجاع رغم أن الخادم يقبل قراره.
السبب أن الصلاحية تُحسب مرّتين بقاعدتين: الخادم يشترط صلاحية مجال الفئة
(``approve_leave`` …) والواجهة تشترط ``approve_request`` العامة المهجورة.

وخطر إصلاحه أنه **يُظهر أزراًرا كانت مخفيّة**. وبلاغ موثَّق سابق: مدير
الشركة اعتمد مرحلة مسؤول الفرع ثم مرحلته ثم مرحلة HR بحسابه وحده. فلا
يُعالَج «الأزرار مخفيّة» بإظهارها للجميع — ولهذا نصف هذه الاختبارات على
من **لا** يجب أن يرى.
"""
from __future__ import annotations

import pytest

from app import models, permissions, request_actions
from app.database import SessionLocal

from .conftest import auth_headers, login

EMPLOYEE = ("100000000101", "emp12345")
SUPERVISOR = ("100000000005", "sup12345")
MANAGER = ("100000000001", "manager123")
HR = ("100000000002", "hr12345")
OTHER_COMPANY_HR = ("200000000002", "hr12345")


@pytest.fixture
def pending_request(client):
    """طلب إجازة قائم بانتظار قرار — يُنشئه الموظف بنفسه."""
    tok = login(client, *EMPLOYEE)
    r = client.post("/api/requests", headers=auth_headers(tok), json={
        "request_type_code": "leave",
        "payload_json": {"leave_type": "annual", "start_date": "2026-10-01",
                         "end_date": "2026-10-03", "days": 3,
                         "reason": "اختبار بوابة الاعتماد"},
    })
    # لا تخطٍّ: البند مانع، واختبار يتخطّى نفسه يبدو أخضر ولا يثبت شيًئا.
    assert r.status_code in (200, 201), f"تعذّر إنشاء طلب: {r.text[:200]}"
    rid = r.json()["id"]
    yield rid
    db = SessionLocal()
    try:
        obj = db.get(models.Request, rid)
        if obj:
            db.query(models.RequestApproval).filter(
                models.RequestApproval.request_id == rid).delete()
            db.delete(obj)
            db.commit()
    finally:
        db.close()


def _detail(client, creds, rid):
    tok = login(client, *creds)
    r = client.get(f"/api/requests/{rid}", headers=auth_headers(tok))
    assert r.status_code == 200, r.text
    return r.json(), auth_headers(tok)


# ---------------------------------------------------------------------------
# 1) المعيَّن الحالي يرى أزراره
# ---------------------------------------------------------------------------
def test_current_approver_sees_actions(client, pending_request):
    """المعتمِد الفعليّ يرى أفعاله — وهذا هو البلاغ الأصلي."""
    body, _ = _detail(client, SUPERVISOR, pending_request)
    actions = body.get("allowed_actions") or []
    assert actions, (
        "المعتمِد الحالي لا يرى أي فعل — "
        f"السبب المعلن: {body.get('no_actions_reason')!r}"
    )
    names = {a["action"] for a in actions}
    assert {"approve", "reject"} <= names, f"أفعال ناقصة: {names}"


def test_actions_carry_their_decision_and_label(client, pending_request):
    """الواجهة لا تترجم فعًلا إلى قرار: الترجمة عندها قاعدة ثانية تنحرف."""
    body, _ = _detail(client, SUPERVISOR, pending_request)
    for a in body["allowed_actions"]:
        assert a["decision"] in ("approved", "rejected", "returned")
        assert a["label_ar"] and a["label_en"]


# ---------------------------------------------------------------------------
# 2) غير المعيَّن لا يراها ولا ينفّذها بالرابط المباشر
# ---------------------------------------------------------------------------
def test_non_assignee_sees_nothing_and_is_refused_directly(client, pending_request):
    """الإخفاء وحده ليس أماًنا: الرابط المباشر يجب أن يُرَدّ بـ403."""
    body, hdr = _detail(client, HR, pending_request)
    assert not (body.get("allowed_actions") or []), (
        "غير المعيَّن يرى أزراًرا — الإصلاح فتح ثغرة"
    )
    assert body.get("no_actions_reason"), "أُخفيت الأزرار بلا سبب معروض"

    direct = client.post(f"/api/requests/{pending_request}/decide",
                         headers=hdr, json={"decision": "approved", "note": ""})
    assert direct.status_code in (403, 409), (
        f"غير المعيَّن نفّذ القرار بالرابط المباشر: {direct.status_code}"
    )


def test_other_company_cannot_see_or_act(client, pending_request):
    """العزل بين الشركات يسبق كل شيء."""
    tok = login(client, *OTHER_COMPANY_HR)
    r = client.get(f"/api/requests/{pending_request}", headers=auth_headers(tok))
    assert r.status_code in (403, 404), "طلب شركة أخرى ظاهر"


# ---------------------------------------------------------------------------
# 3) لا اعتماد ذاتي
# ---------------------------------------------------------------------------
def test_requester_never_sees_decision_actions(client, pending_request):
    """أن يكون HR معتمِد مرحلة لا يعني أن يعتمد إجازته هو."""
    body, hdr = _detail(client, EMPLOYEE, pending_request)
    assert not (body.get("allowed_actions") or []), "صاحب الطلب يرى أزرار قراره"
    direct = client.post(f"/api/requests/{pending_request}/decide",
                         headers=hdr, json={"decision": "approved", "note": ""})
    assert direct.status_code in (403, 409)


# ---------------------------------------------------------------------------
# 4) الأزرار تختفي بعد انتقال المرحلة · 5) المهمة المنتهية مرفوضة
# ---------------------------------------------------------------------------
def test_actions_disappear_after_the_stage_moves(client, pending_request):
    """من قرّر لا يبقى صاحب قرار في المرحلة نفسها."""
    body, hdr = _detail(client, SUPERVISOR, pending_request)
    assert body["allowed_actions"]
    done = client.post(f"/api/requests/{pending_request}/decide",
                       headers=hdr, json={"decision": "approved", "note": "موافق"})
    assert done.status_code == 200, done.text

    after, _ = _detail(client, SUPERVISOR, pending_request)
    assert not (after.get("allowed_actions") or []), (
        "المعتمِد ما زال يرى أزراره بعد انتقال المرحلة"
    )


def test_repeated_click_produces_one_effect(client, pending_request):
    """الضغط المكرّر أثر واحد — لا مرحلتان بقرار واحد."""
    body, hdr = _detail(client, SUPERVISOR, pending_request)
    assert body["allowed_actions"]
    first = client.post(f"/api/requests/{pending_request}/decide",
                        headers=hdr, json={"decision": "approved", "note": "أ"})
    assert first.status_code == 200, first.text
    second = client.post(f"/api/requests/{pending_request}/decide",
                         headers=hdr, json={"decision": "approved", "note": "ب"})
    assert second.status_code != 200, "القرار نُفِّذ مرتين"

    db = SessionLocal()
    try:
        req = db.get(models.Request, pending_request)
        stage = req.current_stage
    finally:
        db.close()
    assert stage <= 2, f"تقدّمت المراحل أكثر من قرار واحد: {stage}"


# ---------------------------------------------------------------------------
# 6) لا تسلسل بحساب واحد — البلاغ الموثَّق
# ---------------------------------------------------------------------------
def test_manager_cannot_walk_the_whole_chain_alone(client, pending_request):
    """مدير الشركة اعتمد مرحلة مسؤول الفرع ثم مرحلته ثم HR بحسابه وحده.

    هذا ما لا يجوز أن يعود مع إظهار الأزرار.
    """
    body, hdr = _detail(client, MANAGER, pending_request)
    # المدير ليس معتمِد المرحلة الأولى (مسؤول الفرع)
    assert not (body.get("allowed_actions") or []), (
        "المدير يرى أزرار مرحلة غيره"
    )
    direct = client.post(f"/api/requests/{pending_request}/decide",
                         headers=hdr, json={"decision": "approved", "note": ""})
    assert direct.status_code in (403, 409), (
        "المدير اعتمد مرحلة مسؤول الفرع"
    )


# ---------------------------------------------------------------------------
# الجذر: قاعدة واحدة لا اثنتان
# ---------------------------------------------------------------------------
def test_actions_use_the_same_rule_as_the_decide_endpoint(client, pending_request):
    """ما يُعرَض هو ما يُقبَل — لكل دور، بلا استثناء.

    هذا هو الفحص الذي يمنع عودة العطل: أي انحراف بين القائمة والمسار
    يظهر هنا، لا في بلاغ عميل بعد شهر.
    """
    for creds in (SUPERVISOR, MANAGER, HR, EMPLOYEE):
        body, hdr = _detail(client, creds, pending_request)
        shown = bool(body.get("allowed_actions"))
        probe = client.post(f"/api/requests/{pending_request}/decide",
                            headers=hdr, json={"decision": "returned",
                                               "note": "فحص انحراف"})
        accepted = probe.status_code == 200
        assert shown == accepted, (
            f"انحراف للحساب {creds[0]}: الواجهة تعرض={shown} "
            f"والخادم يقبل={accepted} (ردّ {probe.status_code})"
        )
        if accepted:
            break            # الطلب تغيّر حاله — يكفي إثبات التطابق مرة


def test_frontend_carries_no_permission_logic_for_the_action_bar():
    """حارس: شريط الإجراءات لا يُبنى بشرط دور ولا صلاحية محسوبة.

    القاعدة في مكانين تنحرف. والحارس على المصدر لأن لا مشغّل اختبارات
    للواجهة.
    """
    import re
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "frontend" / "src" /
           "pages" / "RequestDetail.tsx")
    if not src.exists():
        pytest.skip("مصدر الواجهة غير موجود في هذه البيئة")
    text = src.read_text(encoding="utf-8")
    block = text[text.index("allowed_actions"):]
    block = block[:block.index("</div>")]
    for bad in ('can("approve_request")', "user?.role ===", "user.role ==="):
        assert bad not in block, (
            f"شريط الإجراءات يحسب الصلاحية محليًّا عبر {bad!r}"
        )


def test_approval_inbox_tab_is_not_gated_by_the_deprecated_permission():
    """صندوق «بانتظار موافقتي» لا يُحجب بـapprove_request العامة.

    العطل هنا أسبق من الأزرار: من لا يرى صندوقه لا يصل الطلب أصًلا. ونقطة
    الوصول محروسة بمجموعة صلاحيات القرار كاملة، فحكم الواجهة عليها زائد
    وينحرف.
    """
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "frontend" / "src" /
           "pages" / "Requests.tsx")
    if not src.exists():
        pytest.skip("مصدر الواجهة غير موجود في هذه البيئة")
    text = src.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.lstrip().startswith(("//", "*", "/*")):
            continue
        assert 'can("approve_request")' not in line, (
            f"صندوق القرار ما زال محجوًبا بصلاحية مهجورة: {line.strip()[:80]}"
        )


def test_deprecated_permission_is_not_what_the_server_requires():
    """توثيق الجذر: الخادم يشترط صلاحية مجال الفئة لا العامة.

    فحص على القاعدة نفسها: لو عاد أحد فجعل approve_request كافية، صار
    لمن يعتمد الإجازات سلطة على الخصومات والتظلّمات وإنهاء الخدمة.
    """
    assert "approve_request" in permissions.APPROVAL_PERMS
    for category, perm in permissions.DECISION_DOMAIN_BY_CATEGORY.items():
        assert perm != "approve_request", (
            f"فئة {category} تقبل الصلاحية العامة — عاد الخلط بين المجالات"
        )
