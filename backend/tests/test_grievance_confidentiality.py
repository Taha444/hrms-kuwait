# -*- coding: utf-8 -*-
"""سرّية الشكاوى/التظلمات (FIX-014): لا يطّلع المدير العام على شكوى ضده، وتصل للشؤون فقط."""
from tests.conftest import auth_headers, login


def test_manager_cannot_see_or_decide_grievance(client):
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "REQGRV",
        "payload_json": {"subject": "شكوى ضد المدير العام", "details": "..."}})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]

    # المدير العام لا يستطيع فتح الشكوى رغم أنه يملك approve_request عمومًا
    mgr = auth_headers(login(client, "100000000001", "manager123"))
    r = client.get(f"/api/requests/{rid}", headers=mgr)
    assert r.status_code == 404
    r = client.post(f"/api/requests/{rid}/decide", headers=mgr, json={"decision": "approved"})
    assert r.status_code in (403, 404)
    # ولا تظهر له في صندوق الوارد
    inbox = client.get("/api/requests/inbox", headers=mgr).json()
    assert not any(x["id"] == rid for x in inbox)

    # الشؤون القانونية (hr) تراها وتستطيع البت فيها
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    r = client.get(f"/api/requests/{rid}", headers=hr)
    assert r.status_code == 200
    inbox_hr = client.get("/api/requests/inbox", headers=hr).json()
    assert any(x["id"] == rid for x in inbox_hr)
    r = client.post(f"/api/requests/{rid}/decide", headers=hr, json={"decision": "approved"})
    assert r.status_code == 200

    # صاحب الشكوى نفسه يستطيع رؤية طلبه
    r = client.get(f"/api/requests/{rid}", headers=emp)
    assert r.status_code == 200
