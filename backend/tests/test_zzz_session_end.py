# -*- coding: utf-8 -*-
"""الخروج وإنهاء الانتحال — هل يفعلان ما يقولانه؟

JWT لا يُسترجع: من حمله ظلّ صالًحا حتى انقضاء مدّته. فكان الزرّان يكتبان في
السجل ويمسحان المتصفح ولا يمسّان الرمز نفسه — رمز دخول نصف ساعة، ورمز
تجديد أربعة عشر يوًما. زرّان يقولان إن الجلسة انتهت وهي لم تنتهِ، وهذا هو
النمط الذي يبدو نجاًحا وليس به.
"""
from __future__ import annotations

from .conftest import auth_headers

EMP = ("100000000101", "emp12345")
SUPER = ("000000000000", "admin123")


def _login(client, creds=EMP):
    r = client.post("/api/auth/login",
                    json={"civil_id": creds[0], "password": creds[1]})
    assert r.status_code == 200, r.text
    return r.json()


def test_logout_invalidates_the_access_token(client):
    """الرمز الذي كان يعمل قبل الخروج لا يعمل بعده."""
    t = _login(client)
    h = auth_headers(t["access_token"])
    assert client.get("/api/auth/me", headers=h).status_code == 200

    assert client.post("/api/auth/logout", headers=h,
                       json={"refresh_token": t["refresh_token"]}).status_code == 200

    assert client.get("/api/auth/me", headers=h).status_code == 401, (
        "رمز الدخول ما زال يعمل بعد الخروج — الجلسة لم تنتهِ فعًلا"
    )


def test_logout_invalidates_the_refresh_token(client):
    """رمز التجديد أخطر: يولّد رموز دخول جديدة أربعة عشر يوًما."""
    t = _login(client)
    client.post("/api/auth/logout", headers=auth_headers(t["access_token"]),
                json={"refresh_token": t["refresh_token"]})

    r = client.post("/api/auth/refresh", json={"refresh_token": t["refresh_token"]})
    assert r.status_code == 401, (
        "رمز التجديد نجا من الخروج — الباب مفتوح أسبوعين"
    )


def test_logout_does_not_end_the_users_other_devices(client):
    """من خرج من حاسوب المكتب لا يخرج من هاتفه معه.

    هذا سبب رفض البديل الأسهل (رفع tokens_valid_after): كان يُخرج المستخدم
    من كل أجهزته عقوبة على خروجه من جهاز واحد.
    """
    phone = _login(client)
    desk = _login(client)
    client.post("/api/auth/logout", headers=auth_headers(desk["access_token"]),
                json={"refresh_token": desk["refresh_token"]})
    assert client.get("/api/auth/me",
                      headers=auth_headers(phone["access_token"])).status_code == 200, (
        "الخروج من جهاز أنهى جلسة الجهاز الآخر"
    )


def _impersonate(client):
    from app import models
    from app.database import SessionLocal
    admin = _login(client, SUPER)
    db = SessionLocal()
    try:
        tid = db.query(models.User).filter(
            models.User.civil_id == EMP[0]).one().id
    finally:
        db.close()
    r = client.post(f"/api/users/{tid}/impersonate",
                    headers=auth_headers(admin["access_token"]))
    assert r.status_code == 200, r.text
    return r.json()


def test_impersonate_end_actually_ends_it(client):
    """بعد «إنهاء الانتحال» لا تبقى رموز المُنتحَل صالحة بيد الإدارة العليا."""
    imp = _impersonate(client)
    h = auth_headers(imp["access_token"])
    assert client.get("/api/auth/me", headers=h).status_code == 200

    assert client.post("/api/users/impersonate-end", headers=h,
                       json={"refresh_token": imp["refresh_token"]}).status_code == 200

    assert client.get("/api/auth/me", headers=h).status_code == 401, (
        "رمز الانتحال ما زال يعمل بعد إنهائه"
    )
    assert client.post("/api/auth/refresh",
                       json={"refresh_token": imp["refresh_token"]}).status_code == 401, (
        "رمز تجديد الانتحال نجا — الانتحال يجدّد نفسه أسبوعين بعد إنهائه"
    )


def test_impersonate_end_spares_the_impersonated_users_own_session(client):
    """المُنتحَل لم يفعل شيًئا يستحقّ إخراجه من أجهزته."""
    his_own = _login(client)          # الموظف داخل من جهازه
    imp = _impersonate(client)
    client.post("/api/users/impersonate-end", headers=auth_headers(imp["access_token"]),
                json={"refresh_token": imp["refresh_token"]})
    assert client.get("/api/auth/me",
                      headers=auth_headers(his_own["access_token"])).status_code == 200, (
        "إنهاء الانتحال أخرج المُنتحَل الحقيقي من جلسته"
    )


def test_revocation_list_is_cleaned_of_expired_rows(client):
    """الجدول لا ينمو بلا حدّ: ما انتهت مدّته يرفضه انتهاؤه نفسه."""
    from datetime import datetime, timedelta

    from app import models
    from app.database import SessionLocal
    from app.token_revocation import purge_expired

    db = SessionLocal()
    try:
        past = datetime.utcnow() - timedelta(days=1)
        db.add(models.RevokedToken(jti="منتهٍ-للتنظيف", expires_at=past,
                                   reason="test"))
        db.add(models.RevokedToken(jti="ما-زال-حيًّا",
                                   expires_at=datetime.utcnow() + timedelta(days=1),
                                   reason="test"))
        db.commit()
        purge_expired(db)
        assert db.get(models.RevokedToken, "منتهٍ-للتنظيف") is None, (
            "الصفوف المنتهية لم تُنظَّف — الجدول ينمو بلا حدّ"
        )
        assert db.get(models.RevokedToken, "ما-زال-حيًّا") is not None, (
            "التنظيف حذف رمًزا ما زال يجب رفضه"
        )
        db.delete(db.get(models.RevokedToken, "ما-زال-حيًّا"))
        db.commit()
    finally:
        db.close()
