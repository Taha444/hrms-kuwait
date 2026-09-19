# -*- coding: utf-8 -*-
"""مطابقُة شركٍة بملفّها عبر الموقع — طلب المالك (2026-09-19).

الحالُة كما وقعت: الاتحاد الخليجي قائمٌة بفروٍع قديمٍة برموٍز أخرى (GUF6…)،
واستُوردت فروُعها من الملف (GU02…). فالمطابقة:
- تُنشئ «مقر الشركة» إن لم يكن.
- تسجّل كلَّ ترخيٍص في الملف **بتاريخ انتهائه** (كانت التراخيص لا تُسجَّل أصلًا).
- تعرض الفروَع الخارجة عن الملف، وتؤرشف منها — بطلبه — ما لا موظفين عليه،
  وتقول عن الباقي إلى أين يُنقل موظفوه. **ولا تحذف شيًئا.**
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.import_company_package import run_api
from app.main import app
from tests.conftest import login, purge

DATA = Path(__file__).resolve().parents[2] / "docs" / "data" / "gulf_union_import.json"
ADMIN = ("000000000000", "admin123")


@pytest.fixture
def company_with_old_branches():
    db = SessionLocal()
    co = models.Company(name="شركة الاتحاد الخليجي للأقمشة")
    db.add(co)
    db.flush()
    empty = models.Branch(company_id=co.id, name="Reem Fashion", code="GUF6",
                          address="Qibla", qr_secret=secrets.token_hex(8))
    busy = models.Branch(company_id=co.id, name="Silver Fashion", code="GUF7",
                         address="Qibla", qr_secret=secrets.token_hex(8))
    db.add_all([empty, busy])
    db.flush()
    emp = models.Employee(company_id=co.id, name="موظف فعلي", branch_id=busy.id, status="active")
    db.add(emp)
    db.commit()
    ids = (co.id, empty.id, busy.id, emp.id)
    db.close()
    yield ids
    db = SessionLocal()
    try:
        cid = ids[0]
        purge(db, "employees", [ids[3]])
        purge(db, "licenses", [x.id for x in db.scalars(select(models.License).where(
            models.License.company_id == cid)).all()])
        purge(db, "branches", [x.id for x in db.scalars(select(models.Branch).where(
            models.Branch.company_id == cid)).all()])
        purge(db, "companies", [cid])
        db.commit()
    finally:
        db.close()


def _run(client, monkeypatch, *, archive: bool):
    token = login(client, *ADMIN)
    monkeypatch.setattr(httpx, "Client", lambda **kw: client.__class__(
        app, headers=kw.get("headers")))
    data = json.loads(DATA.read_text(encoding="utf-8"))
    return run_api(data, Path("."), apply=True, base="http://testserver", token=token,
                   archive_extras=archive)


def test_reconcile_creates_hq_licenses_and_handles_extras(client, monkeypatch,
                                                          company_with_old_branches):
    cid, empty_id, busy_id, _ = company_with_old_branches
    data = json.loads(DATA.read_text(encoding="utf-8"))

    rep = _run(client, monkeypatch, archive=False)
    assert not [b for b in rep["blocked"] if "تعذّر" in b], rep["blocked"]
    db = SessionLocal()
    try:
        hq = db.scalar(select(models.Branch).where(
            models.Branch.company_id == cid, models.Branch.is_headquarters.is_(True)))
        assert hq is not None and hq.name == "مقر الشركة" and hq.latitude == 29.372842
        lics = {x.license_no: x for x in db.scalars(select(models.License).where(
            models.License.company_id == cid)).all()}
        want = {b["license_no"] for b in data["branches"]} | {data["headquarters"]["license_no"]}
        assert want <= set(lics), want - set(lics)
        gu02 = next(b for b in data["branches"] if b["code"] == "GU02")
        assert str(lics[gu02["license_no"]].expiry_date) == gu02["expiry"]
        assert db.get(models.Branch, empty_id).status == "active", "أُرشف بلا طلب"
    finally:
        db.close()
    text = "\n".join(rep["extras"])
    assert "GUF6" in text and "GU06" in text, text      # غالبًا المحلُّ نفسه
    assert "GUF7" in text and "انقلهم" in text, text

    rep2 = _run(client, monkeypatch, archive=True)
    db = SessionLocal()
    try:
        assert db.get(models.Branch, empty_id).status == "archived"
        assert db.get(models.Branch, busy_id).status == "active", "أُرشف فرٌع عليه موظف"
        n_hq = len(db.scalars(select(models.Branch).where(
            models.Branch.company_id == cid, models.Branch.is_headquarters.is_(True))).all())
        n_lic = len(db.scalars(select(models.License).where(models.License.company_id == cid)).all())
    finally:
        db.close()
    assert n_hq == 1, "مقرٌّ ثاٍن في التشغيل الثاني"
    assert n_lic == len(want), "ترخيٌص مكرّر في التشغيل الثاني"
    assert any("أُرشف" in x for x in rep2["extras"]), rep2["extras"]
