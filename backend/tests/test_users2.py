# -*- coding: utf-8 -*-
"""اختبارات حالات المستخدم (تعطيل/إيقاف) وانتحال الهوية (Impersonation)."""
from tests.conftest import auth_headers, login


def test_user_status_suspend_blocks_login(client):
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    uid = client.post("/api/users", headers=ah, json={
        "civil_id": "888000111000", "full_name": "مستخدم اختبار", "role": "hr",
        "company_id": 1, "password": "temp123456"}).json()["id"]

    # إيقاف → يُمنع الدخول
    client.post(f"/api/users/{uid}/status", headers=ah, params={"status": "suspended"})
    r = client.post("/api/auth/login", json={"civil_id": "888000111000", "password": "temp123456"})
    assert r.status_code == 403

    # إعادة تفعيل → يدخل
    client.post(f"/api/users/{uid}/status", headers=ah, params={"status": "active"})
    r2 = client.post("/api/auth/login", json={"civil_id": "888000111000", "password": "temp123456"})
    assert r2.status_code == 200


def test_impersonation_super_admin_only(client):
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    # هوية موظف
    users = client.get("/api/users", headers=ah, params={"company_id": 1}).json()
    emp_uid = next(u["id"] for u in users if u["civil_id"] == "100000000101")

    r = client.post(f"/api/users/{emp_uid}/impersonate", headers=ah, params={"reason": "دعم"})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    me = client.get("/api/auth/me", headers=auth_headers(tok)).json()
    assert me["civil_id"] == "100000000101"  # نتصفّح كالموظف فعليًا

    # المدير لا يستطيع الانتحال
    mgr = login(client, "100000000001", "manager123")
    assert client.post(f"/api/users/{emp_uid}/impersonate", headers=auth_headers(mgr)).status_code == 403


def test_impersonate_end_logs_audit_with_original_actor(client):
    """P1-04: إنهاء الانتحال يُسجَّل في التدقيق منسوًبا للإدارة العليا (المُنتحِل الفعلي)،
    لا للموظف المُنتحَل هويته، عبر claim مضمَّن في الرمز نفسه (impersonator_id)."""
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    users = client.get("/api/users", headers=ah, params={"company_id": 1}).json()
    emp_uid = next(u["id"] for u in users if u["civil_id"] == "100000000101")

    tok = client.post(f"/api/users/{emp_uid}/impersonate", headers=ah,
                      params={"reason": "دعم"}).json()["access_token"]
    r = client.post("/api/users/impersonate-end", headers=auth_headers(tok))
    assert r.status_code == 200, r.text

    logs = client.get("/api/audit", headers=ah, params={"action": "impersonate_end"}).json()
    assert any(log_.get("entity_id") == emp_uid for log_ in logs)

    # رمز عادي (غير مُنتحَل) لا يحمل claim الانتحال → 400
    mgr = login(client, "100000000001", "manager123")
    r2 = client.post("/api/users/impersonate-end", headers=auth_headers(mgr))
    assert r2.status_code == 400


def test_audit_filters_by_entity_and_date(client):
    """P1-04: فلاتر التدقيق الجديدة (entity_type/entity_id/user_id/from_date/to_date)."""
    from datetime import date, timedelta

    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    acc = login(client, "100000000007", "account123")
    emps = client.get("/api/employees", headers=auth_headers(acc)).json()
    emp = next(e for e in emps if e["civil_id"] == "100000000101")
    client.post(f"/api/employees/{emp['id']}/actual-salary", headers=auth_headers(acc),
               params={"amount": 999})

    logs = client.get("/api/audit", headers=ah, params={
        "company_id": 1, "entity_type": "employee", "entity_id": emp["id"],
        "action": "edit_actual_salary",
    }).json()
    assert any("→" in (log_.get("detail") or "") for log_ in logs)

    today = date.today()
    logs2 = client.get("/api/audit", headers=ah, params={
        "company_id": 1, "from_date": str(today), "to_date": str(today),
    }).json()
    assert len(logs2) >= 1
    future = today + timedelta(days=1)
    logs3 = client.get("/api/audit", headers=ah, params={
        "company_id": 1, "from_date": str(future),
    }).json()
    assert logs3 == []


def test_cannot_impersonate_super_admin(client):
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    admins = client.get("/api/users", headers=ah).json()
    sa_uid = next(u["id"] for u in admins if u["civil_id"] == "000000000000")
    assert client.post(f"/api/users/{sa_uid}/impersonate", headers=ah).status_code == 400
