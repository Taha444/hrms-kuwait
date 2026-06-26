# -*- coding: utf-8 -*-
"""اختبارات وحدة المندوب (PRO): متابعة الإقامات، التجديد، الملاحظات، الجهات الحكومية."""
from tests.conftest import auth_headers, login


def test_pro_lists_permits_with_urgency(client):
    pro = login(client, "100000000003", "deleg123")
    r = client.get("/api/pro/permits", headers=auth_headers(pro))
    assert r.status_code == 200, r.text
    permits = r.json()
    assert len(permits) >= 1
    p0 = permits[0]
    assert set(p0) >= {"kind", "employee_name", "days_left", "urgency"}


def test_pro_renew_permit_and_log(client):
    pro = login(client, "100000000003", "deleg123")
    h = auth_headers(pro)
    pid = client.get("/api/pro/permits", headers=h).json()[0]["id"]
    r = client.post(f"/api/pro/permits/{pid}/renew", headers=h,
                    params={"expiry_date": "2030-01-01", "note": "جُدّدت بنجاح"})
    assert r.status_code == 200, r.text
    assert r.json()["expiry_date"] == "2030-01-01"
    # السجل يحفظ التجديد
    notes = client.get("/api/pro/notes", headers=h, params={"entity_type": "permit", "entity_id": pid}).json()
    assert any(n["action"] == "renew" for n in notes)


def test_pro_add_note(client):
    pro = login(client, "100000000003", "deleg123")
    h = auth_headers(pro)
    pid = client.get("/api/pro/permits", headers=h).json()[0]["id"]
    r = client.post("/api/pro/notes", headers=h,
                    params={"entity_type": "permit", "entity_id": pid, "note": "بانتظار البصمة"})
    assert r.status_code == 200
    notes = client.get("/api/pro/notes", headers=h, params={"entity_type": "permit", "entity_id": pid}).json()
    assert any(n["note"] == "بانتظار البصمة" for n in notes)


def test_pro_government_overview(client):
    pro = login(client, "100000000003", "deleg123")
    r = client.get("/api/pro/government", headers=auth_headers(pro))
    assert r.status_code == 200
    d = r.json()
    assert "entities" in d and "known_authorities" in d


def test_hr_cannot_access_pro(client):
    hr = login(client, "100000000002", "hr12345")
    assert client.get("/api/pro/permits", headers=auth_headers(hr)).status_code == 403
