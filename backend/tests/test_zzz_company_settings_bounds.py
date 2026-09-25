# -*- coding: utf-8 -*-
"""M03 — معاملاتُ الشركة لا تقبل قيمًا بلا معنى (تُحسب بها مستحقات الموظفين).

قيس (200 لكلٍّ): ``eos_day_divisor`` سالبًا وصفرًا ومليارًا، و``eos_max_months`` سالبًا،
و``annual_leave_days`` بـ-30 و9999، و``alert_lead_days`` سالبًا. والحدود واسعة عمدًا فلا تحسم
سياسةً، ولا تُطبَّق على **القراءة** (``CompanyOut`` مستقلّ) فلا تنكسر قائمةُ الشركات بسجلٍّ قديم.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login


@pytest.fixture
def company1_restore():
    db = SessionLocal()
    c = db.get(models.Company, 1)
    saved = (c.eos_day_divisor, c.eos_max_months, c.alert_lead_days, c.annual_leave_days)
    db.close()
    yield
    db = SessionLocal()
    try:
        c = db.get(models.Company, 1)
        c.eos_day_divisor, c.eos_max_months, c.alert_lead_days, c.annual_leave_days = saved
        db.commit()
    finally:
        db.close()


@pytest.mark.parametrize("payload", [
    {"eos_day_divisor": -5}, {"eos_day_divisor": 0}, {"eos_day_divisor": 10 ** 9},
    {"eos_max_months": -3}, {"eos_max_months": 0},
    {"annual_leave_days": -30}, {"annual_leave_days": 9999},
    {"alert_lead_days": -10}, {"alert_lead_days": 0},
])
def test_nonsensical_company_settings_are_refused(client, company1_restore, payload):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    r = client.put("/api/companies/1", headers=admin, json=payload)
    assert r.status_code == 422, f"{payload} قُبل: {r.status_code}"


def test_the_usual_settings_still_save(client, company1_restore):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    r = client.put("/api/companies/1", headers=admin, json={
        "eos_day_divisor": 30, "eos_max_months": 18, "annual_leave_days": 30, "alert_lead_days": 45})
    assert r.status_code == 200, r.text[:150]
    assert r.json()["eos_day_divisor"] == 30 and r.json()["alert_lead_days"] == 45


def test_reading_a_legacy_out_of_range_company_does_not_break_the_list(client, company1_restore):
    db = SessionLocal()
    try:
        c = db.get(models.Company, 1)
        c.eos_day_divisor, c.annual_leave_days = 0, 5000   # قيمٌ قديمة خارج حدود الإدخال الجديدة
        db.commit()
    finally:
        db.close()
    admin = auth_headers(login(client, "000000000000", "admin123"))
    r = client.get("/api/companies", headers=admin)
    assert r.status_code == 200, f"قائمة الشركات انكسرت بسجلٍّ قديم: {r.status_code}"
