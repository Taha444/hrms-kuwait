# -*- coding: utf-8 -*-
"""اكتمال سجل التدقيق (FIX-012): FORBIDDEN_SCOPE_ACCESS / EXPORT_REPORT / PRINT_DOCUMENT / FILE_DOCUMENT."""
from tests.conftest import auth_headers, login


def test_forbidden_scope_access_is_audited(client):
    mgr1 = auth_headers(login(client, "100000000001", "manager123"))
    # موظف من الشركة 2 — خارج نطاق مدير الشركة 1
    emp2 = login(client, "200000000001", "manager123")
    other_emp_id = client.get("/api/employees", headers=auth_headers(emp2)).json()[0]["id"]

    r = client.get(f"/api/employees/{other_emp_id}", headers=mgr1)
    assert r.status_code == 404

    admin = auth_headers(login(client, "000000000000", "admin123"))
    logs = client.get("/api/audit", headers=admin,
                      params={"company_id": 1, "action": "FORBIDDEN_SCOPE_ACCESS"}).json()
    assert len(logs) >= 1


def test_export_report_is_audited_with_reason(client):
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    # سبب مفقود لتقرير حساس (نهاية خدمة) → 400
    r = client.get("/api/reports/eos/1", headers=hr, params={"fmt": "xlsx"})
    assert r.status_code == 400

    mgr = auth_headers(login(client, "100000000001", "manager123"))
    client.get("/api/reports/employees", headers=mgr, params={"fmt": "csv", "reason": "مراجعة دورية"})
    admin = auth_headers(login(client, "000000000000", "admin123"))
    logs = client.get("/api/audit", headers=admin,
                      params={"company_id": 1, "action": "EXPORT_REPORT"}).json()
    assert any("مراجعة دورية" in (log_.get("detail") or "") for log_ in logs)


def test_print_and_file_document_are_audited(client):
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "salary_certificate",
        "payload_json": {"addressed_to": "بنك", "purpose": "قرض"}})
    rid = r.json()["id"]
    mgr = auth_headers(login(client, "100000000001", "manager123"))
    client.post(f"/api/requests/{rid}/decide", headers=mgr, json={"decision": "approved"})
    client.post(f"/api/requests/{rid}/document/generated_pdf/mark-printed", headers=mgr)
    client.post(f"/api/requests/{rid}/document/generated_pdf/mark-filed", headers=mgr)

    admin = auth_headers(login(client, "000000000000", "admin123"))
    printed = client.get("/api/audit", headers=admin,
                         params={"company_id": 1, "action": "print_document"}).json()
    filed = client.get("/api/audit", headers=admin,
                       params={"company_id": 1, "action": "file_document"}).json()
    assert len(printed) >= 1 and len(filed) >= 1
