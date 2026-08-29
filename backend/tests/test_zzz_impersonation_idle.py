# -*- coding: utf-8 -*-
"""IMP-01/IMP-02 — الخمول يُقاس على الجلسة لا على المستخدم.

**العطل**: الإدارة العليا تنتحل شخصية مستخدم خامل منذ أكثر من مهلة
الخمول، فتُرفض جلسة الانتحال بـ401 **فورًا** رغم أن رمزها تولّد قبل ثانية.

**الجذر**: بدء الانتحال كان يُعامل استئناًفا لجلسة لا بدًءا لواحدة. النشاط
مخزَّن على ``users.last_activity_at`` — صفّ المستخدم لا الجلسة — فقرأ
المحرّك آخر نشاط لمن انتُحلت شخصيته وحكم على جلسة وليدة.

ومن الجذر نفسه عطلان آخران: جلستان لمستخدم واحد في متصفّحين تتصارعان على
صفّ واحد، ونشاط المُنتحِل يُكتب على المُنتحَل فيبدو حاضًرا وهو غائب.

والإصلاح ليس استثناءً مكتوًبا للانتحال: الجلسة صارت تُعرَف بـ``sid`` يمشي
مع رمز الدخول ورمز التجديد معًا، فجلسة الانتحال جديدة **ببنيتها**.

(وسم الانتحال وبقاؤه عبر التجديد في ``test_zzz_impersonation_session.py``
— هذا الملف للخمول وحده.)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app import models
from app.config import settings
from app.database import SessionLocal
from app.security import decode_token
from tests.conftest import auth_headers, login

SUPER = ("000000000000", "admin123")
TARGET_CIVIL = "100000000101"
TARGET_PASSWORD = "emp12345"


def _sid(token: str) -> str:
    return decode_token(token)["sid"]


def _age_session(sid: str, minutes: int) -> None:
    """يُشيخ صفّ جلسة بعينها — لا صفّ المستخدم."""
    db = SessionLocal()
    try:
        row = db.get(models.SessionActivity, sid)
        assert row is not None, "لا صفّ لهذه الجلسة"
        row.last_activity_at = (datetime.now(timezone.utc)
                                - timedelta(minutes=minutes)).replace(tzinfo=None)
        db.commit()
    finally:
        db.close()


@pytest.fixture
def idle_target(client):
    """مستخدم خامل منذ ما يتجاوز المهلة — بالطريقتين القديمة والجديدة.

    تشييخ صفّ المستخدم وحده لم يعد يُنهي شيًئا بعد الإصلاح، فلو اكتفى
    الاختبار به لمرّ أخضر وهو لم يُنشئ حالة الخمول أصًلا.
    """
    minutes = int(getattr(settings, "idle_logout_minutes", 0) or 0)
    assert minutes > 0, "المهلة معطّلة — الاختبار بلا معنى"

    tok = login(client, TARGET_CIVIL, TARGET_PASSWORD)
    client.get("/api/auth/me", headers=auth_headers(tok))
    _age_session(_sid(tok), minutes + 5)

    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(
            models.User.civil_id == TARGET_CIVIL))
        u.last_activity_at = (datetime.now(timezone.utc)
                              - timedelta(minutes=minutes + 5)).replace(tzinfo=None)
        db.commit()
        uid = u.id
    finally:
        db.close()

    assert client.get("/api/auth/me",
                      headers=auth_headers(tok)).status_code == 401
    return uid, minutes


def test_impersonating_an_idle_user_starts_a_live_session(client, idle_target):
    """**هذا هو العطل**: الجلسة الوليدة كانت تُرفض بـ401."""
    uid, _ = idle_target
    admin = auth_headers(login(client, *SUPER))
    r = client.post(f"/api/users/{uid}/impersonate", headers=admin)
    assert r.status_code == 200, r.text

    me = client.get("/api/auth/me",
                    headers=auth_headers(r.json()["access_token"]))
    assert me.status_code == 200, (
        f"جلسة الانتحال ورثت خمول المُنتحَل ورُفضت وهي وليدة: {me.text}"
    )


def test_the_impersonated_session_is_new_by_construction(client, idle_target):
    """الفرق بنيوي لا استثناء مكتوب: هوية جلسة جديدة."""
    uid, _ = idle_target
    admin = auth_headers(login(client, *SUPER))
    tok = client.post(f"/api/users/{uid}/impersonate",
                      headers=admin).json()["access_token"]
    p = decode_token(tok)
    assert p.get("sid"), "رمز الانتحال بلا هوية جلسة"
    assert p.get("impersonator_id") is not None


def test_impersonation_still_times_out_like_any_session(client, idle_target):
    """**لا تُفتح ثغرة أثناء الإصلاح**: المهلة نفسها لا أطول.

    إصلاح يطيل جلسة قد يُلغي الحماية وهو يصلح العطل.
    """
    uid, minutes = idle_target
    admin = auth_headers(login(client, *SUPER))
    tok = client.post(f"/api/users/{uid}/impersonate",
                      headers=admin).json()["access_token"]
    assert client.get("/api/auth/me", headers=auth_headers(tok)).status_code == 200

    _age_session(_sid(tok), minutes + 5)
    assert client.get("/api/auth/me",
                      headers=auth_headers(tok)).status_code == 401, (
        "جلسة الانتحال لا تنتهي بالخمول — الإصلاح فتح ثغرة"
    )


def test_impersonation_does_not_fake_the_real_user_presence(client, idle_target):
    """من انتُحلت شخصيته لم يفتح النظام: لا يُسجَّل حاضًرا."""
    uid, _ = idle_target
    db = SessionLocal()
    try:
        before = db.get(models.User, uid).last_activity_at
    finally:
        db.close()

    admin = auth_headers(login(client, *SUPER))
    tok = client.post(f"/api/users/{uid}/impersonate",
                      headers=admin).json()["access_token"]
    for _ in range(3):
        client.get("/api/auth/me", headers=auth_headers(tok))

    db = SessionLocal()
    try:
        after = db.get(models.User, uid).last_activity_at
    finally:
        db.close()
    assert after == before, (
        "نشاط المُنتحِل كُتب على المُنتحَل — يبدو حاضًرا وهو غائب"
    )


def test_two_sessions_of_one_user_are_independent(client):
    """IMP-02 — متصفّحان لا يقتل أحدهما الآخر ولا يُحييه."""
    minutes = int(getattr(settings, "idle_logout_minutes", 0) or 0)
    a = login(client, TARGET_CIVIL, TARGET_PASSWORD)
    b = login(client, TARGET_CIVIL, TARGET_PASSWORD)
    client.get("/api/auth/me", headers=auth_headers(a))
    client.get("/api/auth/me", headers=auth_headers(b))
    assert _sid(a) != _sid(b), "جلستان بهوية واحدة"

    _age_session(_sid(a), minutes + 5)
    assert client.get("/api/auth/me", headers=auth_headers(a)).status_code == 401
    assert client.get("/api/auth/me", headers=auth_headers(b)).status_code == 200, (
        "خمول جلسة أنهى جلسة أخرى للمستخدم نفسه"
    )


def test_refreshing_keeps_the_same_session(client):
    """التجديد استمرار لا بداية.

    لو حمل الرمز الجديد هوية جديدة لصُفِّر عدّاد الخمول عند كل تجديد فلا
    تنتهي جلسة أبًدا. ولو قِيس الخمول على ``jti`` بدل ``sid`` لبدت الجلسة
    النشطة خاملة عند أول تجديد وطُردت وهي تعمل — وهذا ما حدث فعًلا في أول
    كتابة، وكشفه اختبار الخمول القائم.
    """
    lr = client.post("/api/auth/login", json={"civil_id": TARGET_CIVIL,
                                              "password": TARGET_PASSWORD})
    access, refresh = lr.json()["access_token"], lr.json()["refresh_token"]
    client.get("/api/auth/me", headers=auth_headers(access))

    rr = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert rr.status_code == 200, rr.text
    assert _sid(rr.json()["access_token"]) == _sid(access), (
        "التجديد بدأ جلسة جديدة — عدّاد الخمول يُصفَّر كل نصف ساعة"
    )


def test_an_idle_session_cannot_be_revived_by_refreshing(client):
    """والخمول لا يُحيي نفسه: التجديد لا ينقذ جلسة ماتت."""
    minutes = int(getattr(settings, "idle_logout_minutes", 0) or 0)
    lr = client.post("/api/auth/login", json={"civil_id": TARGET_CIVIL,
                                              "password": TARGET_PASSWORD})
    access, refresh = lr.json()["access_token"], lr.json()["refresh_token"]
    client.get("/api/auth/me", headers=auth_headers(access))
    _age_session(_sid(access), minutes + 5)

    rr = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert rr.status_code == 401, "التجديد أحيا جلسة خاملة"
