# -*- coding: utf-8 -*-
"""P11-36 — الخطّ الزمني يقول من فعل حًقا.

**ثلاثة أعطال مقيسة بجلسة انتحال واحدة** (مدير النظام ينتحل شخصية موظف
الشؤون القانونية ثم يعتمد طلًبا):

1. ``RequestApproval`` سجّل المنتحَل وحده. فمن يقرأ الطلب بعد شهور يقرأ
   أن الشؤون القانونية اعتمدت — وهو الاسم الباقي أمام المراجع.
2. سجلّ التدقيق كان يحمل الحقيقة (``user_id=4``، ``original_user_id=1``)
   و**قارئه لا يعرضها**: ``by`` وحده. بيانات موجودة وقارئ يُخفيها.
3. وثلاث كتابات تدقيق في ``workflow`` تُثبّت ``user_id=None`` يدًوا،
   فتُقرأ ``by_system: True`` — «أكمله النظام» بينما أكمله ضغطة الأدمن
   في المعاملة نفسها التي سجّلت ``request_approved`` باسمه. وسياق
   الفاعل (``audit_context``) بُني لهذه الحالة بالذات ولم يكن يُقرأ.
"""
from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")
SUPER = ("000000000000", "admin123")
OWNER = ("111111111111", "owner123")     # يملك view_audit

CERT = {"purpose": "بنك", "reason": "فتح حساب",
        "language": "ar", "addressed_to": "بنك الخليج"}


def _approve_while_impersonating(client) -> tuple[int, int, int]:
    """يعتمد طلًبا بانتحال شخصية HR. يعيد (الطلب، معرّف HR، معرّف الأدمن)."""
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
        hr_id = db.scalar(select(models.User.id).where(
            models.User.civil_id == HR[0]))
        adm_id = db.scalar(select(models.User.id).where(
            models.User.civil_id == SUPER[0]))
    finally:
        db.close()

    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQCERTSAL",
        "payload_json": CERT})
    assert r.status_code == 201, r.text[:200]
    rid = r.json()["id"]

    ah = auth_headers(login(client, *SUPER))
    imp = client.post(f"/api/users/{hr_id}/impersonate", headers=ah,
                      params={"reason": "دعم فني"})
    assert imp.status_code == 200, f"تعذّر الانتحال: {imp.text[:200]}"
    ih = auth_headers(imp.json()["access_token"])

    d = client.post(f"/api/requests/{rid}/decide", headers=ih,
                    json={"decision": "approved"})
    assert d.status_code == 200, d.text[:200]
    return rid, hr_id, adm_id


def test_the_impersonation_really_happened(client):
    """خطّ الأساس: بلا انتحال فعلي يكون ما بعده قياًسا على لا شيء."""
    rid, hr_id, adm_id = _approve_while_impersonating(client)
    assert hr_id != adm_id
    db = SessionLocal()
    try:
        ap = db.scalars(select(models.RequestApproval).where(
            models.RequestApproval.request_id == rid)).all()
    finally:
        db.close()
    assert ap, "لا قرار مسجَّل"
    assert ap[0].approver_user_id == hr_id, (
        f"القرار لم يقع تحت هوية HR: {ap[0].approver_user_id}"
    )


def test_the_decision_records_who_actually_pressed_it(client):
    """**جوهر البند**: القرار يحمل الفاعل الحقيقي، لا الاسم وحده."""
    rid, hr_id, adm_id = _approve_while_impersonating(client)
    db = SessionLocal()
    try:
        ap = db.scalar(select(models.RequestApproval).where(
            models.RequestApproval.request_id == rid))
    finally:
        db.close()
    assert ap.original_user_id == adm_id, (
        f"القرار منسوب للمنتحَل وحده: original={ap.original_user_id}"
    )


