# -*- coding: utf-8 -*-
"""SEC-HEADERS tests — يتحقق من كل ترويسة أمنية مطلوبة (Mozilla Observatory)."""


def _headers(client, path="/api/health") -> dict:
    """يجيب استجابة ويحوّل الترويسات لـ dict lower-case."""
    r = client.get(path)
    assert r.status_code == 200
    return {k.lower(): v for k, v in r.headers.items()}


def test_hsts_header_present_with_one_year(client):
    """HSTS يجبر HTTPS لمدة سنة على الأقل، ويشمل subdomains."""
    h = _headers(client)
    hsts = h.get("strict-transport-security", "")
    assert "max-age=" in hsts
    # قيمة max-age بالثواني — سنة = 31,536,000
    import re
    m = re.search(r"max-age=(\d+)", hsts)
    assert m and int(m.group(1)) >= 31536000
    assert "includesubdomains" in hsts.lower()


def test_x_content_type_options_nosniff(client):
    h = _headers(client)
    assert h.get("x-content-type-options") == "nosniff"


def test_referrer_policy_strict_origin_when_cross_origin(client):
    h = _headers(client)
    assert h.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_permissions_policy_restricts_sensitive_features(client):
    """Permissions-Policy يمنع payment/usb/microphone كحد أدنى."""
    h = _headers(client)
    pp = h.get("permissions-policy", "")
    for feature in ("payment=()", "usb=()", "microphone=()"):
        assert feature in pp, f"missing feature restriction: {feature}"


def test_csp_header_has_all_required_directives(client):
    """CSP يحوي كل التوجيهات اللي فشل فيها الاختبار السابق."""
    h = _headers(client)
    csp = h.get("content-security-policy", "")
    # التوجيهات الأساسية اللي أشعلت الفشل
    for directive in (
        "default-src 'self'",
        "script-src 'self'",  # بلا unsafe-inline
        "object-src 'none'",  # لا Flash/Java
        "base-uri 'self'",    # يمنع سرقة الـ base
        "form-action 'self'", # يمنع سرقة النماذج
        "frame-ancestors 'self'",  # يمنع clickjacking
    ):
        assert directive in csp, f"CSP missing: {directive}"
    # يجب ألا يحوي unsafe-inline في script-src (ضعف رئيسي في التقرير)
    # ملاحظة: unsafe-inline موجود في style-src فقط، وهذا مقبول
    assert "script-src 'self' 'unsafe-inline'" not in csp
    assert "script-src 'self' 'unsafe-eval'" not in csp


def test_cross_origin_policies_set(client):
    """COOP + CORP للعزل الكامل."""
    h = _headers(client)
    assert h.get("cross-origin-opener-policy") == "same-origin"
    assert h.get("cross-origin-resource-policy") == "same-origin"


def test_x_frame_options_present(client):
    """X-Frame-Options موجود للتوافق مع browsers القديمة (frame-ancestors في CSP هو الأصل)."""
    h = _headers(client)
    assert h.get("x-frame-options") in ("SAMEORIGIN", "DENY")


def test_headers_apply_to_api_json_and_html_alike(client):
    """الترويسات مطبقة على كل استجابة، مش على HTML فقط."""
    r_api = client.get("/api/health")
    r_manifest = client.get("/api/manifest")
    for r in (r_api, r_manifest):
        assert r.status_code == 200
        assert "strict-transport-security" in {k.lower() for k in r.headers}
        assert "content-security-policy" in {k.lower() for k in r.headers}
