# -*- coding: utf-8 -*-
"""ARC-01/02/03 — النسخ السابقة قابلة للعرض والتنزيل.

الخادم يحتفظ بكل إصدار، والتنزيل والتدقيق يعملان — ولم يكن في الواجهة باب
إليها. فالنسخة القديمة «محفوظة» ولا سبيل إلى فتحها، ووجودها في القاعدة
وحده لا يفيد من يحتاجها.

والقاعدة التي تحرسها هذه الاختبارات: **الرفع يضيف ولا يمسح**. مستند رسمي
استُبدل هو مستند له تاريخ، ومحو القديم يمحو الدليل على ما كان.
"""
from __future__ import annotations

import io

import pytest

from app import models
from app.database import SessionLocal
from app.storage import key_exists

from .conftest import auth_headers, login

HR = ("100000000002", "hr12345")
EMPLOYEE = ("100000000101", "emp12345")
OTHER_COMPANY_HR = ("200000000002", "hr12345")

ENTITY_TYPE = "company"
ENTITY_ID = 1
DOC_TYPE = "contract"


def _upload(client, hdr, content: bytes, name: str):
    return client.post(
        "/api/documents/upload", headers=hdr,
        data={"entity_type": ENTITY_TYPE, "entity_id": str(ENTITY_ID),
              "document_type_code": DOC_TYPE, "title": name},
        files={"file": (f"{name}.txt", io.BytesIO(content), "text/plain")},
    )


@pytest.fixture
def two_versions(client):
    """مستند له إصداران — v1 ثم v2 يستبدله."""
    hdr = auth_headers(login(client, *HR))
    a = _upload(client, hdr, "النسخة الأولى".encode("utf-8"), "عقد v1")
    assert a.status_code in (200, 201), f"تعذّر رفع v1: {a.text[:200]}"
    b = _upload(client, hdr, "النسخة الثانية".encode("utf-8"), "عقد v2")
    assert b.status_code in (200, 201), f"تعذّر رفع v2: {b.text[:200]}"
    yield hdr
    db = SessionLocal()
    try:
        db.query(models.Document).filter(
            models.Document.entity_type == ENTITY_TYPE,
            models.Document.entity_id == ENTITY_ID,
            models.Document.document_type_code == DOC_TYPE).delete()
        db.commit()
    finally:
        db.close()


def _history(client, hdr):
    r = client.get("/api/documents/history", headers=hdr, params={
        "entity_type": ENTITY_TYPE, "entity_id": ENTITY_ID,
        "document_type_code": DOC_TYPE})
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1–3) v2 حالية · v1 موجودة في التاريخ
# ---------------------------------------------------------------------------
def test_history_lists_both_versions(client, two_versions):
    rows = _history(client, two_versions)
    assert len(rows) >= 2, f"التاريخ لا يحمل الإصدارين: {rows}"
    current = [r for r in rows if r["is_current"]]
    assert len(current) == 1, "أكثر من نسخة حالية — أو لا نسخة"
    assert current[0]["version"] == max(r["version"] for r in rows), (
        "الحالية ليست الأحدث"
    )


def test_history_carries_uploader_and_size(client, two_versions):
    """من رفعها وحجمها — بلا هذين لا تُميَّز نسخة عن أخرى.

    ومن يفتّش في إصدارات مستند رسمي يسأل أوًلا «من غيّره ومتى؟».
    """
    for row in _history(client, two_versions):
        assert row["uploaded_by_name"], f"إصدار بلا صاحب: v{row['version']}"
        assert row["size_bytes"], f"إصدار بلا حجم: v{row['version']}"
        assert row.get("version_count", 0) >= 2


# ---------------------------------------------------------------------------
# 4–5) تنزيل نسخة قديمة يعمل، والقديمة لم تُحذف من التخزين
# ---------------------------------------------------------------------------
def test_old_version_downloads_with_its_own_content(client, two_versions):
    rows = _history(client, two_versions)
    old = next(r for r in rows if not r["is_current"])
    r = client.get(f"/api/documents/{old['id']}/download", headers=two_versions)
    assert r.status_code == 200, r.text
    assert "الأولى" in r.content.decode("utf-8"), (
        "تنزيل النسخة القديمة أعاد محتوى غيرها"
    )


def test_old_version_file_is_not_deleted_from_storage(client, two_versions):
    """الرفع يضيف ولا يمسح — محو القديم يمحو الدليل على ما كان."""
    rows = _history(client, two_versions)
    db = SessionLocal()
    try:
        for row in rows:
            doc = db.get(models.Document, row["id"])
            assert doc.file_path and key_exists(doc.file_path), (
                f"ملف الإصدار v{doc.version} غير موجود في التخزين"
            )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 6) التنزيل مسجَّل في التدقيق
