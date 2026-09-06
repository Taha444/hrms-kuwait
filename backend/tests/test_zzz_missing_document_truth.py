# -*- coding: utf-8 -*-
"""البند 28 — لا وعد بورقة مفقودة.

**العطل**: الملف قد يضيع (قرص مؤقّت يُمحى مع النشرة) والسجلّ يبقى في
القاعدة. فتقول الشاشة «جاهز للاستلام» ويعرض زرّ الطباعة، ويرجع التنزيل
``410``. ويقف الموظف أمام من لا يجد ما يسلّمه.

والتخزين نفسه أُصلح — المستندات الجديدة تعيش بعد النشر. الباقي **صدق
الشاشة عن القديم**: من يقرأ «جاهز» يجب أن يجد ورقة.

**والفحص من دالة التنزيل نفسها** (``key_exists``) لا من شرط يشبهها:
قاعدتان لحالة واحدة تنحرفان، فتقول إحداهما «موجود» والأخرى ``410``.
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
SUP = ("100000000005", "sup12345")
HR = ("100000000002", "hr12345")

FRONT = Path(__file__).resolve().parents[2] / "frontend"
PAGE = FRONT / "src" / "pages" / "RequestDetail.tsx"


def _completed_leave(client) -> int:
    """طلب إجازة يبلغ مرحلة توليد المستند."""
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()
    hdr = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQLV",
        "payload_json": {"start_date": "2030-02-01", "end_date": "2030-02-03",
                         "days": 3, "leave_type": "unpaid",
                         "reason": "قياس المستند المفقود"}}).json()["id"]
    for who in (SUP, HR):
        client.post(f"/api/requests/{rid}/decide",
                    headers=auth_headers(login(client, *who)),
                    json={"decision": "approved"})
    return rid


def test_a_present_document_is_not_flagged(client):
    """أوًلا: المستند الموجود لا يُتَّهم — وحارس يُنذر دائًما لا يُنذر."""
    rid = _completed_leave(client)
    body = client.get(f"/api/requests/{rid}",
                      headers=auth_headers(login(client, *HR))).json()
    gen = next((d for d in body["documents"] if d["kind"] == "generated_pdf"), None)
    assert gen is not None, body["documents"]
    assert gen["file_missing"] is False, gen


def test_a_lost_file_is_declared_not_promised(client):
    """**جوهر العطل**: السجلّ باقٍ والملف ذهب — والشاشة كانت تَعِد."""
    rid = _completed_leave(client)
    db = SessionLocal()
    try:
        doc = db.scalar(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid,
            models.RequestDocument.kind == "generated_pdf"))
        doc.file_path = "generated/does-not-exist-999.pdf"
        db.commit()
    finally:
        db.close()

    hdr = auth_headers(login(client, *HR))
    body = client.get(f"/api/requests/{rid}", headers=hdr).json()
    gen = next(d for d in body["documents"] if d["kind"] == "generated_pdf")
    assert gen["file_missing"] is True, gen

    # والتنزيل يوافقها: مصدر واحد للحقيقة لا مصدران.
    dl = client.get(f"/api/requests/{rid}/document/generated_pdf", headers=hdr)
    assert dl.status_code == 410, dl.status_code


def test_a_record_without_a_path_counts_as_missing(client):
    """وسجٌل بلا مسار مفقود كذلك: توليد بدأ ولم يكتمل."""
    rid = _completed_leave(client)
    db = SessionLocal()
    try:
        doc = db.scalar(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid,
            models.RequestDocument.kind == "generated_pdf"))
        doc.file_path = None
        db.commit()
    finally:
        db.close()
    body = client.get(f"/api/requests/{rid}",
                      headers=auth_headers(login(client, *HR))).json()
    gen = next(d for d in body["documents"] if d["kind"] == "generated_pdf")
    assert gen["file_missing"] is True, gen


def test_the_flag_uses_the_same_check_the_download_uses():
    """وشرطان متشابهان ينحرفان — فتقول الشاشة «موجود» ويردّ التنزيل 410."""
    import inspect

    from app.routers import requests as req_router

    src = inspect.getsource(req_router)
    assert '"file_missing": bool(not d.file_path or not key_exists(d.file_path))' in src, (
        "الراية لا تستعمل فحص التخزين نفسه"
    )


def test_the_screen_declares_it_and_hides_the_dead_buttons():
    """والشاشة تقول الحقيقة وتُخفي أزراًرا تصف عمًلا لا يمكن أن يقع."""
    page = PAGE.read_text(encoding="utf-8")
    assert "genDoc?.file_missing" in page, "الشاشة لا تعرض حالة الفقد"
    assert "rd_doc_missing" in page, "لا نصّ يشرح ما جرى"
    assert "genDoc && !genDoc.file_missing" in page, (
        "أزرار الطباعة والأرشفة ما زالت تظهر على ورقة مفقودة"
    )
