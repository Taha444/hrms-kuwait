# -*- coding: utf-8 -*-
"""M06 #4 — سجلُّ نسخ المستندات (/history) وتنزيلُ الأحدث (/latest) يفرضان عزل الشركة قبل أي استعلام.

قيس أن HR الشركة 1 يستلم بيانات نسخ مستندات موظفٍ في الشركة 2 (العنوان والرافع والحجم والانتهاء)، وأن
``/latest`` يفرّق بين 404 و403 فيُنبئ بوجود الملف.
"""
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, purge

HR1 = ("100000000002", "hr12345")


def test_history_and_latest_do_not_cross_companies(client):
    db = SessionLocal()
    other = db.scalar(select(models.Employee).where(models.Employee.company_id == 2))
    mine = db.scalar(select(models.Employee).where(models.Employee.company_id == 1))
    docs = []
    for eid, cid in ((other.id, 2), (mine.id, 1)):
        d = models.Document(company_id=cid, entity_type="employee", entity_id=eid,
                            document_type_code="m06_scope", title="x", file_path="nowhere/x.pdf",
                            version=1, is_current=True, uploaded_by=1)
        db.add(d)
        docs.append(d)
    db.commit()
    ids, other_id, mine_id = [d.id for d in docs], other.id, mine.id
    db.close()
    try:
        hr = auth_headers(login(client, *HR1))
        r = client.get("/api/documents/history", headers=hr,
                       params={"entity_type": "employee", "entity_id": other_id})
        assert r.status_code == 404, (r.status_code, r.text[:100])
        r = client.get("/api/documents/latest", headers=hr, params={
            "entity_type": "employee", "entity_id": other_id, "document_type_code": "m06_scope"})
        assert r.status_code == 404, (r.status_code, r.text[:100])         # لا 403: لا وسيطَ وجود
        own = client.get("/api/documents/history", headers=hr,
                         params={"entity_type": "employee", "entity_id": mine_id})
        assert own.status_code == 200 and any(x["type"] == "m06_scope" for x in own.json())
    finally:
        db = SessionLocal()
        purge(db, "documents", ids)
        db.commit()
        db.close()
