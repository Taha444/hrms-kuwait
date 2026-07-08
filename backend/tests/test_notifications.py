# -*- coding: utf-8 -*-
"""اختبارات كتالوج قوالب الإشعارات (74) + التفضيلات + تكامل سجل الطباعة/الأرشفة (FIX-004)."""
import io

from tests.conftest import auth_headers, login


def test_74_notification_templates_seeded(client):
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    r = client.get("/api/notifications/templates", headers=hr)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 74
    codes = {x["code"] for x in data}
    assert "NTF-001" in codes and "NTF-074" in codes
    cats = client.get("/api/notifications/templates/categories", headers=hr).json()
    assert len(cats) == 10


def test_preferences_default_enabled_and_updatable(client):
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    prefs = client.get("/api/notifications/preferences", headers=hr).json()
    assert len(prefs) > 0
    assert all(p["enabled"] for p in prefs)

    cat = prefs[0]["category"]
    r = client.put("/api/notifications/preferences", headers=hr,
                   json=[{"category": cat, "channel": "in_app", "enabled": False}])
    assert r.status_code == 200
    prefs2 = client.get("/api/notifications/preferences", headers=hr).json()
    updated = next(p for p in prefs2 if p["category"] == cat and p["channel"] == "in_app")
    assert updated["enabled"] is False


def test_print_and_file_send_template_driven_notification(client):
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "loan", "payload_json": {"amount": 100, "reason": "ظرف"}})
    rid = r.json()["id"]
    mgr = auth_headers(login(client, "100000000001", "manager123"))
    client.post(f"/api/requests/{rid}/decide", headers=mgr, json={"decision": "approved"})
    acc = auth_headers(login(client, "100000000007", "account123"))

    # لا مستند مولَّد لطلب القرض (produces_document=False) — نتحقق من شهادة الراتب بدلًا منه
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "salary_certificate",
        "payload_json": {"addressed_to": "بنك", "purpose": "قرض"}})
    rid2 = r.json()["id"]
    client.post(f"/api/requests/{rid2}/decide", headers=mgr, json={"decision": "approved"})

    r = client.post(f"/api/requests/{rid2}/document/generated_pdf/mark-printed", headers=mgr)
    assert r.status_code == 200
    tasks = client.get("/api/tasks/my", headers=mgr).json()
    assert any(t["type"] == "print_done" for t in tasks)

    r = client.post(f"/api/requests/{rid2}/document/generated_pdf/mark-filed", headers=mgr)
    assert r.status_code == 200
    tasks = client.get("/api/tasks/my", headers=mgr).json()
    assert any(t["type"] == "file_done" for t in tasks)
