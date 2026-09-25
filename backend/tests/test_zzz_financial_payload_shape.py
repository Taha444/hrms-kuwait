# -*- coding: utf-8 -*-
"""M08 — نماذج المال ترفض عند التقديم ما كان يفشل بعد ثلاث مراحل اعتماد.

``_apply_deduction`` يردّ «المبلغ يجب أن يكون أكبر من صفر» و«شهر المسيّر غير صالح» لكن
**بعد** أن يمرّ الطلب بمراحله كلّها إلى ``apply_failed``. وقيس أن التقديم كان يقبل خصمًا
سالبًا أو صفرًا (201) وشهرًا نصّه «January». فالقاعدة تُفحص عند التقديم، بالمفردات نفسها.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import form_schemas, models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, plain_employee_clause, purge

HR = ("100000000002", "hr12345")


@pytest.mark.parametrize("payload,field", [
    ({"deduction_amount": -500, "reason": "x", "payroll_month": "2027-01"}, "deduction_amount"),
    ({"deduction_amount": 0, "reason": "x", "payroll_month": "2027-01"}, "deduction_amount"),
    ({"deduction_amount": 5, "reason": "x", "payroll_month": "January"}, "payroll_month"),
    ({"deduction_amount": 5, "reason": "x", "payroll_month": "2027-13"}, "payroll_month"),
])
def test_a_deduction_with_a_bad_amount_or_month_is_refused_at_submission(client, payload, field):
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            plain_employee_clause(models)).limit(1))
    finally:
        db.close()
    hr = auth_headers(login(client, *HR))
    r = client.post("/api/requests", headers=hr, json={
        "employee_id": eid, "request_type_code": "ADMDED", "payload_json": payload})
    if r.status_code == 201:
        db = SessionLocal()
        try:
            purge(db, "requests", [r.json()["id"]])
            db.commit()
        finally:
            db.close()
    assert r.status_code == 400, f"{payload} قُبل: {r.status_code}"
    assert field in r.text


def test_every_declared_month_field_uses_the_month_format():
    """الحقول المعلنة «YYYY-MM» في تسميتها كلّها تحمل ``format='month'`` — فلا يبقى واحدٌ يُنسى."""
    missing = []
    for code, s in form_schemas.SCHEMAS.items():
        for f in s.get("fields") or []:
            if "YYYY-MM" in (f.get("label") or "") and f.get("format") != "month":
                missing.append(f"{code}.{f['code']}")
    assert not missing, f"حقول شهرٍ بلا فحص صيغة: {missing}"


def test_a_valid_deduction_still_passes_validation():
    assert form_schemas.validate_payload("ADMDED", {
        "deduction_amount": 12.5, "reason": "x", "payroll_month": "2027-01"}) == []
