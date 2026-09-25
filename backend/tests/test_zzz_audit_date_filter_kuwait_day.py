# -*- coding: utf-8 -*-
"""M22 #6 — فلتر التاريخ في التدقيق يقصّ بيوم الكويت لا بيوم UTC (المخزَّن UTC، والشاشة تعرض بتوقيت الكويت)."""
from datetime import datetime

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login


def test_the_date_filter_uses_the_kuwait_day(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    db = SessionLocal()
    early = models.AuditLog(action="m22_kw_day", entity_type="probe", detail="a",
                            created_at=datetime(2031, 3, 14, 22, 0))    # 01:00 كويت يوم 15
    late = models.AuditLog(action="m22_kw_day", entity_type="probe", detail="b",
                           created_at=datetime(2031, 3, 15, 22, 0))     # 01:00 كويت يوم 16
    db.add_all([early, late])
    db.commit()
    ids = (early.id, late.id)
    db.close()
    try:
        r = client.get("/api/audit", headers=admin, params={
            "action": "m22_kw_day", "from_date": "2031-03-15", "to_date": "2031-03-15"})
        assert r.status_code == 200, r.text
        assert [x["detail"] for x in r.json()] == ["a"], r.json()
    finally:
        db = SessionLocal()
        for i in ids:
            db.delete(db.get(models.AuditLog, i))
        db.commit()
        db.close()
