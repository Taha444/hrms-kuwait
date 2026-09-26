# -*- coding: utf-8 -*-
"""M16 SW-016 — ترخيصٌ انتهى تاريخُه يُعرض «منتهيًا» دون قلب حالته المخزَّنة (وإلا سكت تنبيهُ انتهائه)."""
from datetime import timedelta

from sqlalchemy import select

from app import models
from app.clock import today
from app.database import SessionLocal
from tests.conftest import auth_headers, login, purge


def test_an_expired_license_is_shown_expired_but_stays_active_for_the_alert_scan(client):
    mgr = auth_headers(login(client, "100000000003", "deleg123"))
    db = SessionLocal()
    lic = models.License(company_id=1, name="m16-expired", status="active",
                         expiry_date=today() - timedelta(days=30))
    ok = models.License(company_id=1, name="m16-valid", status="active",
                        expiry_date=today() + timedelta(days=300))
    db.add_all([lic, ok])
    db.commit()
    ids = [lic.id, ok.id]
    db.close()
    try:
        rows = {r["id"]: r for r in client.get("/api/licenses", headers=mgr, params={"company_id": 1}).json()}
        assert rows[ids[0]]["is_expired"] is True and rows[ids[0]]["effective_status"] == "expired"
        assert rows[ids[0]]["status"] == "active", "الحالةُ المخزَّنة قُلبت فسكت تنبيهُ الانتهاء"
        assert rows[ids[1]]["is_expired"] is False and rows[ids[1]]["effective_status"] == "active"
    finally:
        db = SessionLocal()
        purge(db, "licenses", ids)
        db.commit()
        db.close()
