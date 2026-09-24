# -*- coding: utf-8 -*-
"""M17 — المستند الرسمي لا يحمل قيمةً أرسلها العميل مكان قيمة القاعدة.

``_resolve_authoritative_data`` وعدت في تعليقها بمنع تزوير الراتب والتاريخ، لكن قائمة
القفل كانت 17 مفتاحًا يدويًّا والسياق يبني نحو 60: قُبلت ``official_salary`` و
``actual_salary`` و``residency_expiry`` و``passport_number`` و``date_today`` من ``extra``
وخرجت على مستندٍ رسمي. صار القفل مشتقًّا من السياق نفسه.
"""
from __future__ import annotations

import re

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

_BODY = ("<p>XX{{official_salary}}|{{actual_salary}}|{{residency_expiry}}|{{passport_number}}"
         "|{{date_today}}|{{employment_status}}|{{special_condition_1}}YY</p>")


def _render(client, extra):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    db = SessionLocal()
    try:
        t = models.DocumentTemplate(company_id=None, code="ZZZ-LOCKED-FIELDS", name="فحص القفل",
                                    category="other", body_html=_BODY, is_active=True)
        db.add(t)
        e = db.scalar(select(models.Employee).where(models.Employee.status == "active").limit(1))
        db.commit()
        tid, eid = t.id, e.id
    finally:
        db.close()
    try:
        r = client.post(f"/api/templates/{tid}/preview", headers=admin,
                        json={"employee_id": eid, "extra": extra})
        assert r.status_code == 200, r.text
        return re.search(r"XX(.*?)YY", r.json()["html"], re.S).group(1).split("|")
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.DocumentTemplate).where(models.DocumentTemplate.id == tid))
            db.commit()
        finally:
            db.close()


def test_database_fields_cannot_be_overridden_from_the_request(client):
    clean = _render(client, {})
    forged = _render(client, {
        "official_salary": "99999", "actual_salary": "88888", "residency_expiry": "2099-01-01",
        "passport_number": "FORGED1", "date_today": "2001-01-01", "employment_status": "forged"})
    assert forged[:6] == clean[:6], f"قيم مزوَّرة وصلت للمستند: {forged[:6]} ≠ {clean[:6]}"


def test_manually_filled_fields_still_work(client):
    out = _render(client, {"special_condition_1": "شرط اختبار M17"})
    assert out[6] == "شرط اختبار M17", out
