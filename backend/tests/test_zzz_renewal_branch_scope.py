# -*- coding: utf-8 -*-
"""معاملاتُ التجديد تُقرأ بنطاق الفرع — كما يُقرأ ملفُّ الموظف.

**القياس**: ``/renewals`` وتنزيلُ مستنداته (البطاقة المدنية، إذن العمل،
العقود) تُفتح لكلّ من يملك **أيَّ صلاحية اعتماد** — ومسؤولُ الفرع يملكها.
والتحقُّق شركٌة واحدة (``assert_same_company``) لا فرع. فمسؤوُل الفرع الأول
يسرد معاملاِت الفرع الثاني ويُنزّل البطاقَة المدنيَة لموظّفيه — بينما ملفُّ
الموظف نفسه (``_get_emp``) يمنعه بنطاق الفرع ويُسجّل المحاولة.

فالمستنُد الأشدُّ حساسيًة كان أوسَع قراءًة من الملفّ الذي يحمله.
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

SUP1 = ("100000000005", "sup12345")      # مسؤول الفرع الأول


def _renewal_in_another_branch():
    db = SessionLocal()
    try:
        sup = db.scalar(select(models.User).where(models.User.civil_id == SUP1[0]))
        from app.deps import resolve_scope
        mine = resolve_scope(sup, db).branch_ids or set()
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1,
            models.Employee.branch_id.isnot(None),
            models.Employee.branch_id.notin_(mine)))
        assert emp is not None, "لا موظَف في فرعٍ آخر — لا يُقاس النطاق"
        rn = models.ResidencyRenewal(company_id=1, employee_id=emp.id, status="new")
        db.add(rn)
        db.commit()
        return rn.id, emp.id
    finally:
        db.close()


def _drop(rid):
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.ResidencyRenewal).where(models.ResidencyRenewal.id == rid))
        db.commit()
    finally:
        db.close()


def test_a_branch_supervisor_does_not_list_another_branchs_renewals(client):
    rid, _ = _renewal_in_another_branch()
    try:
        rows = client.get("/api/renewals", headers=auth_headers(login(client, *SUP1))).json()
        assert rid not in [r["id"] for r in rows], "مسؤوُل الفرع يرى معاملاِت فرٍع آخر"
    finally:
        _drop(rid)


def test_a_branch_supervisor_cannot_open_another_branchs_renewal(client):
    rid, _ = _renewal_in_another_branch()
    try:
        hdr = auth_headers(login(client, *SUP1))
        r = client.get(f"/api/renewals/{rid}", headers=hdr)
        assert r.status_code == 404, (r.status_code, r.text[:150])
        doc = client.get(f"/api/renewals/{rid}/document/civil_id", headers=hdr)
        assert doc.status_code == 404, (doc.status_code, doc.text[:150])
    finally:
        _drop(rid)


def test_the_due_list_is_branch_scoped_too(client):
    db = SessionLocal()
    try:
        sup = db.scalar(select(models.User).where(models.User.civil_id == SUP1[0]))
        from app.deps import resolve_scope
        mine = resolve_scope(sup, db).branch_ids or set()
        foreign = {e.id for e in db.scalars(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.branch_id.notin_(mine))).all()}
    finally:
        db.close()
    rows = client.get("/api/renewals/due/permits",
                      headers=auth_headers(login(client, *SUP1))).json()
    leaked = [r["employee_name"] for r in rows if r["employee_id"] in foreign]
    assert not leaked, f"قائمُة المستحقّ تعرض إقاماِت فرٍع آخر: {leaked}"


def test_the_pro_still_sees_the_whole_company(client):
    """والمندوُب يعمل على الشركة كلّها — النطاُق لا يحجبه عن فرع."""
    rid, _ = _renewal_in_another_branch()
    try:
        rows = client.get("/api/renewals",
                          headers=auth_headers(login(client, "100000000003", "deleg123"))).json()
        assert rid in [r["id"] for r in rows], "حُجب المندوُب عن معاملة"
    finally:
        _drop(rid)
