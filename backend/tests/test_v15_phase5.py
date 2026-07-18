# -*- coding: utf-8 -*-
"""V1.5 Phase 5 tests — feature flags + dual-read demonstration."""
from tests.conftest import auth_headers, login


# =========================================================================
# 1) وحدة feature_flags الأساسية
# =========================================================================
def test_default_flag_value_from_code_when_no_db_row():
    """flag بدون صف في القاعدة يعيد القيمة الافتراضية من REGISTRY."""
    from app.database import SessionLocal
    from app.feature_flags import is_enabled, V15_CANONICAL_DISPLAY, REGISTRY
    db = SessionLocal()
    try:
        # الافتراضي False لكل الـ flags في هذه المرحلة
        assert is_enabled(db, company_id=1, key=V15_CANONICAL_DISPLAY) is False
        assert REGISTRY[V15_CANONICAL_DISPLAY]["default"] is False
    finally:
        db.close()


def _clear_flag(db, key):
    """يحذف كل صفوف flag معيّن (global + كل الشركات) لضمان عزل الاختبارات."""
    from app import models
    for row in db.query(models.FeatureFlag).filter_by(key=key).all():
        db.delete(row)
    db.commit()


def test_global_flag_overrides_default():
    from app.database import SessionLocal
    from app.feature_flags import is_enabled, set_flag, V15_CANONICAL_DISPLAY
    db = SessionLocal()
    try:
        set_flag(db, V15_CANONICAL_DISPLAY, "on", company_id=None)
        assert is_enabled(db, 1, V15_CANONICAL_DISPLAY) is True
        assert is_enabled(db, None, V15_CANONICAL_DISPLAY) is True
    finally:
        _clear_flag(db, V15_CANONICAL_DISPLAY)
        db.close()


def test_company_specific_flag_overrides_global():
    from app.database import SessionLocal
    from app.feature_flags import is_enabled, set_flag, V15_CANONICAL_DISPLAY
    db = SessionLocal()
    try:
        set_flag(db, V15_CANONICAL_DISPLAY, "on", company_id=None)
        set_flag(db, V15_CANONICAL_DISPLAY, "off", company_id=1)
        assert is_enabled(db, 1, V15_CANONICAL_DISPLAY) is False  # الشركة تعلو
        assert is_enabled(db, 2, V15_CANONICAL_DISPLAY) is True   # الشركة 2 على العام
    finally:
        _clear_flag(db, V15_CANONICAL_DISPLAY)
        db.close()


def test_set_flag_rejects_unknown_key():
    from app.database import SessionLocal
    from app.feature_flags import set_flag
    db = SessionLocal()
    try:
        try:
            set_flag(db, "xyz_bogus_key", "on")
            assert False, "should have raised"
        except ValueError as e:
            assert "غير معروف" in str(e)
    finally:
        db.close()


def test_list_effective_shows_source():
    from app.database import SessionLocal
    from app.feature_flags import list_effective, set_flag, V15_STATUS_LABELS
    db = SessionLocal()
    try:
        set_flag(db, V15_STATUS_LABELS, "on", company_id=1)
        eff = list_effective(db, company_id=1)
        assert eff[V15_STATUS_LABELS]["value"] is True
        assert eff[V15_STATUS_LABELS]["source"] == "company"
        # شركة أخرى تعود للـ default
        eff2 = list_effective(db, company_id=2)
        assert eff2[V15_STATUS_LABELS]["source"] == "default"
    finally:
        _clear_flag(db, V15_STATUS_LABELS)
        db.close()


# =========================================================================
# 2) API — super_admin فقط
# =========================================================================
def test_feature_flags_registry_endpoint_requires_super_admin(client):
    hr_tok = auth_headers(login(client, "100000000002", "hr12345"))
    r = client.get("/api/feature-flags/registry", headers=hr_tok)
    assert r.status_code == 403


def test_feature_flags_registry_lists_known_keys(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    r = client.get("/api/feature-flags/registry", headers=admin)
    assert r.status_code == 200
    keys = set(r.json())
    assert "v15_canonical_display" in keys
    assert "v15_status_labels" in keys
    assert "v15_document_lifecycle" in keys


def test_super_admin_can_set_and_delete_flag(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    r = client.post("/api/feature-flags", headers=admin, json={
        "key": "v15_canonical_display", "value": "on", "company_id": 1,
        "note": "تفعيل تجريبي",
    })
    assert r.status_code == 201
    flag_id = r.json()["id"]
    # القراءة تعكس التفعيل
    eff = client.get("/api/feature-flags", headers=admin, params={"company_id": 1}).json()
    assert eff["v15_canonical_display"]["value"] is True
    assert eff["v15_canonical_display"]["source"] == "company"
    # الحذف يرجعها للـ default
    r = client.delete(f"/api/feature-flags/{flag_id}", headers=admin)
    assert r.status_code == 200
    eff2 = client.get("/api/feature-flags", headers=admin, params={"company_id": 1}).json()
    assert eff2["v15_canonical_display"]["source"] == "default"


# =========================================================================
# 3) تكامل: الـ flag يغيّر شكل /api/requests/types (dual-read)
# =========================================================================
def test_types_default_shows_legacy_code_as_primary_with_canonical_metadata(client):
    """الافتراضي: primary_code = legacy، canonical_code موجود كمعلومة إضافية.
    نستخدم HR (شركة 1) لأن super_admin بلا company_id."""
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    types = client.get("/api/requests/types", headers=hr).json()
    leave = next((t for t in types if t["code"] == "leave"), None)
    assert leave is not None
    assert leave["primary_code"] == "leave"  # legacy default
    assert leave["canonical_code"] == "WF-001"  # metadata
    assert leave["legacy_code"] is None


def test_types_with_canonical_display_flag_flips_primary(client):
    """عند تفعيل v15_canonical_display لشركة 1: primary_code = canonical WF-*."""
    admin = auth_headers(login(client, "000000000000", "admin123"))
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    # فعّل الـ flag لشركة 1 (شركة HR)
    r = client.post("/api/feature-flags", headers=admin, json={
        "key": "v15_canonical_display", "value": "on", "company_id": 1,
    })
    assert r.status_code == 201, r.text
    try:
        types = client.get("/api/requests/types", headers=hr).json()
        leave = next((t for t in types if t["code"] == "leave"), None)
        assert leave is not None
        assert leave["primary_code"] == "WF-001"
        assert leave["legacy_code"] == "leave"
    finally:
        # نظّف — احذف كل صفوف الـ flag
        rows = client.get("/api/feature-flags/raw", headers=admin).json()
        for row in rows:
            if row["key"] == "v15_canonical_display":
                client.delete(f"/api/feature-flags/{row['id']}", headers=admin)


def test_registry_endpoint_still_public_to_authenticated_users(client):
    """GET /api/requests/registry يبقى للمستخدمين العاديين (Phase 1 endpoint)."""
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.get("/api/requests/registry", headers=emp)
    assert r.status_code == 200
