# -*- coding: utf-8 -*-
"""صورة المستخدم لشركته — قرار المالك (2026-09-18).

``/users/{id}/avatar/image`` كانت تُعطي صورَة أيّ مستخدم لأيّ مسجَّل دخول،
ومن أيّ شركة: معرِّفاٌت متتالية تُعدِّد وجوَه موظفي الشركات الأخرى.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR1 = ("100000000002", "hr12345")
HR2 = ("200000000002", "hr12345")
OWNER = ("111111111111", "owner123")

PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000050001a5f645ea0000000049454e44ae426082")


def _hr1_with_avatar(client) -> tuple[int, dict]:
    h = auth_headers(login(client, *HR1))
    r = client.post("/api/me/avatar", headers=h, files={"file": ("a.png", PNG, "image/png")})
    assert r.status_code == 200, r.text[:150]
    db = SessionLocal()
    try:
        return db.scalar(select(models.User.id).where(models.User.civil_id == HR1[0])), h
    finally:
        db.close()


def test_another_companys_user_cannot_open_the_photo(client):
    uid, h = _hr1_with_avatar(client)
    try:
        r = client.get(f"/api/users/{uid}/avatar/image", headers=auth_headers(login(client, *HR2)))
        assert r.status_code in (403, 404), r.status_code
    finally:
        client.delete("/api/me/avatar", headers=h)


def test_same_company_and_owner_still_see_it(client):
    uid, h = _hr1_with_avatar(client)
    try:
        assert client.get(f"/api/users/{uid}/avatar/image", headers=h).status_code == 200
        r = client.get(f"/api/users/{uid}/avatar/image", headers=auth_headers(login(client, *OWNER)))
        assert r.status_code == 200
    finally:
        client.delete("/api/me/avatar", headers=h)
