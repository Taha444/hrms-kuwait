# -*- coding: utf-8 -*-
"""قرار الإجازة يصدر فوًرا — قرار المالك.

**ما كان**: الطلب يقف عند «بانتظار حضور الموظف للتوقيع»، ويُطلَب منه
الحضور ليوقّع باليد **ورقًة تحمل توقيعه مطبوًعا فيها أصًلا**: التوليد
يسحب ``signature_path`` من حسابه ويضعه في موضعه.

**وبقاؤه لم يكن اختياًرا**: كانت الإجازة النوع **الوحيد** الذي يقف
للتوقيع قبل P5-23 — فاستمرّت بحكم الحال لا بقرار.

**والعقود تبقى كما هي** (REQRESIGN · REQEOS · REQCLR): تُقدَّم لجهات
تشترط توقيًعا حًيا، ويُحتجّ بها في نزاع.

**والشهادات كانت خارج الانتظار أصًلا** — فقرار المالك عنها كان قائًما
قبل أن يُطلَب، وقستُه قبل التنفيذ فلم أُنفّذ فيها شيًئا.
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete, select

from app import models, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
SUP = ("100000000005", "sup12345")
HR = ("100000000002", "hr12345")

LEAVE = {"start_date": "2027-08-02", "end_date": "2027-08-06", "days": 5,
         "leave_type": "annual", "reason": "راحة", "travel_required": False}


def _emp_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()


def test_only_the_contracts_still_wait_for_a_wet_signature():
    """الحصيلة: ثلاثة عقود وحدها — لا الإجازة ولا الشهادات."""
    signed = {rt["code"] for rt in workflow.DEFAULT_REQUEST_TYPES
              if rt.get("requires_physical_signature")}
    assert signed == {"REQRESIGN", "REQEOS", "REQCLR"}, sorted(signed)


def test_certificates_were_already_outside_the_wait():
    """والشهادات لم تكن تنتظر قبل هذا القرار — فلم يُنفَّذ فيها شيء.

    وتثبيت ذلك يمنع أن يُقال «نُفِّذ» على ما كان قائًما.
    """
    certs = {"salary_certificate", "REQCERTSAL", "REQCERTEMP", "REQCERTEXP"}
    waiting = {rt["code"] for rt in workflow.DEFAULT_REQUEST_TYPES
               if rt["code"] in certs and rt.get("requires_physical_signature")}
    assert not waiting, waiting


def test_a_leave_request_completes_without_a_signature_step(client):
    """**جوهر القرار**: الطلب لا يقف عند «بانتظار التوقيع»."""
    eid = _emp_id()
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQLV",
        "payload_json": LEAVE})
    assert r.status_code == 201, r.text[:250]
    rid = r.json()["id"]

    seen = []
    for who in (SUP, HR):
        d = client.post(f"/api/requests/{rid}/decide",
                        headers=auth_headers(login(client, *who)),
                        json={"decision": "approved"})
        assert d.status_code == 200, d.text[:200]
        seen.append(client.get(f"/api/requests/{rid}", headers=hdr
                               ).json()["status"])

    assert "awaiting_signature" not in seen, (
        f"ما زال يقف للتوقيع: {seen}"
    )
    # ويستقرّ عند الاستلام لا عند التوقيع: المستند صدر، ويُقال أين يُؤخَذ.
    # (مرحلة الاستلام قرار لاحق للمالك — انظر ``test_zzz_leave_pickup_stage``)
    assert seen[-1] == "ready_for_pickup", f"استقرّ عند {seen[-1]}"


def test_the_document_is_issued_and_carries_the_signature(client):
    """ويصدر المستند فعًلا — لا يُلغى الانتظار ويبقى بلا ورقة.

    وتوقيع الموظف مدموج فيه: هذا هو سبب الاستغناء عن الانتظار، فلو زال
    الدمج لصار الإصدار الفوري ورقًة بلا توقيع أصًلا.
    """
    import inspect

    src = inspect.getsource(workflow.generate_document)
    assert "employee_signature=" in src, (
        "زال دمج توقيع الموظف — والإصدار الفوري يقوم عليه"
    )

    eid = _emp_id()
    hdr = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQLV",
        "payload_json": LEAVE}).json()["id"]
    for who in (SUP, HR):
        client.post(f"/api/requests/{rid}/decide",
                    headers=auth_headers(login(client, *who)),
                    json={"decision": "approved"})

    db = SessionLocal()
    try:
        docs = db.scalars(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid)).all()
    finally:
        db.close()
    assert any(d.lifecycle_status == "GENERATED" and d.file_path for d in docs), (
        f"اكتمل الطلب بلا مستند: {[(d.kind, d.lifecycle_status) for d in docs]}"
    )


def test_the_leave_effect_still_applies(client):
    """والأثر يقع: الرصيد يُخصَم عند الاعتماد لا عند رفع التوقيع.

    فنقل خطّ النهاية لم يُسقط ما كان يقع عنده. ثم أُضيفت مرحلة الاستلام،
    فبقي الأثر عند **انتهاء العمل** لا عند تسليم الورقة: لو انتظر
    التسليم لسافر الموظف بلا صفّ إجازة ولا رصيد نقص.
    """
    eid = _emp_id()
    hdr = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQLV",
        "payload_json": {**LEAVE, "start_date": "2027-09-06",
                         "end_date": "2027-09-08", "days": 3}}).json()["id"]
    for who in (SUP, HR):
        client.post(f"/api/requests/{rid}/decide",
                    headers=auth_headers(login(client, *who)),
                    json={"decision": "approved"})

    db = SessionLocal()
    try:
        req = db.get(models.Request, rid)
        approvals = db.scalars(select(models.RequestApproval).where(
            models.RequestApproval.request_id == rid)).all()
    finally:
        db.close()
    assert req.status == "ready_for_pickup", req.status
    # أثر الإجازة يُسجَّل سطًرا في سلسلة الاعتماد باسم النظام — **قبل**
    # التسليم لا بعده.
    assert any(a.approver_role == "system" and a.decision == "approved"
               for a in approvals), (
        f"لم يُسجَّل أثر الإجازة: {[(a.approver_role, a.decision) for a in approvals]}"
    )


def test_a_travelling_leave_still_reaches_the_delegate(client):
    """ولم يُكسر مسار السفر: التأشير ما زال يُدخل مرحلة المندوب.

    فإلغاء انتظار التوقيع لا يقفز فوق ما بعده.
    """
    eid = _emp_id()
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQLV",
        "payload_json": {**LEAVE, "start_date": "2027-10-04",
                         "end_date": "2027-10-08",
                         "travel_required": True, "destination": "القاهرة"}})
    assert r.status_code == 201, r.text[:250]
    rid = r.json()["id"]
    for who in (SUP, HR):
        client.post(f"/api/requests/{rid}/decide",
                    headers=auth_headers(login(client, *who)),
                    json={"decision": "approved"})
    body = client.get(f"/api/requests/{rid}", headers=hdr).json()
    assert body["status"] == "awaiting_delegate", body["status"]
    assert "delegate" in [s.get("role") for s in body.get("stages", [])]
