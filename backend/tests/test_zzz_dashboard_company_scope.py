# -*- coding: utf-8 -*-
"""M20 #3 — أرقام التراخيص والمهام الحكومية في اللوحة تتبع الشركة المختارة لا شركة المستخدم الأصلية."""
from datetime import date, timedelta

from sqlalchemy import select

from app import models
from app.compliance import license_compliance
from app.database import SessionLocal
from tests.conftest import auth_headers, login, purge


def test_license_counts_follow_the_selected_company(client):
    admin = auth_headers(login(client, "111111111111", "owner123"))
    db = SessionLocal()
    made = []
    try:
        for cid, n in ((1, 2), (2, 5)):          # عددان مختلفان كي لا يتطابق المجموعُ مع شركةٍ واحدة
            for i in range(n):
                lic = models.License(company_id=cid, name=f"m20-{cid}-{i}", status="active",
                                     expiry_date=date.today() + timedelta(days=400))
                db.add(lic)
                db.flush()
                made.append(lic.id)
        db.commit()
        for cid in (1, 2):
            d = client.get("/api/dashboard", headers=admin, params={"company_id": cid}).json()
            expected = license_compliance(db, cid, date.today())
            assert d["licenses"] == expected["valid"], (cid, d["licenses"], expected)
    finally:
        purge(db, "licenses", made)
        db.commit()
        db.close()
