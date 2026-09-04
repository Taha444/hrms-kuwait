# -*- coding: utf-8 -*-
"""P11-34 — لكل حالة دخول ومخرج، والصامتة أسوأ من الظاهرة.

**ما ظهر بالقياس** (أفشلتُ تطبيق الأثر على طلب تحديث بيانات اتصال):

1. الحالة ``apply_failed`` بلا مخرج: ``allowed_actions`` فارغة،
   و``no_actions_reason`` فارغ — شاشة صامتة أمام طلب اعتُمد ولم يقع
   أثره. واللافتة تقول «يحتاج إجراء» ولا إجراء موجود. والإلغاء محجوز
   للمدير العام، فلمن تلقّى بلاغ الفشل الطلبُ جدار.

2. ومهمة الفشل ``critical`` كانت تُنشأ ثم تُكنَس في المعاملة نفسها —
   قرأتُها ``dismissed``. ``_close_open_tasks`` يغلق مهام طلب بلغ حالة
   **نهائية**، وهذه ليست نهائية (``closed_at=None``)، وكان النداء يأتي
   بعد الإنشاء لا قبله.

فالطلب يبقى مفتوًحا ظاهًرا وميًتا فعًلا، ولا أحد يُبلَّغ — وهو النمط
نفسه الذي ظهر في «جاهز للطباعة» (P1-03).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import select

from app import models, request_effects, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")

CONTACT = {"new_phone": "99887766"}


@pytest.fixture
def failing_effect(monkeypatch):
    """يُفشل تطبيق الأثر — الحالة لا تُبلَغ بغير ذلك."""
    monkeypatch.setattr(request_effects, "apply_field_effect",
                        lambda db, req: (False, "سبب اختباري للفشل"))


def _stuck_request(client) -> int:
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQCONTACT",
        "payload_json": CONTACT})
    assert r.status_code == 201, r.text[:200]
    rid = r.json()["id"]
    hh = auth_headers(login(client, *HR))
    d = client.post(f"/api/requests/{rid}/decide", headers=hh,
                    json={"decision": "approved"})
    assert d.status_code == 200, d.text[:200]
    return rid


def test_the_request_really_gets_stuck(client, failing_effect):
    """خطّ الأساس: بلا حالة عالقة فعًلا يكون ما بعدها قياًسا على فراغ."""
    rid = _stuck_request(client)
    hh = auth_headers(login(client, *HR))
    body = client.get(f"/api/requests/{rid}", headers=hh).json()
    assert body["status"] == "apply_failed", body["status"]


def test_the_critical_task_survives(client, failing_effect):
    """**العطل الأول**: مهمة تُنشأ وتُقتل في المعاملة نفسها ليست بلاًغا."""
    rid = _stuck_request(client)
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid,
            models.Task.type == "apply_failed")).all()
    finally:
        db.close()
    assert rows, "لم تُنشأ مهمة الفشل أصًلا"
    assert any(t.status in ("open", "in_progress") for t in rows), (
        f"أُنشئت ثم كُنست فوًرا: {[t.status for t in rows]}"
    )
    assert any(t.severity == "critical" for t in rows)


def test_the_stage_tasks_still_close(client, failing_effect):
    """ومهام المراحل تُغلق: الاعتماد تمّ، والذي فشل بعده.

    إعفاء الكلّ من الكنس يترك مهام اعتماد مفتوحة على مرحلة انتهت.
    """
    rid = _stuck_request(client)
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid,
            models.Task.type == "request_stage")).all()
    finally:
        db.close()
    assert rows, "لا مهام مراحل — القياس فارغ"
    assert all(t.status == "dismissed" for t in rows), (
        "بقيت مهمة اعتماد مفتوحة على مرحلة انتهت: "
        f"{[(t.type, t.status) for t in rows]}"
    )


def test_the_screen_stops_being_silent(client, failing_effect):
    """**العطل الثاني**: لا أفعال ولا سبب — يُقرأ الطلب ماضًيا في طريقه."""
    rid = _stuck_request(client)
    hh = auth_headers(login(client, *HR))
    body = client.get(f"/api/requests/{rid}", headers=hh).json()
    reason = body.get("no_actions_reason")
    assert reason, "شاشة صامتة أمام طلب متعثّر"
    assert "أعد التطبيق" in reason, reason


def test_the_employee_is_told_it_is_being_handled(client, failing_effect):
    """ومن لا يملك الإصلاح يُقال له من يتولّاه — لا الصمت ولا زر معطَّل."""
    rid = _stuck_request(client)
    eh = auth_headers(login(client, *EMP))
    body = client.get(f"/api/requests/{rid}", headers=eh).json()
    reason = body.get("no_actions_reason") or ""
    assert "الشؤون القانونية" in reason, reason


def test_there_is_a_way_out(client, failing_effect, monkeypatch):
    """**جوهر البند**: الحالة لها مخرج، والمخرج يعمل."""
    rid = _stuck_request(client)
    hh = auth_headers(login(client, *HR))

    # يُصحَّح سبب الفشل، ثم تُعاد المحاولة من الباب نفسه.
    monkeypatch.setattr(request_effects, "apply_field_effect",
                        lambda db, req: (True, "طُبّق بعد التصحيح"))
    r = client.post(f"/api/requests/{rid}/retry-apply", headers=hh)
    assert r.status_code == 200, r.text[:200]
    assert r.json()["status"] == "completed", r.json()


def test_a_failing_retry_keeps_the_state_and_the_reason(client, failing_effect):
    """وإعادة المحاولة لا تُخفي العطل: الفشل يبقى فشًلا."""
    rid = _stuck_request(client)
    hh = auth_headers(login(client, *HR))
    r = client.post(f"/api/requests/{rid}/retry-apply", headers=hh)
    assert r.status_code == 200, r.text[:200]
    assert r.json()["status"] == "apply_failed", r.json()


def test_retry_is_not_a_back_door_on_healthy_requests(client):
    """ولا يُستعمل على طلب سليم: إعادة تطبيق أثر مطبَّق تكراره."""
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()
    hdr = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQCONTACT",
        "payload_json": CONTACT}).json()["id"]
    hh = auth_headers(login(client, *HR))
    r = client.post(f"/api/requests/{rid}/retry-apply", headers=hh)
    assert r.status_code == 409, (
        f"قُبلت إعادة تطبيق على طلب غير متعثّر: {r.status_code}"
    )


def test_only_who_is_told_can_fix(client, failing_effect):
    """ومن لا يتلقّى البلاغ لا يُعيد التطبيق: البلاغ والصلاحية معًا."""
    rid = _stuck_request(client)
    eh = auth_headers(login(client, *EMP))
    r = client.post(f"/api/requests/{rid}/retry-apply", headers=eh)
    assert r.status_code in (403, 404), r.status_code


def test_every_declared_status_has_an_entry_and_an_exit():
    """**الحارس الجامع**: حالة تُعلَن ولا يُدخَل إليها أو لا يُخرَج منها.

    القياس على المصدر لا على قائمة يدوية: حالة تُضاف غًدا بلا مخرج
    تسقط هنا يوم تُضاف، لا يوم يعلق فيها طلب عميل.
    """
    src = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (Path(__file__).resolve().parents[1] / "app").rglob("*.py"))
    # حالات نهائية بطبعها — لا يُخرَج منها ولا يُنتظر ذلك.
    terminal = {"completed", "rejected", "cancelled"}

    no_entry, no_exit = [], []
    for st in workflow.STATUS_MAP:
        if not re.search(r"\.status\s*=\s*[\"']" + st + r"[\"']", src):
            no_entry.append(st)
        if st in terminal:
            continue
        # مخرج = تُقرأ الحالة في شرط يقود إلى تصرّف
        if not re.search(r"status\s*(?:==|!=|in)\s*[\(\[]?\s*[\"']?" + st, src):
            no_exit.append(st)

    assert not no_entry, f"حالات معلَنة لا يُدخَل إليها: {no_entry}"
    assert not no_exit, f"حالات لا مخرج منها: {no_exit}"
