# -*- coding: utf-8 -*-
"""M06 #1/#2 — رفع المستند يرفض رمز نوعٍ غير صالح وتاريخَ انتهاءٍ يسبق الإصدار."""
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, plain_employee_clause

HR = ("100000000002", "hr12345")


def _upload(client, hr, eid, code, **extra):
    return client.post("/api/documents/upload", headers=hr,
                       data={"entity_type": "employee", "entity_id": str(eid),
                             "document_type_code": code, **extra},
                       files={"file": ("a.pdf", b"%PDF-1.4 x", "application/pdf")})


def test_bad_type_codes_and_date_order_are_refused_before_anything_is_stored(client):
    hr = auth_headers(login(client, *HR))
    db = SessionLocal()
    eid = db.scalar(select(models.Employee.id).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        plain_employee_clause(models)))
    n_before = db.query(models.Document).count()
    db.close()
    for bad in ("x" * 51, "has space", "عربي", "a/b", "<b>", "", "custom:", "custom:a/b", "custom:" + "ع" * 50):
        r = _upload(client, hr, eid, bad)
        assert r.status_code in (400, 422), (bad, r.status_code, r.text[:80])
    r = _upload(client, hr, eid, "passport", issue_date="2026-05-01", expiry_date="2026-04-01")
    assert r.status_code == 400 and "أقدم" in r.json()["detail"], r.text
    db = SessionLocal()
    assert db.query(models.Document).count() == n_before, "رفضٌ ترك مستندًا مخزَّنًا"
    db.close()


def test_a_custom_document_code_with_a_free_arabic_name_is_still_accepted(client):
    hr = auth_headers(login(client, *HR))
    db = SessionLocal()
    eid = db.scalar(select(models.Employee.id).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        plain_employee_clause(models)))
    db.close()
    r = _upload(client, hr, eid, "custom:قياس القبول")
    assert r.status_code == 200, r.text[:120]
    db = SessionLocal()
    try:
        for d in db.scalars(select(models.Document).where(
                models.Document.document_type_code == "custom:قياس القبول")).all():
            db.delete(d)
        db.commit()
    finally:
        db.close()
