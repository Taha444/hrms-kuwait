# -*- coding: utf-8 -*-
"""M05 — إنشاء الموظف يرفض قيمًا بلا معنى كانت تُقبل (201) وتُقرأ لاحقًا بلا شكوى.

``contract_type`` نصٌّ حرّ تعامله محرّكات نهاية الخدمة والعقد على أنه «غير محدد» صامتًا؛
والجنس والبريد بلا صيغة؛ وتاريخُ ميلادٍ بعد التعيين أو في المستقبل. والمفردات المقبولة هي
ما تُرسله الواجهة والـOCR فلا يُكسر مشروع.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, purge

HR = ("100000000002", "hr12345")
_n = [0]


def _create(client, **over):
    _n[0] += 1
    body = {"civil_id": f"77900{_n[0]:04d}", "name": f"M05-{_n[0]}", "basic_salary": 400,
            "hire_date": "2024-01-01", **over}
    hr = auth_headers(login(client, *HR))
    r = client.post("/api/employees", headers=hr, json=body)
    if r.status_code == 201:
        db = SessionLocal()
        try:
            purge(db, "employees", [r.json()["id"]])
            db.commit()
        finally:
            db.close()
    return r


@pytest.mark.parametrize("field,value", [
    ("contract_type", "lifetime-xyz"),
    ("gender", "???"),
    ("email", "not-an-email"),
    ("date_of_birth", "2030-01-01"),      # بعد التعيين
    ("date_of_birth", "2999-01-01"),      # مستقبل
])
def test_nonsensical_values_are_refused(client, field, value):
    r = _create(client, **{field: value})
    assert r.status_code == 422, f"{field}={value!r} قُبل: {r.status_code}"


@pytest.mark.parametrize("over", [
    {"contract_type": "definite"}, {"contract_type": "indefinite"},
    {"gender": "male"}, {"gender": "female"}, {"gender": ""},
    {"email": "a.b@example.com"}, {"date_of_birth": "1990-05-05"},
])
def test_legitimate_values_still_pass(client, over):
    r = _create(client, **over)
    assert r.status_code == 201, f"{over} رُفض: {r.status_code} {r.text[:150]}"
