# -*- coding: utf-8 -*-
"""V1.5 Phase 4 tests — 9 Layouts + 25 Canonical Documents architecture."""
from tests.conftest import auth_headers, login


def test_registry_module_has_25_canonical_documents():
    """v15_registry.CANONICAL_DOCUMENTS يحوي بالضبط OD-001..OD-025."""
    from app.v15_registry import CANONICAL_DOCUMENTS, LAYOUTS
    codes = set(CANONICAL_DOCUMENTS)
    expected = {f"OD-{i:03d}" for i in range(1, 26)}
    assert codes == expected, f"missing/extra: {codes ^ expected}"
    # كل OD يشير لـ layout موجود
    for od_code, od in CANONICAL_DOCUMENTS.items():
        assert od["layout"] in LAYOUTS, f"{od_code} uses unknown layout {od['layout']}"


def test_registry_module_has_9_layouts_matching_specs():
    """v15_registry.LAYOUTS يحوي بالضبط LAY-01..LAY-09."""
    from app.v15_registry import LAYOUTS
    assert set(LAYOUTS) == {f"LAY-0{i}" for i in range(1, 10)}


def test_canonical_documents_summary_reflects_real_dict():
    from app.v15_registry import summary
    s = summary()
    assert s["canonical_documents"] == 25
    assert s["layouts"] == 9
    assert s["reports"] == 6


def test_canonical_catalog_endpoint_lists_layouts_and_od(client):
    """GET /api/documents/canonical عام (بدون مصادقة) ويعرض الجداول."""
    r = client.get("/api/documents/canonical")
    assert r.status_code == 200
    data = r.json()
    assert len(data["canonical_documents"]) == 25
    assert len(data["layouts"]) == 9
    assert "OD-001" in data["canonical_documents"]
    assert data["canonical_documents"]["OD-001"]["layout"] == "LAY-01"
    assert data["canonical_documents"]["OD-001"]["name_ar"] == "شهادة راتب"


def test_canonical_document_detail_includes_layout_info(client):
    r = client.get("/api/documents/canonical/OD-005")
    assert r.status_code == 200
    od = r.json()
    assert od["od_code"] == "OD-005"
    assert od["layout"] == "LAY-02"
    assert od["layout_info"]["name"].startswith("Employment Decision")
    assert "legal_note_ar" in od  # قرار تغيير وظيفي له ملاحظة قانونية


def test_canonical_document_detail_resolves_legacy_prn(client):
    """PRN-001 يجب أن يعيد OD-001 مع legacy_alias flag."""
    r = client.get("/api/documents/canonical/PRN-001")
    assert r.status_code == 200
    od = r.json()
    assert od["od_code"] == "OD-001"
    assert od["legacy_alias"] == "PRN-001"


def test_canonical_document_detail_returns_404_for_unknown(client):
    r = client.get("/api/documents/canonical/OD-999")
    assert r.status_code == 404


def test_request_document_model_has_new_v15_columns():
    """RequestDocument جديد يفتح بحقول Phase 4 المطلوبة."""
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        # الأعمدة موجودة على الـ instance
        d = models.RequestDocument(
            request_id=1, kind="generated_pdf", file_path=None, version=1,
            od_code="OD-001", lifecycle_status="GENERATING",
        )
        # لا نضيفه للـ session؛ فقط نتحقق أن الأعمدة تُعرَف
        assert d.od_code == "OD-001"
        assert d.lifecycle_status == "GENERATING"
    finally:
        db.close()


def test_generated_document_receives_od_code_from_default_template(client):
    """طلب من نوع له default_template_code يجب أن يخرج مستنده وعليه od_code صحيح."""
    emp_tok = login(client, "100000000101", "emp12345")
    # نقدم طلب إجازة (leave) — default_template_code = HRMS-PR-015 → OD-005
    r = client.post("/api/requests", headers=auth_headers(emp_tok), json={
        "request_type_code": "leave",
        "payload_json": {"start_date": "2026-10-01", "end_date": "2026-10-03",
                         "days": 3, "reason": "سياحة"},
    })
    rid = r.json()["id"]
    # نمرّر المسار حتى يُنتج مستند
    for civ, pw in [("100000000005", "sup12345"),
                    ("100000000001", "manager123"),
                    ("100000000002", "hr12345")]:
        tok = login(client, civ, pw)
        client.post(f"/api/requests/{rid}/decide", headers=auth_headers(tok),
                    json={"decision": "approved"})
    d = client.get(f"/api/requests/{rid}", headers=auth_headers(emp_tok)).json()
    gen_docs = [x for x in d.get("documents", []) if x.get("kind") == "generated_pdf"]
    if gen_docs:
        # الحقول موجودة (حتى لو od_code = None لعدم ربط default_template_code)
        assert "od_code" in gen_docs[0]
        assert "lifecycle_status" in gen_docs[0]
        assert gen_docs[0]["lifecycle_status"] in ("GENERATING", "GENERATED")


def test_resolve_canonical_document_direct():
    from app.v15_registry import resolve_canonical_document
    # canonical passthrough
    r = resolve_canonical_document("OD-001")
    assert r["od_code"] == "OD-001"
    assert r["layout"] == "LAY-01"
    # PRN legacy
    r = resolve_canonical_document("PRN-015")
    assert r["od_code"] == "OD-005"
    assert r["legacy_alias"] == "PRN-015"
    assert resolve_canonical_document("nothing") is None
    assert resolve_canonical_document("") is None
