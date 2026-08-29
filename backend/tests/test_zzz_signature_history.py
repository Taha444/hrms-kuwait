# -*- coding: utf-8 -*-
"""SIG-H1/SIG-H3 — تحقيق قبل إصلاح.

البلاغ: ``/api/me/signature/history`` «يرجع فارًغا».

**والتحقيق قلب السؤال**: النقطة سليمة. تُرجع فارًغا لمن لا نسخ له —
وهو الجواب الصحيح لا عطل. والأمر الفعلي أن **الواجهة لا تستدعيها
إطلاًقا**: ``MyProfile.tsx`` ينادي ``/me/signature`` و``/me/signature/image``
وحدهما.

فلا شيء يُصلَح هنا. والسؤال الباقي قرار لا هندسة: أتُبنى شاشة تعرض هذا
السجل، أم تُحذف النقطة؟ (``SIG-H2``)

وبناء ميزة لنقطة مهجورة شغل ضائع، وحذف نقطة مستعمَلة كسر. فيُقاس
الاستعمال ولا يُحدس — وهذه الاختبارات تحرس ذلك القياس.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select

from app import models
from app.database import SessionLocal
from app.endpoint_inventory import unused_endpoints
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"


def _frontend_mentions(needle: str) -> bool:
    for f in FRONTEND.rglob("*"):
        if f.suffix in (".ts", ".tsx", ".js", ".jsx") and f.is_file():
            try:
                if needle in f.read_text(encoding="utf-8"):
                    return True
            except OSError:
                continue
    return False


def test_the_endpoint_is_not_broken_it_is_unused(client):
    """**نتيجة التحقيق**: لا عطل في النقطة، ولا استدعاء لها.

    لو أُصلحت النقطة لأُنفق شغل على ما ليس معطًلا، ولبقي السبب الحقيقي —
    غياب الشاشة — قائًما.
    """
    assert not _frontend_mentions("signature/history"), (
        "صارت الواجهة تستدعيها — راجع قرار SIG-H2 قبل أي حذف"
    )


def test_it_returns_real_records_when_versions_exist(client):
    """الفراغ نطاق صحيح لا خلل: من له نسخ تُعاد نسخُه كاملة."""
    db = SessionLocal()
    try:
        uid = db.scalar(select(models.User.id).where(
            models.User.civil_id == HR[0]))
        n = db.scalar(select(func.count()).select_from(
            models.UserSignatureVersion).where(
                models.UserSignatureVersion.user_id == uid)) or 0
    finally:
        db.close()
    hdr = auth_headers(login(client, *HR))
    r = client.get("/api/me/signature/history", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["versions"]) == n, (
        f"القاعدة فيها {n} نسخة والنقطة أعادت {len(body['versions'])}"
    )
    if n:
        v = body["versions"][0]
        for field in ("version", "checksum_sha256", "reference_no"):
            assert v.get(field), f"نسخة بلا «{field}» — السجل ناقص لا فارغ"


def test_an_empty_history_is_correct_not_a_defect(client):
    """ومن لا نسخة له يُعاد له فراغ — وهذا هو الجواب الصحيح."""
    hdr = auth_headers(login(client, "100000000001", "manager123"))
    r = client.get("/api/me/signature/history", headers=hdr)
    assert r.status_code == 200
    db = SessionLocal()
    try:
        uid = db.scalar(select(models.User.id).where(
            models.User.civil_id == "100000000001"))
        n = db.scalar(select(func.count()).select_from(
            models.UserSignatureVersion).where(
                models.UserSignatureVersion.user_id == uid)) or 0
    finally:
        db.close()
    assert len(r.json()["versions"]) == n


# ---------------------------------------------------------------------------
# SIG-H3 — الجرد: أداة تُقاس لا تُصدَّق
# ---------------------------------------------------------------------------
def test_the_inventory_does_not_flag_a_clearly_used_endpoint():
    """أداة تُبلّغ عن كل شيء لا تُبلّغ عن شيء.

    ``/api/tasks/my`` تستدعيه صفحة المهام حرفًيا. ظهوره في القائمة يعني
    أن الكاشف يطابق خطأً، فتصير القائمة كلها بلا قيمة.
    """
    flagged = {r["path"] for r in unused_endpoints()}
    for used in ("/api/tasks/my", "/api/auth/login", "/api/tasks/count"):
        assert used not in flagged, f"«{used}» مستعمَل وأُدرج كمهجور"


def test_the_inventory_finds_the_endpoint_that_started_this():
    """والاتجاه المعاكس: يلتقط ما نعرف أنه غير مستدعى."""
    flagged = {r["path"] for r in unused_endpoints()}
    assert "/api/me/signature/history" in flagged, (
        "الجرد لم يلتقط النقطة التي فتحت التحقيق"
    )


def test_the_inventory_reports_something_actionable():
    """قائمة فارغة أو تشمل كل شيء كلتاهما بلا فائدة."""
    from app.main import app
    total = len([r for r in app.routes
                 if getattr(r, "path", "").startswith("/api")
                 and (getattr(r, "methods", set()) - {"HEAD", "OPTIONS"})])
    flagged = unused_endpoints()
    assert 0 < len(flagged) < total, (
        f"الجرد أدرج {len(flagged)} من {total} — لا يفصل شيًئا"
    )
