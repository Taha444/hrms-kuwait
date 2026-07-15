# -*- coding: utf-8 -*-
"""V1.5 Phase 1 tests — Migration Registry + Manifest + backward-compat resolver."""
from tests.conftest import auth_headers, login


def test_manifest_reports_v15_registry_counts(client):
    """/api/manifest يعرض spec + registry بالأعداد الصحيحة (29 workflows, 25 OD, 6 RPT, 2 SYS, 9 layouts)."""
    r = client.get("/api/manifest")
    assert r.status_code == 200
    m = r.json()
    assert m["service"] == "hrms-kuwait"
    assert m["spec"]["current_spec"].startswith("V1.5")
    reg = m["registry"]
    assert reg["canonical_workflows"] == 29
    assert reg["canonical_documents"] == 25
    assert reg["reports"] == 6
    assert reg["system_records"] == 2
    assert reg["layouts"] == 9
    assert reg["migration_version"] == "v1.5-consolidated-rev-2"


def test_version_endpoint_still_works_for_backward_compat(client):
    """/api/version يبقى للتوافق العكسي (يعيد subset من manifest)."""
    r = client.get("/api/version")
    assert r.status_code == 200
    v = r.json()
    for k in ("service", "version", "commit", "build_time", "environment"):
        assert k in v


def test_registry_endpoint_lists_canonical_and_aliases(client):
    """GET /api/requests/registry يعرض الـ canonical + alias tables."""
    admin = login(client, "000000000000", "admin123")
    r = client.get("/api/requests/registry", headers=auth_headers(admin))
    assert r.status_code == 200
    data = r.json()
    assert "WF-001" in data["canonical_workflows"]
    assert data["canonical_workflows"]["WF-001"]["name_ar"] == "طلب إجازة عادي"
    assert data["legacy_request_aliases"]["leave"]["canonical"] == "WF-001"
    assert data["legacy_template_aliases"]["PRN-001"] == "OD-001"
    assert data["legacy_template_aliases"]["PRN-029"] == "RPT-001"


def test_resolver_accepts_canonical_code_when_db_has_legacy(client):
    """Forward-compat: عميل حديث يمرر WF-001 يجب أن يجد نوع الطلب المسمى في الـ seed 'leave'."""
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "WF-001",  # canonical V1.5 code
        "payload_json": {"start_date": "2026-08-15", "end_date": "2026-08-17", "days": 3},
    })
    # لا يجب أن يفشل بـ 404 "نوع الطلب غير معرّف"؛ يجب أن يقبله ويعيد 201
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"


def test_resolver_returns_none_for_unknown_canonical(client):
    """كود canonical غير موجود في الـ seed ولا legacy — يجب أن يعيد 404 صريح."""
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.post("/api/requests", headers=emp, json={
        "request_type_code": "WF-999",
        "payload_json": {"details": "x"},
    })
    assert r.status_code == 404


def test_registry_module_direct_calls():
    """تحقق مباشر من دوال registry دون HTTP layer."""
    from app.v15_registry import resolve_request, resolve_template, summary
    # canonical passthrough
    r = resolve_request("WF-001")
    assert r["canonical"] == "WF-001"
    # legacy aliases
    assert resolve_request("leave")["canonical"] == "WF-001"
    assert resolve_request("advance")["subtype"] == "ADVANCE"
    assert resolve_request("REQ-EOS-039")["canonical"] == "WF-025"
    assert resolve_request("ADM-WARN-045")["canonical"] == "WF-014"
    assert resolve_request("UNKNOWN") == {}
    # template aliases
    assert resolve_template("PRN-001") == "OD-001"
    assert resolve_template("HRMS-PR-029") == "RPT-001"
    assert resolve_template("PRN-042") == "SYS-001"
    assert resolve_template("OD-005") == "OD-005"  # passthrough
    assert resolve_template("UNKNOWN") is None
    # summary shape
    s = summary()
    assert s["canonical_workflows"] == 29
    assert s["migration_version"].startswith("v1.5")
