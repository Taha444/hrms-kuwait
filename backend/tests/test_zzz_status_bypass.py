# -*- coding: utf-8 -*-
"""لا تُنهى خدمةٌ بقائمةٍ منسدلة — مسارُ الإنهاء لا يُتخطّى.

**القياس**: القائمةُ المنسدلة في ملف الموظف تعرض كلَّ الحالات، و
``POST /employees/{id}/status`` بـ``edit_employee`` وحده كان يكتب
``terminated`` فورًا — متخطّيًا مسارَ الإنهاء كلَّه: تحضيرٌ ← اعتمادٌ من
**شخصٍ آخر** ← إخلاءُ طرف ← إقرارُ الموظف ← تنفيذ، ومعه التسوية. شخصٌ واحدٌ
يُنهي خدمةً بلا عينٍ ثانية — عينُ «ممنوع Self Approval لكل الأدوار».

وكذلك «مؤرشف» لموظفٍ على رأس عمله: إنهاءٌ بلا مسار (والأرشفةُ في القائمة
الموحَّدة لمن انتهت خدمته — فتُسحب معها الرواتبُ والوصول).

**وما لم يُمَسّ**: «مستقيل» و«متقاعد» — لا مسارَ لهما في النظام، وبناؤه قرار.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")


def _emp_id():
    db = SessionLocal()
    try:
        e = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            models.Employee.civil_id.notin_(("100000000002", "100000000001"))))
        return e.id
    finally:
        db.close()


def _status(eid):
    db = SessionLocal()
    try:
        return db.get(models.Employee, eid).status
    finally:
        db.close()


def _post(client, eid, status):
    return client.post(f"/api/employees/{eid}/status", params={"status": status},
                       headers=auth_headers(login(client, *HR)))


def test_a_dropdown_cannot_end_a_service(client):
    eid = _emp_id()
    r = _post(client, eid, "terminated")
    assert r.status_code == 409, (r.status_code, r.text[:200])
    assert "إنهاء الخدمة" in r.text
    assert _status(eid) == "active"


def test_an_active_employee_cannot_be_archived_directly(client):
    eid = _emp_id()
    r = _post(client, eid, "archived")
    assert r.status_code == 409, (r.status_code, r.text[:200])
    assert _status(eid) == "active"


def test_an_ended_service_can_still_be_archived(client):
    """والأرشفةُ لمن انتهت خدمته تعمل كما كانت."""
    eid = _emp_id()
    try:
        assert _post(client, eid, "resigned").status_code == 200
        assert _post(client, eid, "archived").status_code == 200
        assert _status(eid) == "archived"
    finally:
        db = SessionLocal()
        try:
            db.get(models.Employee, eid).status = "active"
            db.commit()
        finally:
            db.close()


def test_ordinary_statuses_still_change(client):
    eid = _emp_id()
    try:
        assert _post(client, eid, "vacation").status_code == 200
        assert _post(client, eid, "active").status_code == 200
    finally:
        db = SessionLocal()
        try:
            db.get(models.Employee, eid).status = "active"
            db.commit()
        finally:
            db.close()


def test_the_screen_does_not_offer_what_the_server_refuses():
    """**وزرٌّ يُعرض فيُرفض** — القائمةُ تُصفّى بالقاعدة نفسها."""
    import pathlib

    src = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
           / "EmployeeProfile.tsx").read_text(encoding="utf-8")
    assert 'k !== "terminated"' in src, "القائمةُ تعرض «منتهية خدمته»"
