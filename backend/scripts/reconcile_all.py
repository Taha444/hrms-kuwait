# -*- coding: utf-8 -*-
"""مطابقة الشركات الخمس بملفاتها عبر الموقع — بدخولٍ واحد.

نفس ``app.import_company_package --api`` لكل ملف في ``docs/data``، لكن الرقم المدني
وكلمة المرور يُطلبان **مرة واحدة** (كلمة المرور لا تُطبَع ولا تُحفَظ ولا تمرّ بسطر الأوامر).

    python scripts/reconcile_all.py                              # تقرير فقط
    python scripts/reconcile_all.py --apply --delete-extras     # ينفّذ

يحتاج حساًبا يملك «إدارة الفروع» و«إدارة التراخيص» (الإدارة العليا).
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.import_company_package import run_api  # noqa: E402

DATA = Path(__file__).resolve().parents[2] / "docs" / "data"
FILES = ["gulf_union_import.json", "milano_import.json", "blue_nile_import.json",
         "qimat_al_nile_import.json", "mohamed_ibrahim_import.json"]
SECTIONS = (("company", "الشركة"), ("branches", "الفروع"), ("licenses", "التراخيص"),
            ("extras", "فروعٌ تخالف ملف الشركة"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="https://hrms-kuwait-production.up.railway.app")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--archive-extras", action="store_true")
    ap.add_argument("--delete-extras", action="store_true")
    a = ap.parse_args()

    civil = input("الرقم المدني: ").strip()
    pw = getpass.getpass("كلمة المرور (لا تظهر): ")
    r = httpx.post(a.api.rstrip("/") + "/api/auth/login",
                   json={"civil_id": civil, "password": pw}, timeout=60)
    if r.status_code != 200:
        raise SystemExit(f"تعذّر الدخول ({r.status_code})")
    token = r.json()["access_token"]
    del pw

    print("=== " + ("نُفِّذ" if a.apply else "تقرير فقط — لم يُكتب شيء") + " ===")
    for name in FILES:
        data = json.loads((DATA / name).read_text(encoding="utf-8"))
        data["documents"] = []   # المستندات لها حزمتها وأمرها؛ هنا المقر والتراخيص والفروع فقط
        print(f"\n################ {name}")
        try:
            rep = run_api(data, Path("."), apply=a.apply, base=a.api, token=token,
                          archive_extras=a.archive_extras,
                          delete_extras=a.delete_extras)
        except SystemExit as e:
            print(f"  ✗ توقّف: {e}")
            continue
        for key, title in SECTIONS:
            if rep.get(key):
                print(f"\n{title}:")
                print("\n".join(rep[key]))
        for key, title in (("skipped", "متروك"), ("blocked", "موقوف — يحتاج قرارك")):
            if rep.get(key):
                print(f"\n{title}:")
                print("\n".join(f"  · {x}" for x in rep[key]))
    if not a.apply:
        print("\nلإجرائه فعًلا: أضف --apply --delete-extras")


if __name__ == "__main__":
    main()
