# -*- coding: utf-8 -*-
"""روابط البوابات الحكومية مشتركة ويديرها صاحب الشركات — قرار المالك (2026-09-18).

الروابط بلا شركة: جدوٌل واحد يقرؤه الجميع. وكان يعدّله **مدير أيّ شركة** —
فمديُر شركٍة واحدة يغيّر رابًطا يفتحه مندوبو الشركات كلّها. فصارت
الإدارُة لصاحب الشركات (ومعه super_admin)، والقراءُة للجميع كما كانت.
"""
from __future__ import annotations

from tests.conftest import auth_headers, login

OWNER = ("111111111111", "owner123")
MANAGER = ("100000000001", "manager123")
DELEGATE = ("100000000003", "deleg123")

BODY = {"name_ar": "رابط حارس", "url": "https://example.gov.kw/guard", "category": "other_services"}


def test_a_company_manager_cannot_edit_the_shared_links(client):
    r = client.post("/api/gov-portals", json=BODY, headers=auth_headers(login(client, *MANAGER)))
    assert r.status_code == 403, (r.status_code, r.text[:150])


def test_the_company_owner_manages_them(client):
    h = auth_headers(login(client, *OWNER))
    r = client.post("/api/gov-portals", json=BODY, headers=h)
    assert r.status_code == 201, r.text[:150]
    pid = r.json()["id"]
    assert client.get("/api/gov-portals", headers=h).json()["can_manage"] is True
    r = client.put(f"/api/gov-portals/{pid}", json={**BODY, "is_active": False}, headers=h)
    assert r.status_code == 200, r.text[:150]
    r = client.delete(f"/api/gov-portals/{pid}", headers=h)
    assert r.status_code == 200, r.text[:150]


def test_the_delegate_still_reads_them_without_managing(client):
    r = client.get("/api/gov-portals", headers=auth_headers(login(client, *DELEGATE)))
    assert r.status_code == 200
    assert r.json()["can_manage"] is False