# ---------------------------------------------------------------------------
def test_downloading_an_old_version_is_audited(client, two_versions):
    """نسخة قديمة تُفتح دون أثر تعني تفتيًشا لا يُعرف أنه جرى."""
    rows = _history(client, two_versions)
    old = next(r for r in rows if not r["is_current"])
    client.get(f"/api/documents/{old['id']}/download", headers=two_versions)
    db = SessionLocal()
    try:
        row = db.query(models.AuditLog).filter(
            models.AuditLog.action == "download_document_version"
        ).order_by(models.AuditLog.id.desc()).first()
        assert row is not None, "تنزيل نسخة قديمة بلا سطر تدقيق"
        assert f"v{old['version']}" in (row.detail or ""), (
            f"السجلّ لا يسمّي الإصدار المُنزَّل: {row.detail!r}"
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 7) من لا يملك صلاحية عرض المستند لا يصل القائمة ولا التنزيل المباشر
# ---------------------------------------------------------------------------
def test_versions_require_the_same_permission_as_the_document(client, two_versions):
    """صلاحية النسخ السابقة هي صلاحية المستند — لا تُفتح لمن لا يملك الأصل."""
    rows = _history(client, two_versions)
    old = next(r for r in rows if not r["is_current"])
    emp = auth_headers(login(client, *EMPLOYEE))

    listing = client.get("/api/documents/history", headers=emp, params={
        "entity_type": ENTITY_TYPE, "entity_id": ENTITY_ID,
        "document_type_code": DOC_TYPE})
    assert listing.status_code == 403, (
        f"موظف بلا صلاحية يرى قائمة الإصدارات: {listing.status_code}"
    )
    direct = client.get(f"/api/documents/{old['id']}/download", headers=emp)
    assert direct.status_code == 403, (
        "الإخفاء وحده ليس أماًنا — التنزيل المباشر نجح"
    )


def test_other_company_cannot_download_a_version(client, two_versions):
    rows = _history(client, two_versions)
    old = next(r for r in rows if not r["is_current"])
    other = auth_headers(login(client, *OTHER_COMPANY_HR))
    r = client.get(f"/api/documents/{old['id']}/download", headers=other)
    assert r.status_code in (403, 404), "نسخة شركة أخرى قابلة للتنزيل"


# ---------------------------------------------------------------------------
# 8) مستند بإصدار واحد لا يعرض الزر
# ---------------------------------------------------------------------------
def test_single_version_document_reports_no_history(client):
    """قائمة فيها الحالي وحده تُوهم بوجود تاريخ — فتُخفى."""
    hdr = auth_headers(login(client, *HR))
    r = _upload(client, hdr, b"only one", "وحيد")
    assert r.status_code in (200, 201), r.text
    try:
        rows = _history(client, hdr)
        assert len(rows) == 1
        assert rows[0]["is_current"]
        assert rows[0]["version_count"] == 1, (
            "عدد الإصدارات لا يميّز المستند الوحيد — الزر سيظهر بلا داعٍ"
        )
    finally:
        db = SessionLocal()
        try:
            db.query(models.Document).filter(
                models.Document.entity_type == ENTITY_TYPE,
                models.Document.entity_id == ENTITY_ID,
                models.Document.document_type_code == DOC_TYPE).delete()
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 9) الواجهة: مكوّن واحد لا ثلاثة · 10) رسالة «اختر شركة»
# ---------------------------------------------------------------------------
def test_frontend_mounts_versions_on_every_archive_surface():
    """أرشيف الشركة والفرع ومستندات الموظف — السلوك نفسه في الثلاثة.

    والحارس على المصدر لأن لا مشغّل اختبارات للواجهة.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "frontend" / "src"
    if not root.is_dir():
        pytest.skip("مصدر الواجهة غير موجود في هذه البيئة")

    archive = (root / "pages" / "Archive.tsx").read_text(encoding="utf-8")
    # DocGrid يخدم الشركة والفرع معًا، وCustomDocsSection كذلك
    assert archive.count("<DocumentVersions") >= 2, (
        "النسخ السابقة غير مركّبة على كل أسطح الأرشيف"
    )
    profile = (root / "pages" / "EmployeeProfile.tsx").read_text(encoding="utf-8")
    assert "documents/history" in profile, "مستندات الموظف بلا نسخ سابقة"
    assert "uploaded_by_name" in profile and "size_bytes" in profile, (
        "جدول إصدارات الموظف لا يعرض من رفعها ولا حجمها"
    )


def test_all_companies_shows_a_message_not_a_blank_page():
    """ARC-03 — حالة Empty ليست حالة Loading ليست حالة Unauthorized.

    كانت الصفحة تعرض فراًغا برسالة «لا توجد مستندات بعد» — صحيحة نحوًيا
    وخاطئة معنى: المستندات موجودة، والناقص اختيار الشركة.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "frontend" / "src"
    if not root.is_dir():
        pytest.skip("مصدر الواجهة غير موجود في هذه البيئة")
    archive = (root / "pages" / "Archive.tsx").read_text(encoding="utf-8")
    assert "NeedsCompany" in archive, "لا رسالة عند «كل الشركات»"
    assert "needsCompany ?" in archive, "الرسالة غير مربوطة بالحالة"
