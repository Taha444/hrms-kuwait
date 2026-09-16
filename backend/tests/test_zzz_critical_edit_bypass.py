# -*- coding: utf-8 -*-
"""الراتبُ لا يُرفع من نموذج التعديل — مسارُ الاقتراح المعتمَد لا يُتخطّى.

**القياس**: ``propose_salary_change`` مكتوبٌ فيه «لا يُطبَّق على الموظف حتى
الاعتماد» من مستخدمٍ آخر — للراتب وتاريخ التعيين والمسمّى ونوع العقد. و
``PUT /employees/{id}`` بـ``edit_employee`` وحدها كان يكتبها **فورًا**، ونموذجُ
التعديل في ملف الموظف يعرضها حقولًا حرّة — والقسمُ المعتمَد في الصفحة نفسها.

فصار الـPUT يرفض تغييرَها (409 يُحيل إلى «اقتراح تعديل»)، والنموذجُ يُرسل
قيمَها القائمة كما هي فتمرّ — فلا يُكسر حفظُ الاسم أو الهاتف.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")


def _emp():
    db = SessionLocal()
    try:
        e = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            models.Employee.basic_salary.isnot(None)))
        return (e.id, (e.name, e.civil_id), float(e.basic_salary), e.hire_date,
                e.job_title, e.contract_type)
    finally:
        db.close()


def _body(ident, salary, hire, job, contract, **extra):
    name, civil_id = ident
    b = {"name": name, "civil_id": civil_id, "basic_salary": salary,
         "hire_date": hire.isoformat() if hire else None,
         "job_title": job, "contract_type": contract}
    b.update(extra)
    return b


def test_a_salary_cannot_be_raised_from_the_edit_form(client):
    eid, name, sal, hire, job, contract = _emp()
    r = client.put(f"/api/employees/{eid}", json=_body(name, sal + 500, hire, job, contract),
                   headers=auth_headers(login(client, *HR)))
    assert r.status_code == 409, (r.status_code, r.text[:200])
    assert "اقتراح تعديل" in r.text and "الراتب الأساسي" in r.text
    db = SessionLocal()
    try:
        assert float(db.get(models.Employee, eid).basic_salary) == sal, "رُفع الراتبُ بلا اعتماد"
    finally:
        db.close()


def test_saving_unrelated_fields_with_the_same_salary_still_works(client):
    """**والنموذجُ يُرسل القيمَ القائمة** — فحفظُ الهاتف لا يُكسر."""
    eid, name, sal, hire, job, contract = _emp()
    db = SessionLocal()
    try:
        old_phone = db.get(models.Employee, eid).phone
    finally:
        db.close()
    try:
        r = client.put(f"/api/employees/{eid}",
                       json=_body(name, str(int(sal)) if sal == int(sal) else sal,
                                  hire, job or "", contract, phone="99990000"),
                       headers=auth_headers(login(client, *HR)))
        assert r.status_code == 200, (r.status_code, r.text[:200])
    finally:
        db = SessionLocal()
        try:
            db.get(models.Employee, eid).phone = old_phone
            db.commit()
        finally:
            db.close()


def test_the_edit_form_shows_critical_fields_read_only():
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
           / "EmployeeProfile.tsx").read_text(encoding="utf-8")
    assert 'CRITICAL_EDIT_FIELDS = ["basic_salary", "hire_date", "job_title"]' in src
    assert "readOnly={CRITICAL_EDIT_FIELDS.includes(k)}" in src
