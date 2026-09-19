# -*- coding: utf-8 -*-
"""كشف شركٍة على الموقع — **قراءٌة فقط، لا يكتب شيًئا**.

جاء بعد استيراد الاتحاد الخليجي: الشركُة (#1) كانت قائمًة بفروٍع بأكواٍد أخرى
(GUF6…) — والمستورِد وقتها يطابق بالكود وحده — فقد يكون المحلُّ نفسه صار
فرعين. وفي قائمة موظفيها موظفو اختبار («QA … Test»).

فهذا يطبع، لشركٍة بعينها:
- كلَّ فرع: رمزه واسمه ورقمه الآلي وإحداثيّه وعدد موظفيه.
- **الفروع المحتمل تكرارها لمحٍل واحد**: بالرقم الآلي نفسه، أو بالاسم نفسه، أو
  برقم الفرع نفسه تحت رمزين مختلفين (GUF6 و GU06).
- **موظفي الاختبار** المحتملين (QA · Test · Tester · اختبار · تجريبي).

ولا يحذف ولا يدمج: القراُر لصاحبه بعد أن يرى.

    backend/.venv/Scripts/python.exe backend/scripts/company_audit.py \\
        --api https://hrms-kuwait-production.up.railway.app --company "الاتحاد الخليجي"

الدخول برقمك المدني، وكلمة المرور تُطلب ولا تظهر ولا تُحفظ.
"""
from __future__ import annotations

import argparse
import getpass
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PACI_RE = re.compile(r"الرقم الآلي للعنوان:\s*(\d+)")
QA_RE = re.compile(r"\bQA\b|\btest(er)?\b|اختبار|تجريبي", re.I)


def _norm(s: str | None) -> str:
    from app.arabic import normalize_ar  # noqa: PLC0415

    return normalize_ar(s or "").strip()


def _branch_no(code: str | None) -> str | None:
    m = re.search(r"(\d+)$", code or "")
    return str(int(m.group(1))) if m else None


def audit(branches: list[dict], employees: list[dict]) -> dict:
    """نقٌي بلا شبكة — يُختبَر وحده."""
    per_branch = defaultdict(int)
    for e in employees:
        per_branch[e.get("branch_id")] += 1
    rows = []
    for b in branches:
        m = PACI_RE.search(b.get("address") or "")
        rows.append({**b, "_paci": m.group(1) if m else None,
                     "_employees": per_branch.get(b["id"], 0)})

    groups: list[tuple[str, list[dict]]] = []
    seen_pairs: set[frozenset] = set()

    def _add(reason: str, members: list[dict]):
        key = frozenset(m["id"] for m in members)
        if len(members) > 1 and key not in seen_pairs:
            seen_pairs.add(key)
            groups.append((reason, members))

    by_paci, by_name, by_no = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in rows:
        if r["_paci"]:
            by_paci[r["_paci"]].append(r)
        if r.get("name"):
            by_name[_norm(r["name"])].append(r)
        if _branch_no(r.get("code")):
            by_no[_branch_no(r.get("code"))].append(r)
    for k, m in by_paci.items():
        _add(f"الرقم الآلي نفسه {k}", m)
    for k, m in by_name.items():
        _add("الاسم نفسه", m)
    for k, m in by_no.items():
        prefixes = {re.sub(r"\d+$", "", x.get("code") or "") for x in m}
        if len(prefixes) > 1:
            _add(f"رقم الفرع {k} تحت رمزين مختلفين", m)

    qa = [e for e in employees
          if QA_RE.search(e.get("name") or "") or QA_RE.search(e.get("job_title") or "")]
    unassigned = [e for e in employees if not e.get("branch_id")]
    return {"branches": rows, "duplicates": groups, "qa": qa, "unassigned": unassigned}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="كشف شركة — قراءة فقط")
    ap.add_argument("--api", required=True, help="رابط الموقع")
    ap.add_argument("--company", required=True, help="جزء من اسم الشركة")
    ap.add_argument("--civil-id", help="رقمك المدني للدخول")
    a = ap.parse_args(argv)

    import httpx

    from app.arabic import contains_ar

    civil = a.civil_id or input("الرقم المدني: ").strip()
    pw = getpass.getpass("كلمة المرور (لا تظهر): ")
    base = a.api.rstrip("/") + "/api"
    r = httpx.post(base + "/auth/login", json={"civil_id": civil, "password": pw}, timeout=60)
    if r.status_code != 200:
        raise SystemExit(f"تعذّر الدخول ({r.status_code})")
    s = httpx.Client(headers={"Authorization": f"Bearer {r.json()['access_token']}"}, timeout=120)

    def get(path, **params):
        resp = s.get(base + path, params=params)
        resp.raise_for_status()
        return resp

    companies = [c for c in get("/companies").json() if contains_ar(c.get("name"), a.company)]
    if len(companies) != 1:
        raise SystemExit("الشركات المطابقة: " + ("، ".join(f"#{c['id']} {c['name']}" for c in companies)
                                                  or "لا شيء"))
    co = companies[0]
    branches = [b for b in get("/branches", company_id=co["id"]).json()
                if b.get("company_id") == co["id"]]
    employees, offset = [], 0
    while True:
        page = get("/employees", company_id=co["id"], limit=500, offset=offset).json()
        employees += page
        if len(page) < 500:
            break
        offset += 500
    rep = audit(branches, employees)

    names = {b["id"]: f"{b.get('code') or '—'} {b.get('name')}" for b in branches}
    print(f"=== كشف #{co['id']} {co['name']} — قراءة فقط، لم يُغيَّر شيء ===\n")
    print(f"الفروع ({len(rep['branches'])}):")
    for b in sorted(rep["branches"], key=lambda x: (x.get("code") or "")):
        geo = f"{b['latitude']}, {b['longitude']}" if b.get("latitude") is not None else "بلا إحداثيات"
        print(f"  #{b['id']:<4} {b.get('code') or '—':<6} {b.get('name')} | رقم آلي: {b['_paci'] or '—'}"
              f" | {geo} | موظفون: {b['_employees']}")
    print(f"\nالموظفون: {len(employees)}")
    print("\nفروعٌ يُحتمل أنها المحلُّ نفسه:" if rep["duplicates"] else "\nلا فروع مكررة ظاهرة.")
    for reason, members in rep["duplicates"]:
        print(f"  · {reason}: " + " ↔ ".join(
            f"#{m['id']} {m.get('code') or '—'} «{m.get('name')}» ({m['_employees']} موظف)" for m in members))
    print(f"\nموظفو اختبار محتملون ({len(rep['qa'])}):" if rep["qa"] else "\nلا موظفي اختبار ظاهرين.")
    for e in rep["qa"]:
        print(f"  · #{e['id']} {e.get('employee_no') or '—'} {e.get('name')} — {e.get('job_title') or '—'}"
              f" — فرع: {names.get(e.get('branch_id'), '—')}")
    if rep["unassigned"]:
        print(f"\nموظفون بلا فرع ({len(rep['unassigned'])}): "
              + "، ".join(e.get("name") or "—" for e in rep["unassigned"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
