# -*- coding: utf-8 -*-
"""مسؤول الفرع لا يرى من هم أعلى منه — قرار المالك (2026-09-19).

كان يرى في «موظفو الفرع» المديَر العام والمحاسَب وموظَف الشؤون والمندوب —
لأنهم مسجّلون على فرعه. والقرار: لا يرى موظًفا له دوٌر إداري (مدير، شؤون،
محاسب، مندوب، صاحب الشركات، مسؤول فرٍع آخر) ولو على فرعه — **في كل موضع**:
القائمة، والملف، والبحث، ومراجعة الحضور. «هما اللي يشوفوه، مش العكس.»
"""
from __future__ import annotations

from urllib.parse import quote

import pytest

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.deps import resolve_scope
from tests.conftest import auth_headers, login

SUP1 = ("100000000005", "sup12345")
HR = ("100000000002", "hr12345")
ADMIN_ROLES = ("super_admin", "company_owner", "company_manager", "hr",
               "accountant", "delegate", "branch_supervisor")


@pytest.fixture(autouse=True)
def _staff_on_his_branch():
    """موظفو المقر على فرع «المقر» في البيانات التجريبية — فتُنقل ملفاتهم مؤقًتا
    إلى فرعه: القاعدُة تصمد ولو سُجّل موظُف مقٍر على محٍل بالخطأ."""
    db = SessionLocal()
    try:
        sup = db.scalar(select(models.User).where(models.User.civil_id == SUP1[0]))
        target = next(iter(resolve_scope(sup, db).branch_ids))
        moved = {}
        for u in db.scalars(select(models.User).where(
                models.User.company_id == sup.company_id,
                models.User.role.in_(("company_manager", "hr", "accountant", "delegate")),
                models.User.employee_id.isnot(None))).all():
            e = db.get(models.Employee, u.employee_id)
            moved[e.id] = e.branch_id
            e.branch_id = target
        db.commit()
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        for eid, bid in moved.items():
            db.get(models.Employee, eid).branch_id = bid
        db.commit()
    finally:
        db.close()


def _people():
    """(موظفو الإدارة على فرعه، موظفوه العاديون، ملفُّه هو)."""
    db = SessionLocal()
    try:
        sup = db.scalar(select(models.User).where(models.User.civil_id == SUP1[0]))
        bids = resolve_scope(sup, db).branch_ids
        emps = db.scalars(select(models.Employee).where(
            models.Employee.branch_id.in_(bids))).all()
        role_of = {u.employee_id: u.role for u in db.scalars(select(models.User).where(
            models.User.employee_id.isnot(None))).all()}
        staff = [e for e in emps if role_of.get(e.id) in ADMIN_ROLES and e.id != sup.employee_id]
        regular = [e for e in emps if role_of.get(e.id) not in ADMIN_ROLES]
        return [(e.id, e.name) for e in staff], [(e.id, e.name) for e in regular], sup.employee_id
    finally:
        db.close()


def test_the_branch_has_both_kinds_to_measure():
    staff, regular, own = _people()
    assert staff and regular and own, "لا بيانات تكفي للقياس"


def test_the_supervisor_list_hides_higher_staff_but_keeps_regular_and_self(client):
    staff, regular, own = _people()
    h = auth_headers(login(client, *SUP1))
    ids = {e["id"] for e in client.get("/api/employees", headers=h).json()}
    assert not ids & {i for i, _ in staff}, "ظهر لمسؤول الفرع من هو أعلى منه"
    assert {i for i, _ in regular} <= ids
    assert own in ids, "اختفى ملفّه هو"


def test_the_supervisor_cannot_open_their_file(client):
    staff, _, _ = _people()
    h = auth_headers(login(client, *SUP1))
    for emp_id, _name in staff:
        r = client.get(f"/api/employees/{emp_id}", headers=h)
        assert r.status_code in (403, 404), (emp_id, r.status_code)


def test_search_and_attendance_review_hide_them_too(client):
    staff, _, _ = _people()
    h = auth_headers(login(client, *SUP1))
    review = client.get("/api/attendance/review", headers=h)
    assert review.status_code == 200, review.text[:150]
    for _id, name in staff:
        s = client.get(f"/api/search?q={quote(name)}", headers=h).json()
        assert _id not in {e["id"] for e in s.get("results", {}).get("employees", [])}, name
        assert name not in review.text, f"ظهر في مراجعة الحضور: {name}"


def test_hr_still_sees_everyone(client):
    staff, _, _ = _people()
    h = auth_headers(login(client, *HR))
    ids = {e["id"] for e in client.get("/api/employees", headers=h).json()}
    assert {i for i, _ in staff} <= ids
