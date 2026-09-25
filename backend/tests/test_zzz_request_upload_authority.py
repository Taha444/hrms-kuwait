# -*- coding: utf-8 -*-
"""M08 #4 — رفع مستند الطلب: الصلاحيةُ بحسب النوع وقبل الحفظ.

كان من يرى الطلب (وأولهم صاحبه) يرفع ``generated_pdf`` أو ``signed_scan`` أو ``exit_permit`` في أي
حالةٍ لا تطابق فرعَ الفحص، فيُخزَّن بإصدارٍ أعلى ويحلّ محلّ المستند الرسمي عند التنزيل.
"""
import io

from sqlalchemy import func, select

from app import models
from app.database import SessionLocal
from tests.conftest import attach_file, auth_headers, login

EMP = ("100000000101", "emp12345")


def _post(client, headers, rid, kind):
    return client.post(f"/api/requests/{rid}/documents", headers=headers, data={"kind": kind},
                       files={"file": ("f.pdf", io.BytesIO(b"%PDF-1.4 forged"), "application/pdf")})


def _docs(rid):
    db = SessionLocal()
    try:
        return db.scalar(select(func.count()).select_from(models.RequestDocument).where(
            models.RequestDocument.request_id == rid))
    finally:
        db.close()


def test_the_requester_cannot_plant_system_or_official_documents(client):
    emp = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=emp, json={
        "request_type_code": "salary_certificate",
        "payload_json": {"purpose": "بنك", "language": "ar", "notes": "قياس"}}).json()["id"]
    before = _docs(rid)
    for kind in ("generated_pdf", "signed_scan", "exit_permit"):
        r = _post(client, emp, rid, kind)
        assert r.status_code == 403, (kind, r.status_code, r.text[:80])
    assert _docs(rid) == before, "رفضٌ ترك صفَّ مستندٍ"
    assert attach_file(client, emp, rid).status_code in (200, 201)      # المرفقُ العاديّ يبقى لصاحبه
