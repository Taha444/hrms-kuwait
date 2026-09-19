# -*- coding: utf-8 -*-
"""إدخال الاتحاد الخليجي وميلانو — بفروعهما وإحداثياتها، بلا مستندات.

- ملفُّ بلا مستندات يُدخَل بلا مجلد حزمة.
- الفروُع تُنشأ بإحداثيات كويت فايندر ونصف القطر (قرار 32) من ملف البيانات.
- والتشغيُل الثاني لا يُضاعف فرًعا، ولا يكتب فوق إحداثيٍّ موجود.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.import_company_package import run
from tests.conftest import purge

DATA = Path(__file__).resolve().parents[2] / "docs" / "data"


@pytest.mark.parametrize("fname", ["gulf_union_import.json", "milano_import.json"])
def test_the_file_is_consistent(fname):
    d = json.loads((DATA / fname).read_text(encoding="utf-8"))
    assert d["documents"] == []
    codes = [b["code"] for b in d["branches"]]
    assert len(codes) == len(set(codes)) and all(len(c) <= 6 for c in codes), codes
    for b in d["branches"]:
        assert 28.5 < b["latitude"] < 30.2 and 46.5 < b["longitude"] < 48.6, b["code"]
        assert b["geofence_radius_m"] in (100, 200)
        assert b["governorate"] and b["governorate_en"]
        if b["paci_address_no"]:
            m = re.search(r"الرقم الآلي للعنوان:\s*(\d+)", b["address"])
            assert m and m.group(1) == b["paci_address_no"], b["code"]
        assert b["expiry"] is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}", b["expiry"])


@pytest.mark.parametrize("fname", ["gulf_union_import.json", "milano_import.json"])
def test_import_creates_branches_with_their_points(fname):
    d = json.loads((DATA / fname).read_text(encoding="utf-8"))
    db = SessionLocal()
    co = models.Company(name=d["company"]["name"])
    db.add(co)
    db.commit()
    cid = co.id
    try:
        report = run(d, Path("."), apply=True, db=db)
        db.commit()
        assert not report["blocked"], report["blocked"]
        rows = {b.code: b for b in db.scalars(select(models.Branch).where(
            models.Branch.company_id == cid)).all()}
        assert set(rows) == {b["code"] for b in d["branches"]}
        for b in d["branches"]:
            r = rows[b["code"]]
            assert (r.latitude, r.longitude, r.geofence_radius_m) == (
                b["latitude"], b["longitude"], b["geofence_radius_m"]), b["code"]
            assert r.address == b["address"] and r.governorate == b["governorate"]
        # مرًة ثانية: لا مضاعفة، ولا كتابة فوق إحداثيٍّ عُدِّل باليد.
        first = d["branches"][0]["code"]
        rows[first].latitude = 29.0
        db.commit()
        run(d, Path("."), apply=True, db=db)
        db.commit()
        again = db.scalars(select(models.Branch).where(models.Branch.company_id == cid)).all()
        assert len(again) == len(rows)
        assert next(b for b in again if b.code == first).latitude == 29.0
    finally:
        ids = [b.id for b in db.scalars(select(models.Branch).where(
            models.Branch.company_id == cid)).all()]
        if ids:
            purge(db, "branches", ids)
        purge(db, "companies", [cid])
        db.close()
