# -*- coding: utf-8 -*-
"""M02 #1 — لا مسارٌ يُعرَّف مرتين (الثاني ميّت ويُوهم بقاعدةٍ لا تُطبَّق)، وربطُ الحساب بموظفٍ لا يُبدَّل بصلاحية المستخدمين وحدها.

``POST /users/{id}/link-employee`` كان له معالجان: الفعّال يُعيد ربط حسابٍ مربوطٍ بموظفٍ آخر، والميّتُ يرفض ذلك.
"""
import collections

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.main import app
from tests.conftest import auth_headers, login


def test_no_method_and_path_is_registered_twice():
    seen = collections.defaultdict(list)
    for r in app.routes:
        for m in getattr(r, "methods", None) or ():
            if getattr(r, "path", None):
                seen[(m, r.path)].append(getattr(r, "name", "?"))
    dups = {k: v for k, v in seen.items() if len(v) > 1}
    assert not dups, f"مساراتٌ مكرَّرة (الثاني ميّت): {dups}"


def test_an_already_linked_account_cannot_be_re_linked_to_another_employee(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    db = SessionLocal()
    linked = db.scalar(select(models.User).where(
        models.User.civil_id == "100000000101"))
    other = db.scalar(select(models.Employee).where(
        models.Employee.company_id == linked.company_id, models.Employee.id != linked.employee_id))
    uid, was, oid = linked.id, linked.employee_id, other.id
    db.close()
    r = client.post(f"/api/users/{uid}/link-employee", headers=admin, params={"employee_id": oid})
    assert r.status_code == 409, (r.status_code, r.text[:100])
    db = SessionLocal()
    assert db.get(models.User, uid).employee_id == was, "الرفضُ ترك الربطَ مبدَّلًا"
    db.close()
