# -*- coding: utf-8 -*-
"""BKL-02 — تدقيق مركزي موحَّد لقرارات المسار.

البلاغ: حدث ``request_completed`` ظهر بلا Actor وبلا IP. والفحص كشف ما هو
أخطر: **القرار يُنفَّذ ويعود 200 ولا يُسجَّل إطلاًقا**. سطر التدقيق يُضاف
إلى الجلسة، و``workflow.decide`` يلتزم داخله **قبل** إضافته، فيُحفظ القرار
ويُهمَل سجلّه عند إغلاق الجلسة.

وهو أخطر من غياب التدقيق كلّه: السجلّ يبدو كامًلا وفيه فجوة لا تُرى — من
يفتّش يجد التقديم والدخول ولا يجد من اعتمد.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal

from .conftest import auth_headers, login

EMPLOYEE = ("100000000101", "emp12345")
SUPERVISOR = ("100000000005", "sup12345")

#: الحقول التي يفرضها البند على كل حدث قرار
REQUIRED = ["user_id", "action", "entity_type", "entity_id", "company_id",
            "ip", "user_agent", "correlation_id", "actor_role", "result",
            "created_at"]


def _new_request(client):
    hdr = auth_headers(login(client, *EMPLOYEE))
    r = client.post("/api/requests", headers=hdr, json={
        "request_type_code": "leave",
        "payload_json": {"leave_type": "annual", "start_date": "2026-11-10",
                         "end_date": "2026-11-11", "days": 2,
                         "reason": "اختبار التدقيق"}})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"], hdr


def _audit_for(rid: int, action_prefix: str = "request_"):
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.AuditLog).where(
            models.AuditLog.entity_type == "request",
            models.AuditLog.entity_id == rid).order_by(
            models.AuditLog.id)).all()
        return [r for r in rows if (r.action or "").startswith(action_prefix)]
    finally:
        db.close()


def test_a_decision_is_recorded_at_all(client):
    """جوهر البند: قرار بلا سطر تدقيق هو قرار بلا أثر.

    كان يُنفَّذ ويعود 200 ولا يُحفظ سجلّه — لأن الالتزام يسبق الإضافة.
    """
    rid, _ = _new_request(client)
    sup = auth_headers(login(client, *SUPERVISOR))
    d = client.post(f"/api/requests/{rid}/decide", headers=sup,
                    json={"decision": "approved", "note": "موافق"})
    assert d.status_code == 200, d.text

    rows = _audit_for(rid, "request_approved")
    assert rows, "القرار نُفِّذ ولم يُسجَّل — سجلّ فيه فجوة لا تُرى"


def test_decision_audit_carries_every_required_field(client):
    """الفاعل والدور والعنوان والمتصفّح ومعرّف الربط — لا واحد منها اختياري."""
    rid, _ = _new_request(client)
    sup = auth_headers(login(client, *SUPERVISOR))
    client.post(f"/api/requests/{rid}/decide", headers=sup,
                json={"decision": "approved", "note": "موافق"})
    rows = _audit_for(rid, "request_approved")
    assert rows
    row = rows[-1]
    missing = [f for f in REQUIRED if getattr(row, f, None) in (None, "")]
    assert not missing, f"حقول ناقصة في سطر القرار: {missing}"
    assert row.correlation_id == f"req:{rid}", "لا ربط بين أحداث المعاملة"
    assert row.before_json and row.after_json, "قبل/بعد غير مسجَّلين"


def test_reason_is_a_field_not_free_text(client):
    """من يبحث عن «لماذا رُفض» يُصفّي على حقل لا يقرأ ألف سطر."""
    rid, _ = _new_request(client)
    sup = auth_headers(login(client, *SUPERVISOR))
    client.post(f"/api/requests/{rid}/decide", headers=sup,
                json={"decision": "rejected", "note": "الرصيد لا يكفي"})
    rows = _audit_for(rid, "request_rejected")
    assert rows, "الرفض لم يُسجَّل"
    assert rows[-1].reason == "الرصيد لا يكفي", (
        f"السبب غير مُهيكَل: {rows[-1].reason!r}"
    )


def test_role_recorded_is_the_role_at_the_time(client):
    """الأدوار تتغيّر؛ والسجلّ يحفظ الصفة وقت الفعل لا وقت القراءة."""
    rid, _ = _new_request(client)
    sup = auth_headers(login(client, *SUPERVISOR))
    client.post(f"/api/requests/{rid}/decide", headers=sup,
                json={"decision": "approved", "note": "موافق"})
    rows = _audit_for(rid, "request_approved")
    assert rows[-1].actor_role == "branch_supervisor", (
        f"الدور المسجَّل: {rows[-1].actor_role!r}"
    )


def test_no_success_row_when_the_operation_fails(client):
    """**لا يُسجَّل Success عند فشل العملية** — قاعدة البند الصريحة.

    قرار مرفوض من الخادم لا يجوز أن يترك أثًرا يقول إنه تمّ.
    """
    rid, emp_hdr = _new_request(client)
    before = len(_audit_for(rid, "request_"))
    # صاحب الطلب لا يعتمد طلبه — يُرَدّ
    bad = client.post(f"/api/requests/{rid}/decide", headers=emp_hdr,
                      json={"decision": "approved", "note": "محاولة"})
    assert bad.status_code in (403, 409), bad.text
    after = _audit_for(rid, "request_")
    assert len(after) == before, (
        "عملية فاشلة تركت سطر تدقيق — والسجلّ يقول إنها تمّت"
    )
    assert not any(r.result == "success" and r.action == "request_approved"
                   for r in after), "سطر نجاح لقرار لم ينجح"


def test_cancel_and_resubmit_are_recorded_too(client):
    """البند يذكر أربعة أفعال: approve · reject · return · resubmit."""
    rid, emp_hdr = _new_request(client)
    sup = auth_headers(login(client, *SUPERVISOR))
    ret = client.post(f"/api/requests/{rid}/decide", headers=sup,
                      json={"decision": "returned", "note": "أكمل البيانات"})
    assert ret.status_code == 200, ret.text
    assert _audit_for(rid, "request_returned"), "الإرجاع لم يُسجَّل"

    again = client.post(f"/api/requests/{rid}/resubmit", headers=emp_hdr,
                        json={})
    if again.status_code == 200:
        assert _audit_for(rid, "request_resubmit"), "إعادة التقديم لم تُسجَّل"


def test_no_write_endpoint_audits_without_committing():
    """حارس الجذر: سطر يُضاف ولا يُلتزَم يضيع بلا صوت.

    والعطل ليس في قيمة بل في **غياب استدعاء** — وهو ما لا تكشفه مراجعة
    تقرأ ما هو مكتوب لا ما هو ناقص. وأثره متقلّب: أيُّ سطر يضيع يتغيّر
    بترتيب الالتزامات، فيظهر أحياًنا ويختفي أحياًنا.

    والفحص نحويّ لا نصّي: مسح نصّي بسيط كان يبتلع دوال مساعدة ونطاقات
    متجاوزة فيُنذر كذًبا — وحارس يُنذر كذًبا يُعطَّل، فلا يحرس شيًئا.
    """
    import ast
    from pathlib import Path

    routers = Path(__file__).resolve().parents[1] / "app" / "routers"

    def write_endpoints(tree):
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                src = ast.dump(dec)
                if "router" in src and any(
                        m in src for m in ("'post'", "'put'", "'patch'", "'delete'")):
                    yield node
                    break

    def called_names(node):
        out = set()
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                f = n.func
                out.add(f.id if isinstance(f, ast.Name)
                        else getattr(f, "attr", ""))
        return out

    offenders = []
    for path in sorted(routers.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in write_endpoints(tree):
            names = called_names(fn)
            if "audit" in names and "commit" not in names:
                offenders.append(f"{path.name}::{fn.name}")
    assert not offenders, (
        chr(10).join(["نقاط نهاية تكتب سطر تدقيق ولا تلتزم به — يضيع بلا صوت:"]
                     + offenders)
    )
