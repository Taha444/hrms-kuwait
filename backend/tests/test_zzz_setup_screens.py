# -*- coding: utf-8 -*-
"""نقاطٌ مبنيٌة بلا بابٍ في الواجهة — بيانات الإعداد التي لا يُنشئها أحد.

بكنس نداءات الكتابة في الواجهة ظهرت نقاطٌ تكتب ولا شاشَة تناديها. وأثقلُها
في الإعداد نفسه:

- ``PUT /companies/{id}`` — بيانات الشركة (رقم الملف ونوع الكيان ومقسوم
  نهاية الخدمة) تدخل العقدَ الحكوميَّ وحسابَ المكافأة. وكانت الشاشُة كلُّها
  للإدارة العليا وحدها، **و«لا تمنح أي مستخدم Super Admin» قاعدُة المالك** —
  فالقرارُ الذي فتح التعديل لـ``manage_company`` (2026-09-11) لم يصل الواجهة،
  ولا نموذَج تعديٍل فيها أصًلا.
- ``POST /departments`` — الأقسامُ تُقرأ في ملف الموظف ولا شاشَة تُنشئها.
- ``POST /licenses`` — والسعُة القانونيُة تُعَدّ على الترخيص.
"""
from __future__ import annotations

import pathlib
import re

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

SRC = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"
MGR = ("100000000001", "manager123")
PRO = ("100000000003", "deleg123")


def test_the_company_screen_is_not_locked_to_a_role_nobody_holds():
    app_tsx = (SRC / "App.tsx").read_text(encoding="utf-8")
    line = next(ln for ln in app_tsx.splitlines() if 'path="/companies"' in ln)
    assert 'can("manage_company")' in line, (
        "شاشُة الشركات للإدارة العليا وحدها — وقاعدُة المالك ألا يأخذها أحد")


def test_the_company_screen_can_edit_what_the_server_allows():
    page = (SRC / "pages" / "Companies.tsx").read_text(encoding="utf-8")
    assert "api.put(`/companies/" in page, "لا نموذَج تعديٍل لبيانات الشركة"
    for field in ("file_number", "entity_type", "eos_day_divisor", "annual_leave_days"):
        assert field in page, field
    # وإنشاُء الشركات وتعطيلُها يبقيان للإدارة العليا كما يفرض الخادم.
    assert "isAdmin" in page and "company_new" in page


def test_a_manager_can_edit_the_company_data(client):
    db = SessionLocal()
    try:
        before = db.get(models.Company, 1)
        snap = (before.file_number, before.entity_type)
    finally:
        db.close()
    hdr = auth_headers(login(client, *MGR))
    try:
        r = client.put("/api/companies/1", headers=hdr,
                       json={"file_number": "F-9001", "entity_type": "ذات مسؤولية محدودة"})
        assert r.status_code == 200, r.text[:200]
        db = SessionLocal()
        try:
            c = db.get(models.Company, 1)
            assert c.file_number == "F-9001"
            # وما لم يُرسَل لا يُمسّ — أرقاٌم تُحسب بها المكافأة.
            assert c.eos_day_divisor in (26, 30)
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            c = db.get(models.Company, 1)
            c.file_number, c.entity_type = snap
            db.commit()
        finally:
            db.close()


def test_the_structure_screen_creates_departments():
    page = (SRC / "pages" / "CompanyStructure.tsx").read_text(encoding="utf-8")
    assert 'api.post("/departments"' in page, "لا شاشَة تُنشئ قسًما"
    assert 'can("manage_departments")' in page, "النموذُج بلا بوّابة الصلاحية"


def test_a_manager_can_create_a_department(client):
    hdr = auth_headers(login(client, *MGR))
    r = client.post("/api/departments", headers=hdr, params={"name": "قسمُ قياس"})
    assert r.status_code == 201, r.text[:200]
    db = SessionLocal()
    try:
        row = db.scalar(select(models.Department).where(models.Department.name == "قسمُ قياس"))
        assert row is not None
        db.delete(row)
        db.commit()
    finally:
        db.close()


def test_the_operations_screen_creates_licences():
    page = (SRC / "pages" / "Operations.tsx").read_text(encoding="utf-8")
    assert 'api.post("/licenses"' in page, "لا شاشَة تُنشئ ترخيًصا"
    assert 'can("manage_licenses")' in page


def test_the_delegate_can_create_a_licence(client):
    hdr = auth_headers(login(client, *PRO))
    r = client.post("/api/licenses", headers=hdr,
                    params={"name": "ترخيصُ قياس", "license_no": "ZZ-QA-1",
                            "allowed_workers": 5})
    assert r.status_code == 201, r.text[:200]
    db = SessionLocal()
    try:
        row = db.scalar(select(models.License).where(models.License.license_no == "ZZ-QA-1"))
        assert row is not None and row.allowed_workers == 5
        db.delete(row)
        db.commit()
    finally:
        db.close()


def test_no_screen_offers_what_its_user_cannot_do():
    """وكلُّ نموذٍج من هذه خلف الصلاحية التي يفرضها الخادم — لا زرَّ يُرفض."""
    pairs = [("pages/CompanyStructure.tsx", "manage_departments"),
             ("pages/Operations.tsx", "manage_licenses"),
             ("pages/Companies.tsx", "manage_company")]
    for rel, perm in pairs:
        page = (SRC / rel).read_text(encoding="utf-8")
        assert re.search(rf'can\("{perm}"\)', page), (rel, perm)
