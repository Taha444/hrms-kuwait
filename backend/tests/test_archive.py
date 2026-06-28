# -*- coding: utf-8 -*-
"""اختبارات أرشيف الشركة والفرع: العرض، رقم الملف، رفع مستند رسمي، والعزل."""
import io

from tests.conftest import auth_headers, login


def test_company_archive_lists_doc_types(client):
    mgr = login(client, "100000000001", "manager123")
    r = client.get("/api/archive/company", headers=auth_headers(mgr))
    assert r.status_code == 200, r.text
    d = r.json()
    codes = [t["code"] for t in d["doc_types"]]
    assert "incorporation_contract" in codes and "commercial_reg" in codes


def test_set_company_file_number(client):
    # بيانات/إعدادات الشركة للإدارة العليا فقط (المدير لا يعدّل إعدادات النظام)
    admin = login(client, "000000000000", "admin123")
    h = auth_headers(admin)
    r = client.put("/api/archive/company/info", headers=h,
                   params={"file_number": "MF-12345", "company_id": 1})
    assert r.status_code == 200
    again = client.get("/api/archive/company", headers=h, params={"company_id": 1}).json()
    assert again["company"]["file_number"] == "MF-12345"


def test_upload_company_official_document(client):
    mgr = login(client, "100000000001", "manager123")
    h = auth_headers(mgr)
    cid = client.get("/api/archive/company", headers=h).json()["company"]["id"]
    files = {"file": ("reg.pdf", io.BytesIO(b"official-doc-content"), "application/pdf")}
    r = client.post("/api/documents/upload", headers=h, files=files, data={
        "entity_type": "company", "entity_id": str(cid),
        "document_type_code": "commercial_reg", "title": "السجل التجاري"})
    assert r.status_code == 200, r.text
    docs = client.get("/api/archive/company", headers=h).json()["documents"]
    assert any(x["type"] == "commercial_reg" for x in docs)


def test_branch_archive(client):
    mgr = login(client, "100000000001", "manager123")
    h = auth_headers(mgr)
    bid = client.get("/api/branches", headers=h).json()[0]["id"]
    r = client.get(f"/api/archive/branch/{bid}", headers=h)
    assert r.status_code == 200
    assert any(t["code"] == "branch_license" for t in r.json()["doc_types"])


def test_archive_isolation(client):
    # مدير الشركة 1 لا يصل لأرشيف فرع الشركة 2
    admin = login(client, "000000000000", "admin123")
    b2 = client.get("/api/branches", headers=auth_headers(admin), params={"company_id": 2}).json()[0]["id"]
    mgr1 = login(client, "100000000001", "manager123")
    r = client.get(f"/api/archive/branch/{b2}", headers=auth_headers(mgr1))
    assert r.status_code == 404
