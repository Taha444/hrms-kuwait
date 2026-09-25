# -*- coding: utf-8 -*-
"""M20 #4 — اللوحة تُعلن نطاق أرقامها (كل الشركات مجتمعة / شركة بعينها) ولا تتركه للاستنتاج."""
from pathlib import Path

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

SCREEN = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "Dashboard.tsx"


def test_the_dashboard_declares_whether_figures_are_global_or_one_company(client):
    owner = auth_headers(login(client, "111111111111", "owner123"))
    allc = client.get("/api/dashboard", headers=owner).json()["scope"]
    assert allc == {"all_companies": True, "company_id": None, "company_name": None}
    db = SessionLocal()
    name2 = db.scalar(select(models.Company.name).where(models.Company.id == 2))
    db.close()
    one = client.get("/api/dashboard", headers=owner, params={"company_id": 2}).json()["scope"]
    assert one == {"all_companies": False, "company_id": 2, "company_name": name2}
    mgr = auth_headers(login(client, "100000000001", "manager123"))
    own = client.get("/api/dashboard", headers=mgr).json()["scope"]
    assert own["all_companies"] is False and own["company_id"] == 1


def test_the_screen_renders_the_declared_scope():
    src = SCREEN.read_text(encoding="utf-8")
    assert src.count("data.scope") >= 2 and "dash_scope_all" in src and "dash_scope_company" in src
