# -*- coding: utf-8 -*-
"""البحثُ الشامل بنطاق الفرع — كقائمة الموظفين وملفّاتهم.

كان البحُث يُرشّح بالشركة وحدها. فمسؤوُل الفرع يبحث باسٍم أو رقٍم مدنيٍّ أو
رقِم جواز فيجد موظّفي الفروع الأخرى **ورقَمهم المدنيَّ في نتيجة البحث** —
وملفُّ الموظف الذي تفتحه النتيجُة يردّه 404 بنطاق فرعه. فالبحُث كان يكشف
ما يحجبه الملف، ويسمح بتعداد أرقام الجوازات في الشركة كلّها.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

SUP1 = ("100000000005", "sup12345")


def _foreign_employee():
    db = SessionLocal()
    try:
        sup = db.scalar(select(models.User).where(models.User.civil_id == SUP1[0]))
        from app.deps import resolve_scope
        mine = resolve_scope(sup, db).branch_ids or set()
        return db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.branch_id.isnot(None),
            models.Employee.branch_id.notin_(mine)))
    finally:
        db.close()


def test_a_supervisor_does_not_find_another_branchs_employee_by_civil_id(client):
    emp = _foreign_employee()
    r = client.get("/api/search", params={"q": emp.civil_id},
                   headers=auth_headers(login(client, *SUP1)))
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()["results"].get("employees", [])]
    assert emp.id not in ids, "البحُث يكشف موظَف فرٍع آخر ورقَمه المدني"


def test_hr_still_finds_everyone(client):
    emp = _foreign_employee()
    r = client.get("/api/search", params={"q": emp.civil_id},
                   headers=auth_headers(login(client, "100000000002", "hr12345")))
    ids = [e["id"] for e in r.json()["results"].get("employees", [])]
    assert emp.id in ids
