# -*- coding: utf-8 -*-
"""ينقل موظفي كل شركة **الذين بلا فرع** إلى «مقر الشركة» — بدخول الإدارة العليا.

قرار المالك (2026-09-23): الإداريون (مدير/HR/محاسب/مندوب) على المقر. والنقل المباشر
للإدارة العليا وحدها (``POST /employees/{id}/assign-branch``) وبسببٍ مُقيَّد.
لا يمسّ من له فرعٌ أصلًا، ولا شركةً بلا مقر (يُقال ويُترك).

    python scripts/move_admin_staff_to_hq.py            # تقرير فقط
    python scripts/move_admin_staff_to_hq.py --apply    # ينقل
"""
from __future__ import annotations

import argparse
import getpass

import httpx

REASON = "وضع الإداريين على مقر الشركة (قرار المالك 2026-09-23)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="https://hrms-kuwait-production.up.railway.app")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    base = a.api.rstrip("/") + "/api"

    civil = input("الرقم المدني: ").strip()
    pw = getpass.getpass("كلمة المرور (لا تظهر): ")
    r = httpx.post(base + "/auth/login", json={"civil_id": civil, "password": pw}, timeout=60)
    if r.status_code != 200:
        raise SystemExit(f"تعذّر الدخول ({r.status_code})")
    del pw
    s = httpx.Client(headers={"Authorization": f"Bearer {r.json()['access_token']}"}, timeout=60)

    print("=== " + ("نُفِّذ" if a.apply else "تقرير فقط — لم يُكتب شيء") + " ===")
    total = 0
    for co in s.get(base + "/companies").json():
        cid = co["id"]
        branches = s.get(base + "/branches", params={"company_id": cid}).json()
        hq = next((b for b in branches if b.get("is_headquarters")), None)
        emps, off = [], 0
        while True:
            page = s.get(base + "/employees", params={"company_id": cid, "limit": 500, "offset": off}).json()
            page = page if isinstance(page, list) else page.get("items", [])
            emps += page
            if len(page) < 500:
                break
            off += 500
        loose = [e for e in emps if not e.get("branch_id")]
        print(f"\n#{cid} {co['name']} — بلا فرع: {len(loose)}")
        if loose and not hq:
            print("  ✗ لا مقر للشركة — شغّل مطابقة الشركات أولًا")
            continue
        for e in loose:
            line = f"  • {e.get('full_name') or e.get('name')} (#{e['id']}) → {hq['name']}"
            if a.apply:
                x = s.post(base + f"/employees/{e['id']}/assign-branch",
                           params={"branch_id": hq["id"], "reason": REASON})
                line += "  ✓" if x.status_code == 200 else f"  ✗ {x.status_code} {x.text[:120]}"
                total += x.status_code == 200
            print(line)
    print(f"\nنُقل: {total}" if a.apply else "\nلإجرائه فعلًا: أضف --apply")


if __name__ == "__main__":
    main()
