# -*- coding: utf-8 -*-
"""M18 — كلُّ تنزيلٍ لمستندٍ حسّاس يترك أثرًا في التدقيق.

مستندات الموظف والأرشيف كانت تُدقَّق، أما **مستندات التجديد** (العقد الحكومي، البطاقة المدنية،
إذن العمل) و**مستندات الطلبات المُولَّدة** (شهادة راتب، خطاب) فكان تنزيلُها بلا أثر: من نزّل
ورقةً فيها رقمٌ مدنيّ أو راتبٌ لا يُعرَف.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import delete as sa_delete, select

from app import models, renewal as R
from app.database import SessionLocal
from app.storage import save_bytes
from tests.conftest import auth_headers, login, purge

PRO = ("100000000003", "deleg123")
EMP = ("100000000101", "emp12345")


def _audit_rows(action, entity_id):
    db = SessionLocal()
    try:
        return db.scalars(select(models.AuditLog).where(
            models.AuditLog.action == action, models.AuditLog.entity_id == entity_id)).all()
    finally:
        db.close()


def test_a_renewal_document_download_is_audited(client):
    key = save_bytes(b"%PDF-1.4 renewal", "renewals", "m18.pdf", prefix="m18_")
    db = SessionLocal()
    try:
        emp = models.Employee(company_id=1, name="M18-RN", civil_id="777200001", status="active",
                              basic_salary=400, hire_date=date(2020, 1, 1))
        db.add(emp)
        db.flush()
        permit = models.Permit(company_id=1, employee_id=emp.id, kind="residency", status="active",
                               number="M18", expiry_date=date.today() + timedelta(days=20))
        db.add(permit)
        db.flush()
        rn = models.ResidencyRenewal(company_id=1, employee_id=emp.id, permit_id=permit.id,
                                     renewal_type="normal", status="awaiting_contracts",
                                     days_left_at_request=20, created_by=1)
        db.add(rn)
        db.flush()
        doc = models.Document(company_id=1, entity_type="renewal", entity_id=rn.id,
                              document_type_code=R.DOC_CONTRACT_GOV, title="عقد", file_path=key,
                              mime="application/pdf", version=1, is_current=True, uploaded_by=1)
        db.add(doc)
        db.commit()
        ids = dict(emp=emp.id, permit=permit.id, rn=rn.id, doc=doc.id)
    finally:
        db.close()
    try:
        pro = auth_headers(login(client, *PRO))
        r = client.get(f"/api/renewals/{ids['rn']}/document/{R.DOC_CONTRACT_GOV}", headers=pro)
        assert r.status_code == 200, r.text[:120]
        assert _audit_rows("download_renewal_document", ids["rn"]), "تنزيل مستند التجديد بلا تدقيق"
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.AuditLog).where(
                models.AuditLog.action == "download_renewal_document",
                models.AuditLog.entity_id == ids["rn"]))
            db.execute(sa_delete(models.Document).where(models.Document.id == ids["doc"]))
            purge(db, "residency_renewals", [ids["rn"]])
            purge(db, "permits", [ids["permit"]])
            purge(db, "employees", [ids["emp"]])
            db.commit()
        finally:
            db.close()


def test_a_generated_request_document_download_is_audited(client):
    emp_hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=emp_hdr, json={
        "request_type_code": "salary_certificate",
        "payload_json": {"purpose": "بنك M18", "language": "ar", "notes": "تدقيق التنزيل"}})
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    key = save_bytes(b"%PDF-1.4 cert", "requests", "m18.pdf", prefix="m18_")
    db = SessionLocal()
    try:
        rd = models.RequestDocument(request_id=rid, kind="generated_pdf", file_path=key, version=1)
        db.add(rd)
        db.commit()
        rdid = rd.id
    finally:
        db.close()
    try:
        d = client.get(f"/api/requests/{rid}/document/generated_pdf", headers=emp_hdr)
        assert d.status_code == 200, d.text[:120]
        assert _audit_rows("download_request_document", rid), "تنزيل مستند الطلب بلا تدقيق"
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.AuditLog).where(
                models.AuditLog.action == "download_request_document",
                models.AuditLog.entity_id == rid))
            db.execute(sa_delete(models.RequestDocument).where(models.RequestDocument.id == rdid))
            db.commit()
        finally:
            db.close()


def test_an_employees_own_document_download_is_audited(client):
    key = save_bytes(b"%PDF-1.4 own", "documents", "m18own.pdf", prefix="m18own_")
    db = SessionLocal()
    try:
        user = db.scalar(select(models.User).where(models.User.civil_id == EMP[0]))
        doc = models.Document(company_id=user.company_id, entity_type="employee",
                              entity_id=user.employee_id, document_type_code="m18_own_doc",
                              title="x", file_path=key, mime="application/pdf",
                              version=1, is_current=True, uploaded_by=user.id)
        db.add(doc)
        db.commit()
        did = doc.id
    finally:
        db.close()
    try:
        h = auth_headers(login(client, *EMP))
        r = client.get("/api/me/document/m18_own_doc", headers=h)
        if r.status_code == 404:
            r = client.get("/api/selfservice/document/m18_own_doc", headers=h)
        assert r.status_code == 200, r.text[:120]
        assert _audit_rows("download_own_document", did), "تنزيل الموظف لمستنده بلا تدقيق"
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.AuditLog).where(
                models.AuditLog.action == "download_own_document",
                models.AuditLog.entity_id == did))
            db.execute(sa_delete(models.Document).where(models.Document.id == did))
            db.commit()
        finally:
            db.close()
