# -*- coding: utf-8 -*-
"""إعادُة إدخال كلمة المرور داخل الجلسة تُحصى كما يُحصى الدخول.

تغييُر كلمة المرور، وتعطيُل التحقق الثنائي، وإعادُة توليد رموز الاسترداد —
كلُّها تطلب الكلمَة الحالية لتصمد إن سُرقت الجلسة (جهاٌز تُرك مفتوحًا). وكان
الفشُل فيها **بلا عدٍّ ولا قفٍل ولا أثٍر في التدقيق**: فمن سرق جلسًة يخمّن
الكلمَة هنا بلا حدّ، ثم يُعطّل التحقق الثنائي أو يأخذ رموَز الاسترداد.

والقاعدُة الآن قاعدُة الرمز الثنائي نفسها: يُحصى الفشُل على الحساب، وعند
الحدّ يُقفَل وتُبطَل جلساته.
"""
from __future__ import annotations

import time

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, purge

CIVIL = "399999999901"
PW = "Guard-Pass-12345"


@pytest.fixture
def victim():
    from app.security import hash_password

    db = SessionLocal()
    try:
        old = db.scalar(select(models.User).where(models.User.civil_id == CIVIL))
        if old:
            purge(db, "users", [old.id])
            db.commit()
        u = models.User(civil_id=CIVIL, full_name="حساب حارس", role="hr", company_id=1,
                        password_hash=hash_password(PW), is_active=True, status="active",
                        must_change_password=False)
        db.add(u)
        db.commit()
        uid = u.id
    finally:
        db.close()
    yield uid
    db = SessionLocal()
    try:
        purge(db, "users", [uid])
        db.commit()
    finally:
        db.close()


@pytest.mark.parametrize("path,body", [
    ("/api/auth/change-password", lambda pw: {"old_password": pw, "new_password": "New-Pass-67890!"}),
    ("/api/2fa/disable", lambda pw: {"password": pw}),
    ("/api/2fa/recovery/regenerate", lambda pw: {"password": pw}),
])
def test_guessing_the_password_inside_a_session_locks_and_ends_it(client, victim, path, body):
    def _fails():
        db = SessionLocal()
        try:
            return len(db.scalars(select(models.AuditLog).where(
                models.AuditLog.user_id == victim,
                models.AuditLog.action == "password_reconfirm_fail")).all())
        finally:
            db.close()

    before = _fails()
    h = auth_headers(login(client, CIVIL, PW))
    # الإبطال بهامش ثانيٍة (iat بالثواني) — والجلسة المسروقة أقدم من ذلك دائمًا.
    time.sleep(2.2)
    for _ in range(5):
        r = client.post(path, headers=h, json=body("wrong-guess"))
        assert r.status_code in (400, 401), r.text[:150]
    # الجلسة انتهت، والحساب مقفول.
    after = client.get("/api/auth/me", headers=h)
    assert after.status_code == 401, (after.status_code, after.text[:150])
    db = SessionLocal()
    try:
        u = db.get(models.User, victim)
        assert u.locked_until is not None
    finally:
        db.close()
    assert _fails() - before == 5, "كل تخميٍن فاشل يُسجَّل في التدقيق"
    db = SessionLocal()
    try:
        pass
    finally:
        db.close()
