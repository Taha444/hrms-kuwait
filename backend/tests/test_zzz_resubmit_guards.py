# -*- coding: utf-8 -*-
"""M09 — إعادة التقديم بعد الإرجاع بابٌ ثانٍ إلى ``pending`` لا يمرّ بحرّاس الإنشاء.

``create_request`` يحرس الباب الأول: حالةُ الموظف (``BLOCKED_EMPLOYEE_STATUSES``)
وبصمةُ التكرار (فهرسٌ فريد جزئي على الطلب المفتوح). أما ``workflow.resubmit``
فيقلب الطلب من ``returned`` إلى ``pending`` ويصفّر ``closed_at`` **بلا أيٍّ
منهما** — وهو نمطُ «موضعان يصفان قاعدةً واحدة» بعينه.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
MGR = ("100000000001", "manager123")
HR = ("100000000002", "hr12345")

_PAYLOAD = {"purpose": "بنك الاختبار", "language": "ar", "notes": "M09 resubmit"}


def _returned_request(client, notes: str) -> int:
    emp = auth_headers(login(client, *EMP))
    payload = {**_PAYLOAD, "notes": notes}
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "salary_certificate", "payload_json": payload})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    mgr = auth_headers(login(client, *MGR))
    ret = client.post(f"/api/requests/{rid}/decide", headers=mgr, json={
        "decision": "returned", "note": "للتصحيح"})
    assert ret.status_code == 200, ret.text
    return rid


def _cleanup(ids, emp_status_restore=None):
    db = SessionLocal()
    try:
        if emp_status_restore:
            eid, status = emp_status_restore
            e = db.get(models.Employee, eid)
            if e:
                e.status = status
        from tests.conftest import purge
        for rid in ids:
            purge(db, "requests", [rid])
        db.commit()
    finally:
        db.close()


def test_a_returned_request_of_a_terminated_employee_is_not_resubmittable(client):
    rid = _returned_request(client, "M09-A")
    db = SessionLocal()
    try:
        emp_id = db.get(models.Request, rid).employee_id
        prev = db.get(models.Employee, emp_id).status
        db.get(models.Employee, emp_id).status = "terminated"
        db.commit()
    finally:
        db.close()
    try:
        hr = auth_headers(login(client, *HR))
        r = client.post(f"/api/requests/{rid}/resubmit", headers=hr, json={})
        assert r.status_code == 409, (
            f"طلبُ موظفٍ انتهت خدمته عاد إلى pending: {r.status_code} {r.text[:200]}")
        st = client.get(f"/api/requests/{rid}", headers=hr).json()["status"]
        assert st == "returned", f"الحالة تغيّرت رغم الرفض: {st}"
    finally:
        _cleanup([rid], (emp_id, prev))


def test_resubmitting_into_a_duplicate_is_refused_cleanly_not_a_500(client):
    rid = _returned_request(client, "M09-B")
    emp = auth_headers(login(client, *EMP))
    # طلبٌ مطابقٌ بالبصمة نفسها — مسموحٌ لأن الأول مُغلَق (returned)
    dup = client.post("/api/requests", headers=emp, json={
        "request_type_code": "salary_certificate",
        "payload_json": {**_PAYLOAD, "notes": "M09-B"}})
    assert dup.status_code == 201, dup.text
    rid2 = dup.json()["id"]
    assert rid2 != rid
    try:
        r = client.post(f"/api/requests/{rid}/resubmit", headers=emp, json={})
        assert r.status_code == 409, (
            f"إعادة التقديم إلى طلب مكرَّر لم تُردّ بنظافة: {r.status_code} {r.text[:200]}")
    finally:
        _cleanup([rid, rid2])
