# -*- coding: utf-8 -*-
"""لا تُنهى خدمةٌ بقائمةٍ منسدلة — مسارُ الإنهاء لا يُتخطّى.

**القياس**: القائمةُ المنسدلة في ملف الموظف تعرض كلَّ الحالات، و
``POST /employees/{id}/status`` بـ``edit_employee`` وحده كان يكتب
``terminated`` فورًا — متخطّيًا مسارَ الإنهاء كلَّه: تحضيرٌ ← اعتمادٌ من
**شخصٍ آخر** ← إخلاءُ طرف ← إقرارُ الموظف ← تنفيذ، ومعه التسوية. شخصٌ واحدٌ
يُنهي خدمةً بلا عينٍ ثانية — عينُ «ممنوع Self Approval لكل الأدوار».

وكذلك «مؤرشف» لموظفٍ على رأس عمله: إنهاءٌ بلا مسار (والأرشفةُ في القائمة
الموحَّدة لمن انتهت خدمته — فتُسحب معها الرواتبُ والوصول).

**و«مستقيل» و«متقاعد» كذلك** — قرار المالك (2026-09-17): تمرّان بمسار
الإنهاء، والمسارُ يكتب «مستقيل» لسبب الاستقالة.
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


import pytest


@pytest.mark.parametrize("ended", ["terminated", "resigned", "retired"])
def test_a_dropdown_cannot_end_a_service(client, ended):
    eid = _emp_id()
    r = _post(client, eid, ended)
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
        db = SessionLocal()
        try:
            db.get(models.Employee, eid).status = "resigned"   # كما يكتبه المسار
            db.commit()
        finally:
            db.close()
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
    import re

    from app.routers.employees import PATH_ONLY_STATUSES
    m = re.search(r"const ENDED = \[([^\]]*)\]", src)
    assert m, "القائمةُ لا تُصفّى بقائمة الحالات المنتهية"
    ended = set(re.findall(r'"(\w+)"', m.group(1)))
    assert ended == set(PATH_ONLY_STATUSES), (ended, PATH_ONLY_STATUSES)
    assert "!ENDED.includes(k)" in src, "القائمةُ تعرض حالاتٍ يرفضها الخادم"


def test_the_path_writes_resigned_for_a_resignation(client):
    """والمسارُ يكتب «مستقيل» لسببها — وإلا ضاع التمييزُ الذي كانت القائمةُ تحمله."""
    from app import exit_case
    assert exit_case.final_status("resignation") == "resigned"
    assert exit_case.final_status("termination") == "terminated"
    assert exit_case.final_status("misconduct") == "terminated"
    import inspect

    from app.routers import employees as RE, eos as RO
    assert "_exit_status(reason)" in inspect.getsource(RE.execute_termination)
    assert "final_status(case.termination_reason)" in inspect.getsource(RO.settle_case)


def test_retirement_is_a_reason_with_full_entitlement():
    """قرار المالك (2026-09-17): التقاعد سببٌ في المسار — كاملُ الاستحقاق، بلا
    إنذار، ويكتب «متقاعد». وبدونه صارت الحالةُ لا يكتبها شيء."""
    from app import eos, exit_case
    assert "retirement" in eos.TERMINATION_REASONS
    assert exit_case.final_status("retirement") == "retired"
    r = eos.calculate_eos(1000, "2020-01-01", "2026-01-01", reason="retirement")
    full = eos.calculate_eos(1000, "2020-01-01", "2026-01-01", reason="termination")
    assert r["entitlement_factor"] == 1.0
    assert r["indemnity"] == full["indemnity"]
    assert eos.notice_owed_days("retirement", 90, None, None, "2026-01-01") == 0.0


def test_the_profile_offers_every_server_reason():
    import pathlib
    import re

    from app import eos
    src = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
           / "EmployeeProfile.tsx").read_text(encoding="utf-8")
    block = re.search(r"const REASONS: Record<string, string> = \{(.*?)\};", src, re.S).group(1)
    offered = set(re.findall(r"(\w+): t\(", block))
    assert offered == set(eos.TERMINATION_REASONS), (offered ^ set(eos.TERMINATION_REASONS))
