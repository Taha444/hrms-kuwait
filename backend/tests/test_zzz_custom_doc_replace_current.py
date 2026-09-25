# -*- coding: utf-8 -*-
"""M18 #4 — استبدال مستند مخصّص لا يُنتج نسختين «حاليتين»: الاستبدال على النسخة الحالية وحدها."""
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.storage import save_bytes
from tests.conftest import auth_headers, login, plain_employee_clause

HR = ("100000000002", "hr12345")
CODE = "custom:m18-replace"


def _replace(client, hr, doc_id):
    return client.post(f"/api/archive/custom-doc/{doc_id}/replace", headers=hr,
                       files={"file": ("a.pdf", b"%PDF-1.4 x", "application/pdf")})


def test_replacing_a_history_version_is_refused_and_one_current_remains(client):
    hr = auth_headers(login(client, *HR))
    db = SessionLocal()
    emp = db.scalar(select(models.Employee).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        plain_employee_clause(models)))
    key = save_bytes(b"%PDF-1.4 v1", "custom_docs/employee", "v1.pdf", prefix="m18r_")
    v1 = models.Document(company_id=1, entity_type="employee", entity_id=emp.id,
                         document_type_code=CODE, title="m18", file_path=key,
                         mime="application/pdf", version=1, is_current=True, uploaded_by=1)
    db.add(v1)
    db.commit()
    v1_id, eid = v1.id, emp.id
    db.close()
    try:
        r = _replace(client, hr, v1_id)
        assert r.status_code == 200, r.text
        again = _replace(client, hr, v1_id)          # v1 صار تاريخًا
        assert again.status_code == 409, again.text
        db = SessionLocal()
        rows = db.scalars(select(models.Document).where(
            models.Document.entity_id == eid, models.Document.document_type_code == CODE)).all()
        assert sorted(d.version for d in rows) == [1, 2]
        assert [d.version for d in rows if d.is_current] == [2]
        db.close()
    finally:
        db = SessionLocal()
        for d in db.scalars(select(models.Document).where(
                models.Document.entity_id == eid, models.Document.document_type_code == CODE)).all():
            for a in db.scalars(select(models.AuditLog).where(
                    models.AuditLog.action == "replace_custom_document",
                    models.AuditLog.entity_id == eid)).all():
                db.delete(a)
            db.delete(d)
        db.commit()
        db.close()
