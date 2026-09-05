# -*- coding: utf-8 -*-
"""P11-34 — مخرج «فشل التطبيق» يصل إلى المستخدم.

**العطل**: ``retry-apply`` بُنيت خصّيًصا لتفتح حالًة كانت بلا مخرج،
و``why_not`` تقول لصاحب الصلاحية «صحّح سبب الفشل **ثم أعد التطبيق**» —
ثم بقيت النقطة بلا طريق من الواجهة. فالرسالة تأمر بفعل لا تملكه الشاشة،
وهو أسوأ من الصمت: يبحث المستخدم عن زرّ غير موجود ويظنّ العطل فيه.

وهو النمط نفسه الذي ظهر في ``ATT-07``: منع صحيح، ورسالة تحيل إلى مكان،
ولا شيء في ذلك المكان. **بوابة بلا مخرج.**

والراية من الخادم لا من حساب دور في الواجهة: القاعدة الواحدة في مكانين
تنحرف — وهو ما يقوله تعليق ``allowed_actions`` نفسه.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app import models, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
SUP = ("100000000005", "sup12345")
HR = ("100000000002", "hr12345")

FRONT = Path(__file__).resolve().parents[2] / "frontend"


def _stuck_request(client) -> int:
    """طلب إجازة بأيام تفوق الرصيد — يُعتمد ثم يفشل أثره."""
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()
    hdr = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQLV",
        "payload_json": {"start_date": "2030-01-01", "end_date": "2030-03-31",
                         "days": 90, "leave_type": "annual",
                         "reason": "قياس", "travel_required": False}}).json()["id"]
    for who in (SUP, HR):
        client.post(f"/api/requests/{rid}/decide",
                    headers=auth_headers(login(client, *who)),
                    json={"decision": "approved"})
    return rid


def test_the_screen_is_told_the_exit_exists(client):
    """**جوهر الإصلاح**: الخادم يقول «لهذا المستخدم مخرج»، لا الواجهة تحزر."""
    rid = _stuck_request(client)
    body = client.get(f"/api/requests/{rid}",
                      headers=auth_headers(login(client, *HR))).json()
    assert body["status"] == "apply_failed", body["status"]
    assert body["can_retry_apply"] is True, (
        "الشاشة لا تعرف أن للحالة مخرًجا — الرسالة تأمر بفعل بلا زرّ"
    )
    assert body["no_actions_reason"], "حالة تحتاج إجراًء بلا سبب معروض"


def test_it_is_not_offered_to_whoever_cannot_use_it(client):
    """ولا يُعرَض زرٌّ سيُرفض: نفس الأدوار التي يفحصها الخادم.

    زرّ يردّ 403 يُعلّم المستخدم أن الأزرار تكذب.
    """
    rid = _stuck_request(client)
    body = client.get(f"/api/requests/{rid}",
                      headers=auth_headers(login(client, *EMP))).json()
    assert body["can_retry_apply"] is False, "المخرج معروض على من لا يملكه"
    # ومع ذلك يُقال له ما يجري: الطلب ليس ماضًيا في طريقه.
    assert body["no_actions_reason"], "صمت أمام طلب لم يقع أثره"


def test_a_healthy_request_is_not_offered_a_retry(client):
    """ولا يظهر المخرج حيث لا عطل — وإلا صار زًرا بلا معًنى."""
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()
    hdr = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQLV",
        "payload_json": {"start_date": "2030-06-01", "end_date": "2030-06-03",
                         "days": 3, "leave_type": "unpaid",
                         "reason": "قياس"}}).json()["id"]
    body = client.get(f"/api/requests/{rid}", headers=hdr).json()
    assert body["can_retry_apply"] is False, body["status"]


def test_the_exit_actually_works_end_to_end(client):
    """ومخرج لا يُخرج ليس مخرًجا: بعد تصحيح السبب يمضي الطلب.

    ولا يقفز فوق التسليم — الأثر يقع ثم يُفتَح الاستلام.
    """
    rid = _stuck_request(client)

    # تصحيح السبب: رفع رصيد الموظف بما يكفي (وهو ما يفعله المستخدم يًدا).
    db = SessionLocal()
    try:
        req = db.get(models.Request, rid)
        emp = db.get(models.Employee, req.employee_id)
        emp.annual_leave_balance = 120
        db.commit()
    finally:
        db.close()

    r = client.post(f"/api/requests/{rid}/retry-apply",
                    headers=auth_headers(login(client, *HR)))
    assert r.status_code == 200, r.text[:200]

    body = client.get(f"/api/requests/{rid}",
                      headers=auth_headers(login(client, *HR))).json()
    assert body["status"] == "ready_for_pickup", body["status"]
    assert body["can_retry_apply"] is False, "المخرج ما زال معروًضا بعد نجاحه"


def test_the_button_exists_and_reads_its_flag_from_the_server():
    """والزرّ موجود ومربوط بالراية — لا بشرط دور محسوب في الواجهة."""
    src = (FRONT / "src" / "pages" / "RequestDetail.tsx").read_text(
        encoding="utf-8")
    assert "retry-apply" in src, "لا زرّ لإعادة التطبيق — النقطة بلا طريق"
    assert "req.can_retry_apply" in src, (
        "الزرّ يحسب شرطه في الواجهة — قاعدة ثانية تنحرف عن الخادم"
    )
    for key in ("rd_retry_title", "rd_retry_apply"):
        assert key in src, f"المفتاح «{key}» غير مستعمل"


def test_the_roles_rule_lives_in_one_place():
    """وقاعدة «من يُعيد التطبيق» معرَّفة مرًة واحدة يقرؤها الجميع."""
    import inspect

    from app import request_actions

    assert workflow.APPLY_RETRY_ROLES, "القاعدة فارغة"
    # ``request_actions`` تستوردها ولا تُعيد كتابتها.
    src = inspect.getsource(request_actions)
    assert "APPLY_RETRY_ROLES as _RETRY_ROLES" in src, (
        "قاعدة الأدوار كُتبت مرّتين"
    )
    router = (Path(__file__).resolve().parents[1] / "app" / "routers"
              / "requests.py").read_text(encoding="utf-8")
    assert "workflow.APPLY_RETRY_ROLES" in router, (
        "الراية تحسب الأدوار بنفسها بدل قراءة المصدر الواحد"
    )
