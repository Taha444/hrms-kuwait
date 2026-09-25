# -*- coding: utf-8 -*-
"""M07 — كتالوج «طلب جديد» لا يعرض إجراءً إداريًّا يرفضه الخادم لهذا الدور.

قيس: يرى المندوب «إصدار خصم» و«إنذار» و«مخالفة» و«إلغاء إقامة» في القائمة وكلها 403 عند
الإرسال؛ ويرى مدير الشركة الأربعة وهو ممنوع أصلًا من التقديم نيابةً عن غيره. والثابت الذي
يُقاس **بالسلوك** لكل دور ولكل نوع ``ADM*``: **كل ما يعرضه الكتالوج لا يُرفض 403 سلطة**.
(والعكس لا يصحّ عمدًا: أنواعٌ ``internal_action`` كإضافة موظف تُخفى من «طلب جديد» لأنها تُنفَّذ
من شاشاتها، ويقبلها الخادم لمن يملك سلطتها.)
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, plain_employee_clause, purge

ROLES = {
    "employee": ("100000000101", "emp12345"),
    "hr": ("100000000002", "hr12345"),
    "manager": ("100000000001", "manager123"),
    "delegate": ("100000000003", "deleg123"),
    "branch_supervisor": ("100000000005", "sup12345"),
}
_PAYLOAD = {"reason": "M07", "deduction_amount": 5, "payroll_month": "2027-05"}


@pytest.mark.parametrize("role", sorted(ROLES))
def test_the_catalog_offers_only_internal_actions_the_server_accepts(client, role):
    db = SessionLocal()
    try:
        codes = sorted(db.scalars(select(models.RequestType.code).where(
            models.RequestType.is_active == True,  # noqa: E712
            models.RequestType.code.like("ADM%"))).all())
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            plain_employee_clause(models)).limit(1))
    finally:
        db.close()
    assert codes, "لا أنواع ADM في القاعدة"
    hdr = auth_headers(login(client, *ROLES[role]))
    offered = {x["code"] for x in client.get(
        "/api/requests/types", headers=hdr, params={"creatable_only": "true"}).json()}
    made, wrong = [], []
    try:
        for code in codes:
            r = client.post("/api/requests", headers=hdr, json={
                "employee_id": eid, "request_type_code": code, "payload_json": _PAYLOAD})
            if r.status_code == 201:
                made.append(r.json()["id"])
            if code in offered and r.status_code == 403:
                wrong.append(f"{code}: معروض ويُرفض 403")
    finally:
        db = SessionLocal()
        try:
            purge(db, "requests", made)
            db.commit()
        finally:
            db.close()
    assert not wrong, f"{role}: " + "؛ ".join(wrong)
