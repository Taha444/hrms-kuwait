# -*- coding: utf-8 -*-
"""ما يرفعه مستخدمٌ لا يُخدَم HTML — النوعُ من الامتداد المخزَّن لا من إعلان العميل.

**العطل المقيس**:

- الأرشيفُ والمستنداتُ والتجديدُ تحفظ ``mime=file.content_type`` (ما يُعلنه
  العميل) وتُعيده عند التنزيل: ملفٌّ ``.pdf`` محتواه HTML يُرفع بترويسة
  ``text/html`` فيُخدَم HTML؛ و``nosniff`` يجعل المتصفحَ يصدّقها.
- ومستنداتُ الطلب تُعيد ``text/html`` لكل ``.html`` — وكلُّها مرفوعٌ من مستخدم،
  وصاحبُ الطلب يرفع ما يفتحه المعتمِدُ الأعلى صلاحية.
- والواجهةُ تفتح التنزيلَ بـ``createObjectURL`` + ``window.open``: وثيقةُ blob
  ترث أصلَ التطبيق. فالحمايةُ الباقية كانت ترويسةَ CSP وحدها.

فصار ``storage.served_media_type`` مصدرَ النوع الوحيد: قائمةُ سماحٍ بالامتداد،
و``text/html`` لما يكتبه النظامُ وحده (``forms/``، ``generated/``).
"""
from __future__ import annotations

import io

from sqlalchemy import delete as sa_delete

from app import models
from app.database import SessionLocal
from app.storage import served_media_type
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
_HTML = b"<html><body><script>alert(document.cookie)</script></body></html>"


def test_a_user_uploaded_html_attachment_is_not_served_as_html(client):
    eh = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.post("/api/requests", headers=eh, json={
        "request_type_code": "REQLV", "payload_json": {
            "start_date": "2031-05-01", "end_date": "2031-05-02", "days": 2,
            "leave_type": "sick", "reason": "قياس"}})
    rid = r.json()["id"]
    try:
        u = client.post(f"/api/requests/{rid}/documents", headers=eh,
                        data={"kind": "attachment"},
                        files={"file": ("report.html", io.BytesIO(_HTML), "text/html")})
        assert u.status_code in (200, 201), u.text[:200]
        d = client.get(f"/api/requests/{rid}/document/attachment", headers=eh)
        assert d.status_code == 200, d.text[:200]
        assert "text/html" not in d.headers.get("content-type", ""), d.headers
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.RequestDocument).where(
                models.RequestDocument.request_id == rid))
            db.execute(sa_delete(models.Task).where(
                models.Task.related_entity_type == "request",
                models.Task.related_entity_id == rid))
            db.execute(sa_delete(models.Request).where(models.Request.id == rid))
            db.commit()
        finally:
            db.close()


def test_a_declared_html_type_on_a_pdf_name_is_ignored():
    """والنوعُ المُعلَن لا يُقرأ أصلًا — الامتدادُ المخزَّن يحكم."""
    assert served_media_type("documents/ab12_cv.pdf") == "application/pdf"
    assert served_media_type("archive/ab12_x.html") == "application/octet-stream"
    assert served_media_type("requests/req1_attachment_x.html") == "application/octet-stream"


def test_system_generated_html_is_still_served_as_html():
    """وما يكتبه النظامُ يبقى HTML — الصيغُ المطبوعة تُعرض في المتصفح."""
    assert served_media_type("forms/HRMS-PR-001_1_202609_0001.html").startswith("text/html")


def test_unknown_extensions_are_downloaded_not_rendered():
    assert served_media_type("x/a.svg") == "application/octet-stream"
    assert served_media_type("x/a.bin") == "application/octet-stream"


def test_every_download_passes_through_the_one_helper():
    """ولا تنزيلَ يتخطّاه — ``FileResponse`` المباشر للواجهة المبنية وحدها."""
    import pathlib
    import re

    app_dir = pathlib.Path(__file__).resolve().parents[1] / "app"
    stray = []
    for p in app_dir.rglob("*.py"):
        if p.name in ("storage.py", "main.py"):
            continue
        if re.search(r"\bFileResponse\(", p.read_text(encoding="utf-8", errors="ignore")):
            stray.append(p.name)
    assert not stray, f"تنزيلٌ يتخطّى served_media_type: {stray}"
