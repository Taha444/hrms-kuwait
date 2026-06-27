# -*- coding: utf-8 -*-
"""اختبارات حقول الموظف الموسّعة، الحالات، أحداث HR، والخط الزمني."""
from tests.conftest import auth_headers, login


def _an_emp(client, h):
    return client.get("/api/employees", headers=h).json()[0]["id"]


def test_extended_employee_fields(client):
    mgr = login(client, "100000000001", "manager123")
    h = auth_headers(mgr)
    r = client.post("/api/employees", headers=h, json={
        "civil_id": "199900077001", "name": "موظف موسّع", "basic_salary": 500,
        "gender": "male", "date_of_birth": "1990-05-10", "marital_status": "married",
        "passport_number": "A1234567", "passport_expiry": "2030-01-01",
        "health_insurance": "شركة التأمين", "email": "x@y.com"})
    assert r.status_code == 201, r.text
    new_id = r.json()["id"]
    prof = client.get(f"/api/employees/{new_id}", headers=h).json()
    assert prof["gender"] == "male" and prof["passport_number"] == "A1234567"
    # تنظيف: لا نترك موظفًا نشطًا إضافيًا يؤثّر على عدّادات اختبارات أخرى
    client.post(f"/api/employees/{new_id}/status", headers=h, params={"status": "resigned"})


def test_employee_status_lifecycle(client):
    mgr = login(client, "100000000001", "manager123")
    h = auth_headers(mgr)
    eid = _an_emp(client, h)
    assert client.post(f"/api/employees/{eid}/status", headers=h, params={"status": "vacation"}).status_code == 200
    assert client.get(f"/api/employees/{eid}", headers=h).json()["status"] == "vacation"
    assert client.post(f"/api/employees/{eid}/status", headers=h, params={"status": "xyz"}).status_code == 400
    client.post(f"/api/employees/{eid}/status", headers=h, params={"status": "active"})  # cleanup


def test_employee_hr_events(client):
    mgr = login(client, "100000000001", "manager123")
    h = auth_headers(mgr)
    eid = _an_emp(client, h)
    client.post(f"/api/employees/{eid}/events", headers=h,
                params={"kind": "warning", "title": "تأخر متكرر"})
    client.post(f"/api/employees/{eid}/events", headers=h,
                params={"kind": "bonus", "title": "مكافأة أداء", "amount": 100})
    events = client.get(f"/api/employees/{eid}/events", headers=h).json()
    assert any(e["kind"] == "warning" for e in events)
    assert any(e["kind"] == "bonus" and e["amount"] == 100 for e in events)


def test_employee_timeline(client):
    mgr = login(client, "100000000001", "manager123")
    h = auth_headers(mgr)
    eid = _an_emp(client, h)
    r = client.get(f"/api/employees/{eid}/timeline", headers=h)
    assert r.status_code == 200, r.text
    tl = r.json()["timeline"]
    assert any(x["category"] == "create" for x in tl)
    # مرتّب تنازليًا زمنيًا
    ats = [x["at"] for x in tl]
    assert ats == sorted(ats, reverse=True)
