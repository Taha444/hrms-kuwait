# -*- coding: utf-8 -*-
"""فحُص ما بعد النشر يقيس نقاطًا موجودة — لا مساراتٍ تخيّلها كاتبه.

كُتب أوَّل مرٍة بـ``/api/requests`` و``/api/tasks``، ولا ``GET`` عليهما:
فردّا 404 وقُرئ ذلك «فشًلا» في الإنتاج وهو خطأُ الفاحص. فكلُّ مساٍر يفحصه
``scripts/smoke_prod.py`` على أنه محروس يُثبَت هنا أنه ``GET`` قائم.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


def test_every_protected_path_the_smoke_checks_is_a_real_get_route():
    from app.main import app

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("smoke_prod", root / "scripts" / "smoke_prod.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    gets = {r.path for r in app.routes if "GET" in (getattr(r, "methods", None) or ())}
    missing = [p for p in mod.PROTECTED if p not in gets]
    assert not missing, f"مساراتٌ يفحصها السكربت ولا GET عليها: {missing}"
