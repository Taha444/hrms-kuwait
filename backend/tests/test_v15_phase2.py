# -*- coding: utf-8 -*-
"""V1.5 Phase 2 tests — Canonical Status Model + Step Types."""
from tests.conftest import auth_headers, login


def test_status_model_endpoint_exposes_v15_canonical_taxonomy(client):
    """/api/requests/status-model يعرض الـ 9 حالات request + 8 حالات document + 6 step types."""
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.get("/api/requests/status-model", headers=emp)
    assert r.status_code == 200
    m = r.json()
    # request lifecycle: DRAFT, SUBMITTED, IN_REVIEW, NEEDS_INFO, APPROVED, IN_EXECUTION,
    #                    COMPLETED, REJECTED, CANCELLED, FAILED
    assert set(m["request_lifecycle"]) == {
        "DRAFT", "SUBMITTED", "IN_REVIEW", "NEEDS_INFO", "APPROVED",
        "IN_EXECUTION", "COMPLETED", "REJECTED", "CANCELLED", "FAILED",
    }
    # document lifecycle
    assert "GENERATED" in m["document_lifecycle"]
    assert "NOT_REQUIRED" in m["document_lifecycle"]
    # 6 step types
    assert set(m["step_types"]) == {
        "DECISION", "VALIDATION", "EXECUTION", "ACKNOWLEDGEMENT",
        "NOTIFICATION", "AUTOMATION",
    }
    # internal → v15 mapping
    assert m["internal_to_v15"]["pending"] == "IN_REVIEW"
    assert m["internal_to_v15"]["returned"] == "NEEDS_INFO"
    assert m["internal_to_v15"]["completed"] == "COMPLETED"


def test_status_map_includes_v15_canonical_field(client):
    """/api/requests/status-map يعرض حقل v15 لكل حالة داخلية (توافق مع Phase 2)."""
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.get("/api/requests/status-map", headers=emp)
    assert r.status_code == 200
    m = r.json()
    assert m["pending"]["v15"] == "IN_REVIEW"
    assert m["awaiting_signature"]["v15"] == "IN_EXECUTION"
    assert m["completed"]["v15"] == "COMPLETED"
    assert m["returned"]["v15"] == "NEEDS_INFO"


def test_request_detail_exposes_canonical_workflow_and_v15_status(client):
    """طلب فردي يعرض canonical_workflow (WF-XXX) + status_v15 للتوافق مع V1.5."""
    emp_token = login(client, "100000000101", "emp12345")
    r = client.post("/api/requests", headers=auth_headers(emp_token), json={
        "request_type_code": "leave",
        "payload_json": {"start_date": "2026-09-15", "end_date": "2026-09-16", "days": 2},
    })
    rid = r.json()["id"]
    d = client.get(f"/api/requests/{rid}", headers=auth_headers(emp_token)).json()
    # الطلب المخزَّن بكود قديم "leave" — يجب أن يعرض WF-001 وIN_REVIEW
    assert d["canonical_workflow"] == "WF-001"
    assert d["status_v15"] == "IN_REVIEW"


def test_new_workflow_types_get_step_type_annotation():
    """كل خطوة في approval_chain لأنواع الطلب الجديدة يحمل step_type."""
    from app import workflow
    # نأخذ نوعًا اُنشئ عبر _simple (كل الـ44 المتبقية)
    reqtype = workflow._simple("TESTXX", "اختبار", "cat", ["hr", "company_manager"])
    chain = reqtype["approval_chain_json"]
    assert all(s.get("step_type") == "DECISION" for s in chain)


def test_v15_status_module_direct_calls():
    from app.v15_status import request_v15_status, as_dict, REQUEST_LIFECYCLE, STEP_TYPES
    assert request_v15_status("pending") == "IN_REVIEW"
    assert request_v15_status("returned") == "NEEDS_INFO"
    assert request_v15_status("unknown_state") == "UNKNOWN_STATE"

    # terminal state markers
    assert REQUEST_LIFECYCLE["COMPLETED"].get("terminal") is True
    assert REQUEST_LIFECYCLE["REJECTED"].get("terminal") is True
    assert REQUEST_LIFECYCLE["CANCELLED"].get("terminal") is True
    assert "terminal" not in REQUEST_LIFECYCLE["IN_REVIEW"]

    # step types have expected actions
    assert "approve" in STEP_TYPES["DECISION"]["actions"]
    assert "valid" in STEP_TYPES["VALIDATION"]["actions"]
    assert "acknowledged" in STEP_TYPES["ACKNOWLEDGEMENT"]["actions"]

    d = as_dict()
    assert d["spec_reference"].startswith("V1.5")
