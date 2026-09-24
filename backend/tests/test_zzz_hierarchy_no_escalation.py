# -*- coding: utf-8 -*-
"""لا يأخذ أحدٌ سلطةً أكبر من صلاحياته إلا بتعديلٍ ممّن هو أعلى منه (قرار المالك 2026-09-24).

قيس بمسبارٍ على الأدوار المزروعة: مدير الشركة منح نفسه ``manage_licenses`` ومنح HR
``manage_templates`` (لا يملكها)؛ وHR أوقف ملفّ المدير وكتب عليه؛ وقدّم المندوبُ خصمًا باسم
المدير؛ وأنشأ الموظف طلب «إصدار خصم» بالـAPI؛ وأنشأ HR تفويضًا باسم المدير.
"""
from datetime import datetime, timedelta

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import login, purge

MGR = ("100000000001", "manager123")
HR = ("100000000002", "hr12345")
DEL = ("100000000003", "deleg123")
EMP = ("100000000101", "emp12345")
ADMIN = ("000000000000", "admin123")


def _h(client, cred):
    return {"Authorization": f"Bearer {login(client, *cred)}"}


def _me(client, h):
    return client.get("/api/auth/me", headers=h).json()


def _revoke(client, admin, uid, code):
    client.delete(f"/api/users/{uid}/permissions/{code}", headers=admin)


def test_nobody_grants_himself_or_grants_beyond_what_he_holds(client):
    mgr, admin, hr = _h(client, MGR), _h(client, ADMIN), _h(client, HR)
    mid, hid = _me(client, mgr)["id"], _me(client, hr)["id"]
    try:
        # (١) لا يمنح نفسه.
        r = client.post(f"/api/users/{mid}/permissions", headers=mgr, json={"perm_codes": ["manage_licenses"]})
        assert r.status_code == 403, r.text
        # (٢) لا يمنح غيره ما لا يملكه هو (manage_templates للإدارة العليا وحدها).
        r = client.post(f"/api/users/{hid}/permissions", headers=mgr, json={"perm_codes": ["manage_templates"]})
        assert r.status_code == 403 and "لا تمنح" in r.text, r.text
        # (٣) ما يملكه يمنحه لمن هو أدنى.
        r = client.post(f"/api/users/{hid}/permissions", headers=mgr, json={"perm_codes": ["manage_branches"]})
        assert r.status_code == 200, r.text
        # (٤) الإدارة العليا وحدها بلا سقف.
        r = client.post(f"/api/users/{hid}/permissions", headers=admin, json={"perm_codes": ["manage_templates"]})
        assert r.status_code == 200, r.text
        # ولا يغيّر نطاقَ نفسه ولا يسحب صلاحية نفسه.
        assert client.post(f"/api/users/{mid}/scope", params={"level": "self"}, headers=mgr).status_code == 403
        assert client.post(f"/api/users/{mid}/matrix/reset", headers=mgr).status_code == 403
    finally:
        _revoke(client, admin, hid, "manage_branches")
        _revoke(client, admin, hid, "manage_templates")


def test_a_lower_role_cannot_write_to_a_higher_roles_employee_file(client):
    hr, mgr = _h(client, HR), _h(client, MGR)
    mgr_emp = _me(client, mgr)["employee_id"]
    hr_emp = _me(client, hr)["employee_id"]
    emp_emp = _me(client, _h(client, EMP))["employee_id"]
    assert client.post(f"/api/employees/{mgr_emp}/status", params={"status": "suspended"},
                       headers=hr).status_code == 403
    assert client.post(f"/api/employees/{mgr_emp}/events", params={"kind": "note", "title": "t"},
                       headers=hr).status_code == 403
    assert client.put(f"/api/employees/{mgr_emp}", headers=hr,
                      json={"name": "x", "civil_id": "100000000123", "phone": "5551",
                            "basic_salary": 100}).status_code == 403
    assert client.post(f"/api/employees/{mgr_emp}/terminate",
                       params={"end_date": "2027-01-01"}, headers=hr).status_code == 403
    # ولا ملفّ نفسه في ما يمسّ حالته.
    assert client.post(f"/api/employees/{hr_emp}/events", params={"kind": "note", "title": "t"},
                       headers=hr).status_code == 403
    # ويكتب على من هو أدنى منه.
    ok = client.post(f"/api/employees/{emp_emp}/events", params={"kind": "note", "title": "ملاحظة"},
                     headers=hr)
    assert ok.status_code == 200, ok.text
    db = SessionLocal()
    try:
        purge(db, "employee_events", [ok.json()["id"]])
        db.commit()
    finally:
        db.close()
    # والمدير يكتب على من هو أدنى (HR).
    assert client.post(f"/api/employees/{hr_emp}/events", params={"kind": "note", "title": "م"},
                       headers=mgr).status_code == 200
    db = SessionLocal()
    try:
        purge(db, "employee_events", [e.id for e in db.scalars(select(models.EmployeeEvent).where(
            models.EmployeeEvent.employee_id == hr_emp)).all()])
        db.commit()
    finally:
        db.close()


def test_internal_admin_requests_and_on_behalf_follow_the_hierarchy(client):
    mgr, hr, dele, emp = _h(client, MGR), _h(client, HR), _h(client, DEL), _h(client, EMP)
    mgr_emp = _me(client, mgr)["employee_id"]
    ded = {"request_type_code": "ADMDED",
           "payload_json": {"deduction_amount": 1, "reason": "x", "payroll_month": "2026-10"}}
    assert client.post("/api/requests", headers=emp, json=ded).status_code == 403, "موظفٌ فتح ADMDED"
    assert client.post("/api/requests", headers=dele, json={**ded, "employee_id": mgr_emp}
                       ).status_code == 403, "مندوبٌ قدّم خصمًا باسم المدير"
    # HR لا يقدّم باسم من هو أعلى منه، حتى لطلبٍ عاديّ.
    assert client.post("/api/requests", headers=hr, json={
        "employee_id": mgr_emp, "request_type_code": "REQCERTSAL",
        "payload_json": {"purpose": "x", "language": "ar"}}).status_code == 403
    # وصاحب السلطة يفتحه لمن هو أدنى.
    emp_emp = _me(client, emp)["employee_id"]
    ok = client.post("/api/requests", headers=hr, json={**ded, "employee_id": emp_emp})
    assert ok.status_code == 201, ok.text
    db = SessionLocal()
    try:
        purge(db, "requests", [ok.json()["id"]])
        db.commit()
    finally:
        db.close()


def test_hr_cannot_delegate_a_managers_authority(client):
    hr, mgr = _h(client, HR), _h(client, MGR)
    mid, hid = _me(client, mgr)["id"], _me(client, hr)["id"]
    body = {"delegate_user_id": hid, "reason": "x",
            "starts_at": datetime.utcnow().isoformat(),
            "ends_at": (datetime.utcnow() + timedelta(days=2)).isoformat()}
    r = client.post("/api/delegations", params={"delegator_user_id": mid}, headers=hr, json=body)
    assert r.status_code == 403, r.text
