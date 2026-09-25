# -*- coding: utf-8 -*-
"""M01 — تغيير كلمة المرور يُنهي الجلسة **كلَّها**، ومنها رمزُ التجديد.

``change-password`` يضبط ``tokens_valid_after`` وتقول رسالتُه «سيلزمك تسجيل الدخول مجددًا». وكان
``get_current_user`` يُطبّق ذلك فيُرفض رمزُ الدخول القديم بـ401، بينما ``/auth/refresh`` لا يفحصه: رمزُ
التجديد القديم يُنتج رمزَ دخولٍ جديدًا (200، قيس). فمن سُرقت جلستُه وغيّر كلمة سرّه يبقى المهاجمُ
داخلًا (تجديدٌ متكرّر بلا نهاية). والقاعدةُ صارت دالةً واحدة يستعملها البابان.

الفاصلُ الزمني حقيقيٌّ عمدًا: ``iat`` بالثواني والمقارنةُ بهامش ثانية، فتغييرٌ في اللحظة نفسها لا يُبطل.
"""
from __future__ import annotations

import time

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.security import hash_password
from tests.conftest import auth_headers

CIVIL, OLD, NEW = "100000000101", "emp12345", "NewPass#12345x"


def _restore():
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == CIVIL))
        u.password_hash = hash_password(OLD)
        u.must_change_password = False
        u.tokens_valid_after = None
        db.commit()
    finally:
        db.close()


def test_an_old_refresh_token_cannot_revive_a_session_after_a_password_change(client):
    try:
        login = client.post("/api/auth/login", json={"civil_id": CIVIL, "password": OLD}).json()
        access, refresh = login["access_token"], login["refresh_token"]
        time.sleep(3.2)
        ch = client.post("/api/auth/change-password", headers=auth_headers(access),
                         json={"old_password": OLD, "new_password": NEW})
        assert ch.status_code == 200, ch.text

        assert client.get("/api/auth/me", headers=auth_headers(access)).status_code == 401, \
            "رمز الدخول القديم ما زال يعمل"
        r = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 401, f"رمز التجديد القديم أنتج جلسةً بعد تغيير كلمة المرور: {r.status_code}"

        # والدخولُ بالكلمة الجديدة وحده يفتح جلسةً صالحة
        fresh = client.post("/api/auth/login", json={"civil_id": CIVIL, "password": NEW})
        assert fresh.status_code == 200
        assert client.get("/api/auth/me", headers=auth_headers(fresh.json()["access_token"])).status_code == 200
        # وتجديدُ الجلسة الجديدة يعمل (الإبطال لا يمسّ ما بعده)
        again = client.post("/api/auth/refresh", json={"refresh_token": fresh.json()["refresh_token"]})
        assert again.status_code == 200, again.text[:120]
    finally:
        _restore()


def test_a_disabled_account_cannot_log_in_or_use_any_token(client):
    login = client.post("/api/auth/login", json={"civil_id": CIVIL, "password": OLD}).json()
    access, refresh = login["access_token"], login["refresh_token"]
    db = SessionLocal()
    try:
        db.scalar(select(models.User).where(models.User.civil_id == CIVIL)).is_active = False
        db.commit()
    finally:
        db.close()
    try:
        assert client.post("/api/auth/login", json={"civil_id": CIVIL, "password": OLD}).status_code == 403
        assert client.get("/api/auth/me", headers=auth_headers(access)).status_code == 401
        assert client.post("/api/auth/refresh", json={"refresh_token": refresh}).status_code == 401
    finally:
        db = SessionLocal()
        try:
            db.scalar(select(models.User).where(models.User.civil_id == CIVIL)).is_active = True
            db.commit()
        finally:
            db.close()
