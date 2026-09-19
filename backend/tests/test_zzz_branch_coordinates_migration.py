# -*- coding: utf-8 -*-
"""إحداثياُت الفروع من كويت فايندر — البياناُت والترحيل.

- كلُّ فرٍع في ملفات استيراد الشركات له إحداثيٌّ، ورقمُه الآلي هو نفسه المكتوب في
  عنوانه، ونقطتُه داخل الكويت.
- والترحيُل يطابق بالرقم الآلي ثم بالرمز، ولا يكتب فوق إحداثياٍت موجودة،
  وعكسُه يمحو ما وضعه وحده.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "alembic" / "versions" / "k9f0a1b2c3d_branch_coordinates_paci.py"


def _mig():
    spec = importlib.util.spec_from_file_location("mig_coords", MIG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_imported_branch_has_its_own_paci_point_inside_kuwait():
    rows = {code: (paci, lat, lng) for code, paci, lat, lng, _ in _mig().BRANCHES}
    seen = set()
    # الشركاُت الثالث التي كانت في النظام قبل الترحيل؛ والاتحاد الخليجي وميلانو
    # يدخلان بإحداثياتهما في ملفات الاستيراد نفسها (test_zzz_import_new_companies).
    for name in ("blue_nile_import.json", "mohamed_ibrahim_import.json", "qimat_al_nile_import.json"):
        f = ROOT.parent / "docs" / "data" / name
        for b in json.loads(f.read_text(encoding="utf-8")).get("branches", []):
            seen.add(b["code"])
            assert b["code"] in rows, f"فرعٌ بلا إحداثي: {b['code']}"
            paci, lat, lng = rows[b["code"]]
            m = re.search(r"الرقم الآلي للعنوان:\s*(\d+)", b.get("address") or "")
            assert m and m.group(1) == paci, (b["code"], b.get("address"), paci)
            assert 28.5 < lat < 30.2 and 46.5 < lng < 48.6, (b["code"], lat, lng)
    assert seen == set(rows), set(rows) ^ seen


def _alembic(url: str, *args: str) -> None:
    env = dict(os.environ, DATABASE_URL=url, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stdout[-1200:] + r.stderr[-1200:]


def test_the_migration_matches_by_paci_then_code_and_keeps_manual_points(tmp_path):
    db = tmp_path / "coords.db"
    url = f"sqlite:///{db.as_posix()}"
    _alembic(url, "upgrade", "i7d8e9f0a1b")
    con = sqlite3.connect(db)
    ins = ("INSERT INTO branches (company_id, name, code, address, latitude, longitude, "
           "geofence_radius_m, qr_secret, auto_checkout_minutes, created_at) "
           "VALUES (1,?,?,?,?,?,100,'s',15,'2026-09-19 00:00:00')")
    con.execute(ins, ("بالرقم الآلي", "X1", "الجهراء — الرقم الآلي للعنوان: 14708253", None, None))
    con.execute(ins, ("بالرمز", "QNKFC", "عنوانٌ بلا رقم", None, None))
    con.execute(ins, ("يدوي", "BN05", "الفحيحيل — الرقم الآلي للعنوان: 13813772", 29.1, 48.1))
    con.execute(ins, ("غريب", "ZZ9", "لا علاقة", None, None))
    con.commit()
    con.close()

    _alembic(url, "upgrade", "k9f0a1b2c3d")
    con = sqlite3.connect(db)
    got = {r[0]: (r[1], r[2]) for r in con.execute("SELECT name, latitude, longitude FROM branches")}
    assert got["بالرقم الآلي"] == (29.349444, 47.668653)
    assert got["بالرمز"] == (29.306833, 47.932261)
    assert got["يدوي"] == (29.1, 48.1), "كُتب فوق إحداثيٍّ أُدخل باليد"
    assert got["غريب"] == (None, None)
    con.close()

    _alembic(url, "downgrade", "i7d8e9f0a1b")
    con = sqlite3.connect(db)
    got = {r[0]: (r[1], r[2]) for r in con.execute("SELECT name, latitude, longitude FROM branches")}
    assert got["بالرقم الآلي"] == (None, None) and got["بالرمز"] == (None, None)
    assert got["يدوي"] == (29.1, 48.1), "العكسُ محا ما لم يضعه"
    con.close()


def test_market_branches_get_200m_unless_set_by_hand(tmp_path):
    """قرار المالك (2026-09-19): 200م للأسواق الكبيرة، و100م للمباني المنفصلة."""
    db = tmp_path / "radius.db"
    url = f"sqlite:///{db.as_posix()}"
    _alembic(url, "upgrade", "k9f0a1b2c3d")
    con = sqlite3.connect(db)
    ins = ("INSERT INTO branches (company_id, name, code, address, geofence_radius_m, qr_secret, "
           "auto_checkout_minutes, created_at) VALUES (1,?,?,?,?,'s',15,'2026-09-19 00:00:00')")
    con.execute(ins, ("سوق الصفاة", "MAI02", "القبلة — الرقم الآلي للعنوان: 10228877", 100))
    con.execute(ins, ("كاظمة يدوي", "BN01", "الجهراء — الرقم الآلي للعنوان: 14708253", 120))
    con.execute(ins, ("الفحيحيل", "BN05", "الفحيحيل — الرقم الآلي للعنوان: 13813772", 100))
    con.commit()
    con.close()
    _alembic(url, "upgrade", "l0a1b2c3d4e")
    con = sqlite3.connect(db)
    got = dict(con.execute("SELECT name, geofence_radius_m FROM branches"))
    con.close()
    assert got == {"سوق الصفاة": 200, "كاظمة يدوي": 120, "الفحيحيل": 100}, got
    _alembic(url, "downgrade", "k9f0a1b2c3d")
    con = sqlite3.connect(db)
    got = dict(con.execute("SELECT name, geofence_radius_m FROM branches"))
    con.close()
    assert got == {"سوق الصفاة": 100, "كاظمة يدوي": 120, "الفحيحيل": 100}, got
