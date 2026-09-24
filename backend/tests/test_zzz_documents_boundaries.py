# -*- coding: utf-8 -*-
"""M06 — حدّان في ``/documents`` كانا مفتوحين رغم أن أخوتهما مغلقة.

١) ``POST /upload`` كان يقبل أيّ ``entity_type`` نصّيّ وأيّ ``entity_id`` وينسب الوثيقة لشركة
   الرافع — فيرفع مندوب الشركة 1 وثيقةً على معاملة تجديد تخصّ الشركة 2.
٢) ``GET /{id}/download`` لا يفحص ``may_view_document`` بخلاف ``/latest`` و``/history``:
   الورقة السرّية تُخفى هناك وتُخرَج هنا بمعرّفٍ متسلسل.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from app.storage import save_bytes
from tests.conftest import auth_headers, login, purge

HR = ("100000000002", "hr12345")
PRO = ("100000000003", "deleg123")


def test_upload_rejects_entity_types_outside_the_known_four(client):
    db = SessionLocal()
    try:
        b = models.Employee(company_id=2, name="M06-B", civil_id="777000601", status="active",
                            basic_salary=400, hire_date=date(2020, 1, 1))
        db.add(b)
        db.flush()
        p = models.Permit(company_id=2, employee_id=b.id, kind="residency", status="active",
                          number="M06P", expiry_date=date.today() + timedelta(days=20))
        db.add(p)
        db.flush()
        rn = models.ResidencyRenewal(company_id=2, employee_id=b.id, permit_id=p.id,
                                     renewal_type="normal", status="pending_hr_verify",
                                     days_left_at_request=20, created_by=1)
        db.add(rn)
        db.commit()
        ids = (b.id, p.id, rn.id)
    finally:
        db.close()
    try:
        pro = auth_headers(login(client, *PRO))
        f = {"file": ("x.pdf", b"%PDF-1.4 fake", "application/pdf")}
        cross = client.post("/api/documents/upload", headers=pro, files=f, data={
            "entity_type": "renewal", "entity_id": str(ids[2]),
            "document_type_code": "renewal_signed_gov"})
        bogus = client.post("/api/documents/upload", headers=pro, files=f, data={
            "entity_type": "bogus", "entity_id": "5", "document_type_code": "x"})
        assert cross.status_code == 400, f"وثيقة على معاملة شركة أخرى قُبلت: {cross.status_code}"
        assert bogus.status_code == 400, f"نوع كيان مختلق قُبل: {bogus.status_code}"
    finally:
        db = SessionLocal()
        try:
            # صفوفي أنا فقط: اختباراتٌ أخرى تملك وثائق ``renewal`` بأبناءٍ (مفتاح أجنبي).
            db.execute(sa_delete(models.Document).where(
                models.Document.entity_type == "renewal",
                models.Document.entity_id == ids[2]))
            db.execute(sa_delete(models.Document).where(
                models.Document.entity_type == "bogus",
                models.Document.document_type_code == "x"))
            purge(db, "residency_renewals", [ids[2]])
            purge(db, "permits", [ids[1]])
            purge(db, "employees", [ids[0]])
            db.commit()
        finally:
            db.close()


def test_a_confidential_document_is_not_downloadable_by_id(client):
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(models.Employee.company_id == 1).limit(1))
        key = save_bytes(b"%PDF-1.4 CONFIDENTIAL", "documents", "conf.pdf", prefix="m06_")
        d = models.Document(company_id=1, entity_type="employee", entity_id=emp.id,
                            document_type_code="warning_letter", title="سري", file_path=key,
                            mime="application/pdf", version=1, is_current=True, uploaded_by=1,
                            is_confidential=True)
        db.add(d)
        db.commit()
        did, eid = d.id, emp.id
    finally:
        db.close()
    try:
        hr = auth_headers(login(client, *HR))
        latest = client.get("/api/documents/latest", headers=hr, params={
            "entity_type": "employee", "entity_id": eid, "document_type_code": "warning_letter"})
        by_id = client.get(f"/api/documents/{did}/download", headers=hr)
        assert latest.status_code == 404
        assert by_id.status_code == 404, (
            f"الورقة السرّية تُنزَّل بالمعرّف ({by_id.status_code}) وهي مخفيّة في /latest")
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.Document).where(models.Document.id == did))
            db.commit()
        finally:
            db.close()
