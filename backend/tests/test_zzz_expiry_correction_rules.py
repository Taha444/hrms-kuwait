# -*- coding: utf-8 -*-
"""M06 #2 — تصحيح تاريخ انتهاء المستند: على النسخة الحالية وحدها، بسببٍ إلزامي، ولا يسبق تاريخ الإصدار."""
from datetime import date, timedelta

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, plain_employee_clause, purge

HR = ("100000000002", "hr12345")


def _patch(client, hr, doc_id, **params):
    return client.patch(f"/api/documents/{doc_id}/expiry", headers=hr, params=params)


def test_the_rules_of_an_expiry_correction(client):
    hr = auth_headers(login(client, *HR))
    db = SessionLocal()
    emp = db.scalar(select(models.Employee).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        plain_employee_clause(models)))
    old = models.Document(company_id=1, entity_type="employee", entity_id=emp.id,
                          document_type_code="m06_exp", title="old", file_path="x/a.pdf", version=1,
                          is_current=False, uploaded_by=1, expiry_date=date.today() + timedelta(days=5))
    cur = models.Document(company_id=1, entity_type="employee", entity_id=emp.id,
                          document_type_code="m06_exp", title="cur", file_path="x/b.pdf", version=2,
                          is_current=True, uploaded_by=1, issue_date=date.today() - timedelta(days=30),
                          expiry_date=date.today() + timedelta(days=60))
    db.add_all([old, cur])
    db.commit()
    ids = [old.id, cur.id]
    db.close()
    try:
        soon = (date.today() + timedelta(days=200)).isoformat()
        assert _patch(client, hr, ids[0], expiry_date=soon, reason="x").status_code == 409     # نسخة قديمة
        assert _patch(client, hr, ids[1], expiry_date=soon).status_code == 400                # بلا سبب
        assert _patch(client, hr, ids[1], expiry_date=soon, reason="  ").status_code == 400
        before_issue = (date.today() - timedelta(days=90)).isoformat()
        assert _patch(client, hr, ids[1], expiry_date=before_issue, reason="x").status_code == 400
        ok = _patch(client, hr, ids[1], expiry_date=soon, reason="قراءة خاطئة")
        assert ok.status_code == 200, ok.text
    finally:
        db = SessionLocal()
        for d in db.scalars(select(models.AuditLog).where(
                models.AuditLog.action == "correct_document_expiry",
                models.AuditLog.entity_id == emp.id)).all():
            db.delete(d)
        purge(db, "documents", ids)
        db.commit()
        db.close()
