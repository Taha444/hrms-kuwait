# -*- coding: utf-8 -*-
"""المرفقُ المطلوب ملفٌّ حقيقيٌّ قبل الاعتماد — لا اسمٌ يُدّعى عند الإنشاء.

**القياس** (قبل الإصلاح):

- الشرطُ عند الإنشاء على ``payload["_attachments"]`` — أسماءٌ **يكتبها
  العميل**. فإجازةٌ مرضيةٌ بـ``_attachments: ["medical_report"]`` **بلا أي
  ملف** ← 201.
- والواجهةُ لا ترسلها قطّ — فأحدَ عشرَ نوعًا (سبعةٌ دائمًا: مصروفات، بنك،
  تجديد، جواز، مدنية، اعتراض راتب، توقيع؛ وأربعةٌ بشرط، منها الإجازةُ المرضية)
  **لا تُقدَّم من الشاشة أصلًا**، برسالةٍ تسمّي مفتاحًا داخليًا. والشاشةُ نفسها
  تقول «ترفعها من صفحة الطلب بعد الإنشاء» — ولا فعلَ يعرض الرفع.

**فصار**: الإنشاءُ يُقبل؛ وصاحبُ الطلب يرى فعلَ «رفع المرفق المطلوب»؛
والاعتمادُ يُرفض حتى يُرفع ملفٌّ (الرفضُ والإرجاعُ باقيان)؛ والمعتمِدُ يرى النقصَ
قبل أن يضغط.
"""
from __future__ import annotations

import io

from sqlalchemy import delete as sa_delete

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
MGR = ("100000000001", "manager123")
HR = ("100000000002", "hr12345")

_SICK = {"request_type_code": "REQLV", "payload_json": {
    "start_date": "2031-04-01", "end_date": "2031-04-02", "days": 2,
    "leave_type": "sick", "reason": "قياس"}}


def _cleanup(rid: int) -> None:
    db = SessionLocal()
    try:
        for tbl in (models.RequestDocument, models.RequestApproval):
            db.execute(sa_delete(tbl).where(tbl.request_id == rid))
        db.execute(sa_delete(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid))
        db.execute(sa_delete(models.Request).where(models.Request.id == rid))
        db.commit()
    finally:
        db.close()


#: كلماتُ مرور البذر بحسب الرقم المدني — لتسجيل دخول المعتمِد الفعلي.
_SEED_PW = {"100000000001": "manager123", "100000000002": "hr12345",
            "100000000005": "sup12345", "100000000007": "account123",
            "100000000003": "deleg123", "100000000004": "deleg123",
            "000000000000": "admin123"}


def _stage_approver_headers(client, rid):
    """معتمِدُ المرحلة الحالية كما يحسبه المسارُ نفسه — لا تخمين."""
    from app import workflow

    db = SessionLocal()
    try:
        req = db.get(models.Request, rid)
        rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
        stage = workflow._chain(rt, req)[req.current_stage]
        users = workflow.resolve_stage_approvers(db, req, stage)
        for u in users:
            if u.civil_id in _SEED_PW:
                return auth_headers(login(client, u.civil_id, _SEED_PW[u.civil_id]))
        return None
    finally:
        db.close()


def _approve_as_first_approver(client, rid):
    h = _stage_approver_headers(client, rid)
    if h is None:
        return None, None
    detail = client.get(f"/api/requests/{rid}", headers=h).json()
    acts = [a for a in detail.get("allowed_actions") or []
            if a.get("via") == "decide" and a.get("decision") == "approved"]
    if not acts:
        return None, detail
    resp = client.post(f"/api/requests/{rid}/decide", headers=h,
                       json={"decision": "approved", "action": acts[0]["action"]})
    return resp, detail


def test_the_screen_can_submit_a_sick_leave_without_a_claimed_name(client):
    """**البوّابةُ التي بلا مخرج**: الشاشةُ لا ترسل ``_attachments``."""
    r = client.post("/api/requests", json=_SICK, headers=auth_headers(login(client, *EMP)))
    assert r.status_code == 201, (r.status_code, r.text[:200])
    _cleanup(r.json()["id"])


def test_a_claimed_name_without_a_file_is_not_enough_to_approve(client):
    body = {**_SICK, "payload_json": {**_SICK["payload_json"],
                                      "_attachments": ["medical_report"]}}
    r = client.post("/api/requests", json=body, headers=auth_headers(login(client, *EMP)))
    assert r.status_code == 201, r.text[:200]
    rid = r.json()["id"]
    try:
        resp, detail = _approve_as_first_approver(client, rid)
        assert detail is not None, "لا معتمِدَ للمرحلة الأولى بين الحسابات المجرَّبة"
        assert detail.get("missing_attachments"), "المعتمِد لا يرى النقص"
        assert resp.status_code == 409, (resp.status_code, resp.text[:200])
        assert "التقرير الطبي" in resp.text
    finally:
        _cleanup(rid)


def test_the_requester_sees_the_upload_action_and_a_real_file_unblocks(client):
    eh = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", json=_SICK, headers=eh)
    rid = r.json()["id"]
    try:
        acts = client.get(f"/api/requests/{rid}", headers=eh).json()["allowed_actions"]
        up = [a for a in acts if a.get("action") == "upload_attachment"]
        assert up and up[0]["doc_kind"] == "attachment", acts
        assert "التقرير الطبي" in up[0]["label_ar"]

        u = client.post(f"/api/requests/{rid}/documents", headers=eh,
                        data={"kind": "attachment"},
                        files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")})
        assert u.status_code in (200, 201), (u.status_code, u.text[:200])

        acts2 = client.get(f"/api/requests/{rid}", headers=eh).json()["allowed_actions"]
        assert not [a for a in acts2 if a.get("action") == "upload_attachment"]

        resp, _ = _approve_as_first_approver(client, rid)
        assert resp is not None and resp.status_code == 200, (
            getattr(resp, "status_code", None), getattr(resp, "text", "")[:200])
    finally:
        _cleanup(rid)


def test_an_incomplete_request_can_still_be_returned(client):
    """والمعتمِدُ لا يُحبس أمام طلبٍ ناقص — الإرجاعُ باقٍ."""
    r = client.post("/api/requests", json=_SICK, headers=auth_headers(login(client, *EMP)))
    rid = r.json()["id"]
    try:
        h = _stage_approver_headers(client, rid)
        assert h is not None, "لا معتمِدَ معروفَ الكلمة للمرحلة الأولى"
        acts = client.get(f"/api/requests/{rid}", headers=h).json().get("allowed_actions") or []
        ret = [a for a in acts if a.get("decision") == "returned"]
        assert ret, acts
        resp = client.post(f"/api/requests/{rid}/decide", headers=h,
                           json={"decision": "returned", "action": ret[0]["action"],
                                 "note": "أرفق التقرير الطبي"})
        assert resp.status_code == 200, (resp.status_code, resp.text[:200])
    finally:
        _cleanup(rid)
