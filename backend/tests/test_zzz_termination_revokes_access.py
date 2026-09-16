# -*- coding: utf-8 -*-
"""الإنهاءُ يسحب الوصول — من انتهت خدمته لا يدخل النظامَ بدوره.

**القياس** (قبل الإصلاح): موظفُ الموارد البشرية ``100000000002`` — ملفُّه
``terminated`` — **دخل** (200) واستعرض ``/api/employees`` (200). فلا مسارَ
إنهاءٍ يمسّ صفَّ المستخدم، والدخولُ يفحص ``user.is_active`` وحده.

**والإصلاحُ طبقتان:**

1. **عند الإنهاء** (``terminate/execute`` و``settle_case``) يُعطَّل الحسابُ
   المرتبط ويُبطَل كلُّ رمزٍ صادر — بآلية شاشة المستخدمين نفسها، فتحرسه كلُّ
   البوّابات القائمة.
2. **وبوّابةٌ عند الدخول والتجديد** لمن انتهت خدمته **قبل** هذا الإصلاح
   وحسابُه ما زال نشطًا — بلا تعديلٍ على بيانات الإنتاج.

ومستخدمٌ بلا ملف موظف (إداري، مالك) لا يُمَسّ.
"""
from __future__ import annotations

from sqlalchemy import select

from app import deps, models
from app.database import SessionLocal

HR = ("100000000002", "hr12345")


def _set_emp_status(civil_id: str, status: str):
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == civil_id))
        e = db.get(models.Employee, u.employee_id)
        old = e.status
        e.status = status
        db.commit()
        return old
    finally:
        db.close()


def _login(client, who):
    return client.post("/api/auth/login", json={"civil_id": who[0], "password": who[1]})


def test_an_ended_service_cannot_log_in(client):
    """**الثغرةُ المقيسة بعينها** — والحسابُ ما زال ``is_active``."""
    old = _set_emp_status(HR[0], "terminated")
    try:
        r = _login(client, HR)
        assert r.status_code == 403, (r.status_code, r.text[:200])
        assert "انتهت خدمة" in r.text
    finally:
        _set_emp_status(HR[0], old)


def test_an_ended_service_cannot_refresh_a_token(client):
    """**ورمزُ التجديد لا يُحيي ما أُنهي** — أربعة عشر يومًا من الرموز."""
    r = _login(client, HR)
    assert r.status_code == 200, r.text[:200]
    refresh = r.json().get("refresh_token")
    assert refresh, r.json().keys()
    old = _set_emp_status(HR[0], "terminated")
    try:
        rr = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert rr.status_code == 401, (rr.status_code, rr.text[:200])
    finally:
        _set_emp_status(HR[0], old)


def test_a_vacation_still_logs_in(client):
    """ومن خدمتُه قائمة يدخل — البوّابةُ لا تمنع ما كان يعمل."""
    old = _set_emp_status(HR[0], "vacation")
    try:
        assert _login(client, HR).status_code == 200
    finally:
        _set_emp_status(HR[0], old)


def test_revocation_disables_the_account_and_kills_sessions():
    """**والإنهاءُ نفسه يُعطّل الحساب** — فتحرسه البوّاباتُ القائمة كلّها."""
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == HR[0]))
        emp = db.get(models.Employee, u.employee_id)
        ids = deps.revoke_employee_access(db, emp)
        db.flush()
        assert u.id in ids, ids
        assert u.is_active is False and u.status == "inactive"
        assert u.tokens_valid_after is not None
    finally:
        db.rollback()
        db.close()


def test_both_termination_paths_revoke():
    """والمساران كلاهما يسحبان — فلا بابَ ثانٍ يُنسى."""
    import inspect

    from app.routers import employees, eos

    assert "revoke_employee_access(" in inspect.getsource(employees.execute_termination)
    assert "revoke_employee_access(" in inspect.getsource(eos.settle_case)


def test_a_user_without_an_employee_file_is_untouched():
    db = SessionLocal()
    try:
        admin = db.scalar(select(models.User).where(models.User.civil_id == "000000000000"))
        assert deps.employment_ended(db, admin) is False
    finally:
        db.close()
