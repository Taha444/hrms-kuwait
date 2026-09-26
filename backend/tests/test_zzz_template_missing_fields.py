# -*- coding: utf-8 -*-
"""M17 #7 — المستند الرسمي الذي حُذف منه حقلٌ بلا قيمة **يُسمّي** الناقص بدل الصمت.

``_prune_unfilled`` يحذف الخانة الفارغة عمدًا، فشهادةُ راتبٍ تصدر بلا صفّ الراتب ولا كلمة تُخبر HR. الحذفُ سليم؛ الصمتُ هو
العطل. فالردّ (معاينةً وإصدارًا) يحمل ``missing_fields`` مسمّاةً، وتصدر المستندات بلا حظر (روحُ قرار 2026-09-22).
"""
import re
from datetime import date

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, plain_employee_clause, purge

HR = ("100000000002", "hr12345")


def test_a_document_issued_without_the_salary_says_so(client):
    hr = auth_headers(login(client, *HR))
    db = SessionLocal()
    emp = db.scalar(select(models.Employee).where(
        models.Employee.company_id == 1, models.Employee.status == "active",
        plain_employee_clause(models)))
    tpl = next(t for t in db.scalars(select(models.DocumentTemplate).where(
        models.DocumentTemplate.company_id.is_(None))).all()
        if re.search(r"\{\{\s*basic_salary\s*\}\}", t.body_html or ""))
    eid, salary, tid = emp.id, emp.basic_salary, tpl.id
    doc_ids = []
    try:
        emp.basic_salary = 0
        db.commit()
        pre = client.post(f"/api/templates/{tid}/preview", headers=hr, json={"employee_id": eid})
        assert pre.status_code == 200 and "basic_salary" in [m["key"] for m in pre.json()["missing_fields"]]
        gen = client.post(f"/api/templates/{tid}/generate", headers=hr, json={"employee_id": eid})
        assert gen.status_code == 200, gen.text[:120]        # لا حظر
        keys = [m["key"] for m in gen.json()["missing_fields"]]
        assert "basic_salary" in keys and all(m["label"] for m in gen.json()["missing_fields"])
        doc_ids.append(gen.json()["document_id"])
        emp.basic_salary = salary
        db.commit()
        full = client.post(f"/api/templates/{tid}/preview", headers=hr, json={"employee_id": eid})
        assert "basic_salary" not in [m["key"] for m in full.json()["missing_fields"]]
    finally:
        emp.basic_salary = salary
        db.commit()
        for i in doc_ids:
            d = db.get(models.Document, i)
            if d:
                db.delete(d)
        db.commit()
        db.close()


def test_company_documents_get_ascending_versions(client):
    hr = auth_headers(login(client, *HR))
    db = SessionLocal()
    tpl = next(t for t in db.scalars(select(models.DocumentTemplate).where(
        models.DocumentTemplate.company_id.is_(None))).all() if (t.body_html or "").count("company_name"))
    tid = tpl.id
    db.close()
    ids = []
    try:
        versions = []
        for _ in range(3):
            r = client.post(f"/api/templates/{tid}/company-generate", headers=hr, json={"company_id": 1})
            if r.status_code != 200:
                break
            ids.append(r.json()["document_id"])
            db = SessionLocal()
            versions.append(db.get(models.Document, ids[-1]).version)
            db.close()
        assert len(versions) == 3 and versions == sorted(set(versions)), versions
    finally:
        db = SessionLocal()
        for i in ids:
            d = db.get(models.Document, i)
            if d:
                db.delete(d)
        db.commit()
        db.close()