def test_the_screen_shows_both_names(client):
    """والشاشة تقولهما مًعا: تحت أي صلاحية وقع، ومن ضغط."""
    rid, hr_id, adm_id = _approve_while_impersonating(client)
    hdr = auth_headers(login(client, *HR))
    body = client.get(f"/api/requests/{rid}", headers=hdr).json()
    done = [s for s in body.get("stages", []) if s.get("approver_name")]
    assert done, f"لا مرحلة معتمَدة في الشاشة: {body.get('stages')}"
    st = done[0]
    assert st.get("on_behalf") is True, f"الشاشة لا تشير للانتحال: {st}"
    assert st.get("acted_by"), "لا اسم للفاعل الحقيقي"
    assert st["acted_by"] != st["approver_name"], (
        f"الاسمان متطابقان — لا يقول شيًئا: {st['acted_by']}"
    )


def test_a_normal_decision_is_not_marked_on_behalf(client):
    """ولا يُوسم قرار عادي: وسم على كل شيء يعني لا شيء."""
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()
    hdr = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQCERTSAL",
        "payload_json": CERT}).json()["id"]
    hh = auth_headers(login(client, *HR))
    client.post(f"/api/requests/{rid}/decide", headers=hh,
                json={"decision": "approved"})

    body = client.get(f"/api/requests/{rid}", headers=hh).json()
    for st in body.get("stages", []):
        if st.get("approver_name"):
            assert not st.get("on_behalf"), f"قرار عادي موسوم انتحاًلا: {st}"
            assert not st.get("acted_by")


def test_the_audit_reader_stops_hiding_the_real_actor(client):
    """والقارئ يعرض ما كان مكتوًبا ولا يُقرأ."""
    rid, hr_id, adm_id = _approve_while_impersonating(client)
    oh = auth_headers(login(client, *OWNER))
    r = client.get("/api/audit", headers=oh, params={
        "entity_type": "request", "entity_id": rid, "action": "request_approved"})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert rows, "لا سطر اعتماد في التدقيق"
    row = rows[0]
    assert row.get("on_behalf") is True, f"القارئ ما زال يُخفي الانتحال: {row}"
    assert row.get("acted_by"), f"لا اسم للفاعل الحقيقي: {row}"


def test_completion_is_not_attributed_to_the_system(client):
    """و«أكمله النظام» كذب حين أكمله ضغطة إنسان.

    ``request_completed`` كان يُكتب بـ``user_id=None`` مثبًَّتا يدًوا،
    فيُقرأ ``by_system: True`` في المعاملة نفسها التي سجّلت
    ``request_approved`` باسم فاعلها.
    """
    rid, hr_id, adm_id = _approve_while_impersonating(client)
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.AuditLog).where(
            models.AuditLog.entity_type == "request",
            models.AuditLog.entity_id == rid,
            models.AuditLog.action == "request_completed")).all()
    finally:
        db.close()
    assert rows, "لا سطر اكتمال"
    row = rows[-1]
    assert row.user_id, "الاكتمال منسوب للنظام بينما نفّذه إنسان"
    assert row.original_user_id == adm_id, (
        f"الاكتمال بلا الفاعل الحقيقي: {row.original_user_id}"
    )


def test_no_audit_write_hardcodes_a_missing_actor():
    """**الحارس الجامع**: لا كتابة تدقيق تُثبّت «بلا منفذ» يدًوا.

    كتابة تتجاوز ``audit()`` وتكتب ``user_id=None`` تُنتج سطًرا يقول
    «فعله النظام» عن فعل إنسان. وسياق الفاعل قائم لهذه الحالة بالذات
    (QA-26) — تجاوزُه هو العطل، لا غيابُه.
    """
    root = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in root.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        for m in re.finditer(r"models\.AuditLog\(", src):
            window = src[m.start():m.start() + 600]
            if re.search(r"user_id\s*=\s*None", window):
                offenders.append(f"{path.name}:{src[:m.start()].count(chr(10)) + 1}")
    assert not offenders, (
        "كتابة تدقيق تُثبّت «بلا منفذ» بدل قراءة سياق الفاعل: "
        + ", ".join(offenders)
    )
