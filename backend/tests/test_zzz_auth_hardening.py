# -*- coding: utf-8 -*-
"""مساراتُ الدخول: الرمزُ الثنائيُّ يُحصى على الحساب، وإعادةُ التعيين عشوائيةٌ دائمًا.

**١) الرمزُ الثنائيُّ عند الدخول** كان يُحدّ لكل عنوانٍ وحده — فمن عرف كلمةَ
المرور يوزّع تخميناتِ الأرقام الستة على عناوين كثيرة بلا قفل. والمصادقةُ
الثنائية وُضعت لتصمد بالضبط حين تُعرف الكلمة. فصار يُحصى على الحساب بقاعدة
كلمة المرور نفسها (خمسُ محاولاتٍ ثم قفلٌ ربعَ ساعة).

**٢) ``/2fa/verify``** كان بلا حدٍّ أصلًا — يُقيّد الفشلَ في التدقيق فقط. صار
يُحصى كذلك، وبعد الحدّ تُبطَل الجلسة.

**٣) ``/auth/reset-password``** كان يقبل ``new_password`` يختاره المدير —
وقاعدةُ المالك نصًّا: «ممنوع كلمة مرور موحدة أو مشتركة — أنشئ كلمة مرور مؤقتة
عشوائية ومختلفة لكل شخص». والشاشةُ لا ترسله؛ فكان بابًا في الـAPI وحده.
"""
from __future__ import annotations

import pyotp
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
ADMIN = ("000000000000", "admin123")


def _enable_totp(civil_id: str) -> tuple[int, str, tuple]:
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == civil_id))
        snap = (u.totp_secret, u.totp_confirmed, u.failed_attempts, u.locked_until,
                u.tokens_valid_after)
        secret = pyotp.random_base32()
        u.totp_secret, u.totp_confirmed = secret, True
        u.failed_attempts, u.locked_until = 0, None
        db.commit()
        return u.id, secret, snap
    finally:
        db.close()


def _restore(uid: int, snap: tuple) -> None:
    db = SessionLocal()
    try:
        u = db.get(models.User, uid)
        (u.totp_secret, u.totp_confirmed, u.failed_attempts, u.locked_until,
         u.tokens_valid_after) = snap
        db.commit()
    finally:
        db.close()


def _wrong(secret: str) -> str:
    good = pyotp.TOTP(secret).now()
    return "000000" if good != "000000" else "111111"


def test_totp_guesses_at_login_lock_the_account(client):
    uid, secret, snap = _enable_totp(HR[0])
    try:
        for _ in range(5):
            r = client.post("/api/auth/login", json={
                "civil_id": HR[0], "password": HR[1], "totp_code": _wrong(secret)})
            assert r.status_code in (401, 423), r.text[:200]
        good = client.post("/api/auth/login", json={
            "civil_id": HR[0], "password": HR[1],
            "totp_code": pyotp.TOTP(secret).now()})
        assert good.status_code == 423, (
            "خمسُ تخميناتٍ للرمز ولا قفل — الرمزُ يُخمَّن بلا حدٍّ لمن عرف الكلمة",
            good.status_code, good.text[:150])
    finally:
        _restore(uid, snap)


def test_step_up_verify_is_limited_and_ends_the_session(client):
    """والجلسةُ تُبطَل بعد الحدّ. وإبطالُ الجلسات بدقّة الثانية مع هامشٍ مكتوب
    (``deps``: «نطاف بحاجز 1 ثانية») — فيُؤخذ الرمزُ قبل الهامش."""
    import time

    tok = login(client, *HR)          # قبل تفعيل الرمز — جلسةٌ قائمة
    time.sleep(2.2)
    uid, secret, snap = _enable_totp(HR[0])
    h = auth_headers(tok)
    try:
        for _ in range(5):
            r = client.post("/api/2fa/verify", headers=h, json={"code": _wrong(secret)})
            if r.status_code == 401:
                break
        db = SessionLocal()
        try:
            u = db.get(models.User, uid)
            assert u.locked_until is not None and u.tokens_valid_after is not None
        finally:
            db.close()
        time.sleep(1.2)
        after = client.get("/api/auth/me", headers=h)
        assert after.status_code == 401, (
            "خمسُ محاولاتٍ فاشلة والجلسةُ ما زالت صالحة", after.status_code)
    finally:
        _restore(uid, snap)


def test_a_chosen_password_is_refused_on_reset(client):
    db = SessionLocal()
    try:
        target = db.scalar(select(models.User).where(models.User.civil_id == "100000000007"))
        tid, old_hash = target.id, target.password_hash
    finally:
        db.close()
    try:
        r = client.post("/api/auth/reset-password",
                        headers=auth_headers(login(client, *ADMIN)),
                        json={"user_id": tid, "new_password": "SamePass#2026x"})
        assert r.status_code == 400, (r.status_code, r.text[:200])
        db = SessionLocal()
        try:
            assert db.get(models.User, tid).password_hash == old_hash, "تغيّرت الكلمة"
        finally:
            db.close()
    finally:
        pass


def test_reset_without_a_password_still_generates_one(client):
    db = SessionLocal()
    try:
        target = db.scalar(select(models.User).where(models.User.civil_id == "100000000007"))
        tid = target.id
        snap = (target.password_hash, target.must_change_password, target.tokens_valid_after)
    finally:
        db.close()
    try:
        r = client.post("/api/auth/reset-password",
                        headers=auth_headers(login(client, *ADMIN)), json={"user_id": tid})
        assert r.status_code == 200, r.text[:200]
        assert r.json().get("temporary_password")
    finally:
        db = SessionLocal()
        try:
            u = db.get(models.User, tid)
            u.password_hash, u.must_change_password, u.tokens_valid_after = snap
            db.commit()
        finally:
            db.close()
