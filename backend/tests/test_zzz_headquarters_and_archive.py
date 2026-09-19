# -*- coding: utf-8 -*-
"""مقرُّ الشركة وأرشفُة الفرع — طلب المالك (2026-09-19).

- «مقر الشركة» ليس فرًعا: واحٌد لكل شركة، ومرحلُة «مسؤول الفرع» لموظفيه
  يعتمدها مديُر الشركة (كانت تقف: لا مسؤول على المقر).
- الفرُع المكرَّر أو الخارج عن ملف الشركة **يُؤرشَف لا يُحذف**: يختفي من
  القوائم والحضور ويبقى تاريخه — ولا يُؤرشَف وعليه موظفون، ولا يُؤرشَف المقر.
"""
from __future__ import annotations

import secrets

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

MGR = ("100000000001", "manager123")
ACC = ("100000000007", "account123")


def _hq(company_id=1):
    db = SessionLocal()
    try:
        return db.scalar(select(models.Branch).where(
            models.Branch.company_id == company_id, models.Branch.is_headquarters.is_(True)))
    finally:
        db.close()


def test_one_headquarters_per_company(client):
    hq = _hq()
    assert hq is not None and hq.name == "مقر الشركة"
    r = client.post("/api/companies/1/headquarters", headers=auth_headers(login(client, *MGR)),
                    json={"name": "x"})
    assert r.status_code == 409, r.text[:150]
    listed = client.get("/api/branches", headers=auth_headers(login(client, *MGR))).json()
    assert any(b["id"] == hq.id and b["is_headquarters"] for b in listed)


def test_hq_staff_requests_go_to_the_company_manager(client):
    from app import workflow as W

    db = SessionLocal()
    try:
        acc = db.scalar(select(models.User).where(models.User.civil_id == ACC[0]))
        emp = db.get(models.Employee, acc.employee_id)
        hq = _hq(emp.company_id)
        old = emp.branch_id
        emp.branch_id = hq.id
        db.commit()
        req = models.Request(company_id=emp.company_id, employee_id=emp.id,
                             request_type_code="REQGEN", payload_json={}, status="pending")
        users = W.resolve_stage_approvers(db, req, {"role": "branch_supervisor"})
        roles = {u.role for u in users}
        emp.branch_id = old
        db.commit()
    finally:
        db.close()
    assert "company_manager" in roles, roles


def _empty_branch():
    db = SessionLocal()
    try:
        b = models.Branch(company_id=1, name="فرع مكرر للاختبار", code="DUP9",
                          qr_secret=secrets.token_hex(8), kiosk_key="k-dup9")
        db.add(b)
        db.commit()
        return b.id
    finally:
        db.close()


def test_an_empty_duplicate_is_archived_hidden_and_restorable(client):
    h = auth_headers(login(client, *MGR))
    bid = _empty_branch()
    assert client.post(f"/api/branches/{bid}/archive", headers=h,
                       params={"reason": " "}).status_code == 400
    r = client.post(f"/api/branches/{bid}/archive", headers=h, params={"reason": "مكرر GU06"})
    assert r.status_code == 200 and r.json()["status"] == "archived", r.text[:150]
    assert bid not in {b["id"] for b in client.get("/api/branches", headers=h).json()}
    assert bid in {b["id"] for b in client.get("/api/branches", headers=h,
                                               params={"include_archived": True}).json()}
    k = client.get(f"/api/kiosk/{bid}/qr", params={"key": "k-dup9"})
    assert k.status_code == 403 and "مؤرشَف" in k.text, k.text[:120]
    assert client.post(f"/api/branches/{bid}/restore", headers=h).json()["status"] == "active"
    from tests.conftest import purge

    db = SessionLocal()
    try:
        purge(db, "branches", [bid])
        db.commit()
    finally:
        db.close()


def test_a_branch_with_staff_or_the_hq_is_not_archived(client):
    h = auth_headers(login(client, *MGR))
    db = SessionLocal()
    try:
        busy = db.scalar(select(models.Employee.branch_id).join(
            models.Branch, models.Branch.id == models.Employee.branch_id).where(
            models.Employee.company_id == 1, models.Employee.status == "active",
            models.Branch.is_headquarters.is_(False)))
    finally:
        db.close()
    r = client.post(f"/api/branches/{busy}/archive", headers=h, params={"reason": "x"})
    assert r.status_code == 409 and "موظف" in r.text, r.text[:150]
    r = client.post(f"/api/branches/{_hq().id}/archive", headers=h, params={"reason": "x"})
    assert r.status_code == 409, r.text[:150]
