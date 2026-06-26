# -*- coding: utf-8 -*-
"""اختبار محرّك الطلبات end-to-end: طلب إجازة عبر كل المراحل + إلغاء المدير."""
import io

from tests.conftest import auth_headers, login


def _emp_id(client):
    token = login(client, "100000000001", "manager123")
    emps = client.get("/api/employees", headers=auth_headers(token)).json()
    # الموظف صاحب الخدمة الذاتية (أحمد)
    return next(e["id"] for e in emps if e["civil_id"] == "100000000101")


def test_full_leave_workflow(client):
    emp_token = login(client, "100000000101", "emp12345")
    # 1) العامل يقدّم طلب إجازة
    r = client.post("/api/requests", headers=auth_headers(emp_token), json={
        "request_type_code": "leave",
        "payload_json": {"start_date": "2026-08-01", "end_date": "2026-08-10",
                         "days": 10, "reason": "سفر"},
    })
    assert r.status_code == 201, r.text
    req_id = r.json()["id"]
    assert r.json()["status"] == "pending"

    # 2) مسؤول الفرع يعتمد (أول مرحلة)
    sup = login(client, "100000000005", "sup12345")
    r = client.post(f"/api/requests/{req_id}/decide", headers=auth_headers(sup),
                    json={"decision": "approved"})
    assert r.status_code == 200, r.text

    # 3) المدير العام يعتمد
    mgr = login(client, "100000000001", "manager123")
    r = client.post(f"/api/requests/{req_id}/decide", headers=auth_headers(mgr),
                    json={"decision": "approved"})
    assert r.status_code == 200, r.text

    # 4) HR يعتمد → الحالة awaiting_signature
    hr = login(client, "100000000002", "hr12345")
    r = client.post(f"/api/requests/{req_id}/decide", headers=auth_headers(hr),
                    json={"decision": "approved"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "awaiting_signature"

    # HR يحدد موعد التوقيع
    r = client.post(f"/api/requests/{req_id}/appointment", headers=auth_headers(hr),
                    json={"scheduled_at": "2026-07-20T10:00:00", "location": "مقر الشركة"})
    assert r.status_code == 200

    # 5) HR يرفع النسخة الموقّعة → ينتقل لمرحلة المندوب (awaiting_delegate)
    files = {"file": ("signed.pdf", io.BytesIO(b"signed-content"), "application/pdf")}
    r = client.post(f"/api/requests/{req_id}/documents", headers=auth_headers(hr),
                    data={"kind": "signed_scan"}, files=files)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "awaiting_delegate"

    # 6) المندوب يرفع إذن المغادرة → completed
    delegate = login(client, "100000000004", "deleg123")
    files = {"file": ("exit.pdf", io.BytesIO(b"exit-permit"), "application/pdf")}
    r = client.post(f"/api/requests/{req_id}/documents", headers=auth_headers(delegate),
                    data={"kind": "exit_permit"}, files=files)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"

    # المستند المُولَّد متاح
    r = client.get(f"/api/requests/{req_id}/document/generated_pdf", headers=auth_headers(hr))
    assert r.status_code == 200


def test_manager_can_cancel_anytime(client):
    emp_token = login(client, "100000000101", "emp12345")
    r = client.post("/api/requests", headers=auth_headers(emp_token), json={
        "request_type_code": "leave",
        "payload_json": {"start_date": "2026-09-01", "end_date": "2026-09-05", "days": 5},
    })
    req_id = r.json()["id"]
    mgr = login(client, "100000000001", "manager123")
    r = client.post(f"/api/requests/{req_id}/cancel?note=ظروف+العمل", headers=auth_headers(mgr))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"


def test_request_stages_progress(client):
    """مسار الطلب يعكس التسلسل الهرمي: مرحلة تمّت، الحالية، والباقي قادم."""
    emp_token = login(client, "100000000101", "emp12345")
    r = client.post("/api/requests", headers=auth_headers(emp_token), json={
        "request_type_code": "leave",
        "payload_json": {"start_date": "2026-10-01", "end_date": "2026-10-03", "days": 3},
    })
    req_id = r.json()["id"]
    # المرحلة 0 الآن (مسؤول الفرع)
    detail = client.get(f"/api/requests/{req_id}", headers=auth_headers(emp_token)).json()
    states = [s["state"] for s in detail["stages"]]
    assert states[0] == "current"
    assert states[1] == "pending"

    # بعد اعتماد مسؤول الفرع → المرحلة 0 تمّت، المرحلة 1 الحالية
    sup = login(client, "100000000005", "sup12345")
    client.post(f"/api/requests/{req_id}/decide", headers=auth_headers(sup),
                json={"decision": "approved", "note": "موافق"})
    detail = client.get(f"/api/requests/{req_id}", headers=auth_headers(emp_token)).json()
    assert detail["stages"][0]["state"] == "done"
    assert detail["stages"][0]["approver_name"]  # يظهر اسم المعتمِد
    assert detail["stages"][1]["state"] == "current"


def test_salary_certificate_to_pickup(client):
    emp_token = login(client, "100000000101", "emp12345")
    r = client.post("/api/requests", headers=auth_headers(emp_token), json={
        "request_type_code": "salary_certificate",
        "payload_json": {"addressed_to": "بنك الكويت", "purpose": "قرض"},
    })
    req_id = r.json()["id"]
    mgr = login(client, "100000000001", "manager123")
    r = client.post(f"/api/requests/{req_id}/decide", headers=auth_headers(mgr),
                    json={"decision": "approved"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ready_for_pickup"
