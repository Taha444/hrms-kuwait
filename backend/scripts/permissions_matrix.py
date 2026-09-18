# -*- coding: utf-8 -*-
"""مصفوفة الصلاحيات (DLV-46) — تُولَّد من الشيفرة، لا تُكتب باليد.

مصفوفٌة تُكتب باليد تشيخ مع أوّل صلاحيٍة تُضاف أو نقطٍة تُحرس: فتُقرأ في
التسليم على أنها وصُف النظام وهي وصُف ماضيه. فهذه تُقرأ من مصدرها:

- ``permissions.ROLE_DEFAULT_PERMS`` — ما يحمله كل دور افتراضيًا.
- ``permissions.PERMISSIONS`` — اسُم كل صلاحية بالعربية.
- مسارات التطبيق نفسها — أيُّ نقطٍة تحرسها أيُّ صلاحية أو أيُّ قيِد دور.

يُشغَّل::

    backend/.venv/Scripts/python.exe backend/scripts/permissions_matrix.py          # يكتب
    backend/.venv/Scripts/python.exe backend/scripts/permissions_matrix.py --check  # يتحقّق

ويحرسه ``tests/test_zzz_permissions_matrix_doc.py``: الوثيقُة تطابق الشيفرة
أو يسقط — فمن يضيف صلاحيًة يُعيد التوليد.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

OUT = ROOT / "docs" / "PERMISSIONS_MATRIX.md"

#: قيوُد دوٍر لا صلاحية — تُسمّى باسمها في الوثيقة.
ROLE_GATES = {
    "require_super_admin": "الإدارة العليا التقنية وحدها (super_admin)",
    "require_owner_or_admin": "صاحب الشركات (ومعه super_admin)",
    "require_any_perm_or_owner": "صاحب الشركات أو من يملك «إدارة المستخدمين»",
}


def _gates(route) -> list[str]:
    """أقفال النقطة: ``perm:X`` أو ``any:X|Y`` أو اسُم قيِد الدور."""
    out: list[str] = []
    dep = getattr(route, "dependant", None)
    stack = list(dep.dependencies) if dep else []
    while stack:
        d = stack.pop()
        fn = d.call
        name = getattr(fn, "__name__", "")
        names = getattr(getattr(fn, "__code__", None), "co_freevars", ())
        cells = {}
        for n, c in zip(names, getattr(fn, "__closure__", None) or ()):
            try:
                cells[n] = c.cell_contents
            except ValueError:
                pass
        if isinstance(cells.get("perm"), str):
            out.append(f"perm:{cells['perm']}")
        elif isinstance(cells.get("perms"), tuple):
            out.append("any:" + "|".join(cells["perms"]))
        elif name in ROLE_GATES:
            out.append(name)
        stack.extend(d.dependencies)
    return sorted(set(out))


def render() -> str:
    from app import permissions as P
    from app.main import app

    roles = [r for r in P.ROLE_DEFAULT_PERMS if r != "super_admin"] + ["super_admin"]
    label = getattr(P, "ROLE_LABEL_AR", {})
    perms = sorted(P.PERMISSIONS)

    by_perm: dict[str, list[str]] = defaultdict(list)
    by_role_gate: dict[str, list[str]] = defaultdict(list)
    for rt in app.routes:
        path = getattr(rt, "path", "")
        if not path.startswith("/api/"):
            continue
        for m in sorted(getattr(rt, "methods", None) or ()):
            if m in ("HEAD", "OPTIONS"):
                continue
            for g in _gates(rt):
                line = f"`{m} {path}`"
                if g.startswith("perm:"):
                    by_perm[g[5:]].append(line)
                elif g.startswith("any:"):
                    for p in g[4:].split("|"):
                        by_perm[p].append(line + " (أيٌّ منها)")
                else:
                    by_role_gate[g].append(line)

    L: list[str] = []
    L.append("# مصفوفة الصلاحيات (DLV-46)")
    L.append("")
    L.append("> **مولَّدة من الشيفرة** بـ`backend/scripts/permissions_matrix.py` — لا تُحرَّر باليد.")
    L.append("> ويحرسها اختبارٌ يسقط إن خالفت الشيفرة: من يغيّر صلاحيةً يُعيد التوليد.")
    L.append("")
    L.append("الصلاحيات أدناه **افتراضية لكل دور**؛ ويمكن إسناد صلاحيةٍ إضافية لمستخدمٍ")
    L.append("بعينه من شاشة المستخدمين. والعزل بين الشركات ونطاق الفروع يُفرضان فوقها على الخادم.")
    L.append("")
    L.append("## 1. الأدوار × الصلاحيات")
    L.append("")
    L.append("| الصلاحية | " + " | ".join(label.get(r, r) for r in roles) + " |")
    L.append("|---|" + "|".join(":-:" for _ in roles) + "|")
    for p in perms:
        row = [("✓" if P.has_permission(r, set(), p) else "") for r in roles]
        L.append(f"| {P.PERMISSIONS[p]} (`{p}`) | " + " | ".join(row) + " |")
    L.append("")
    L.append("## 2. قواعد الأدوار الخاصة")
    L.append("")
    L.append("- **التقديم نيابةً عن موظف:** " + "، ".join(
        label.get(r, r) for r in sorted(P.ON_BEHALF_ROLES)))
    L.append("- **العابرون للشركات:** " + "، ".join(
        label.get(r, r) for r in sorted(P.CROSS_COMPANY_ROLES)))
    if hasattr(P, "TWOFA_REQUIRED_ROLES"):
        L.append("- **التحقق الثنائي إلزامي:** " + "، ".join(
            label.get(r, r) for r in sorted(P.TWOFA_REQUIRED_ROLES)))
    L.append("- **لا اعتماد ذاتي لأي دور** (قرار المالك 2026-09-17)، ومنه super_admin.")
    L.append("- **مسؤول الفرع** مقيَّدٌ بفروعه على الخادم في القوائم والبحث والحضور والمهام.")
    L.append("")
    L.append("## 3. النقاط المقيَّدة بدورٍ لا بصلاحية")
    L.append("")
    for g, title in ROLE_GATES.items():
        eps = sorted(set(by_role_gate.get(g, [])))
        if not eps:
            continue
        L.append(f"### {title}")
        L.append("")
        L.extend(f"- {e}" for e in eps)
        L.append("")
    L.append("## 4. النقاط التي تحرسها كل صلاحية")
    L.append("")
    for p in perms:
        eps = sorted(set(by_perm.get(p, [])))
        L.append(f"### {P.PERMISSIONS[p]} (`{p}`)")
        L.append("")
        if eps:
            L.extend(f"- {e}" for e in eps)
        else:
            L.append("- — لا نقطة تحرسها مباشرةً (تُقرأ داخل النقاط أو في الواجهة).")
        L.append("")
    return "\n".join(L).rstrip() + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur != text:
            print("PERMISSIONS_MATRIX.md لا يطابق الشيفرة — شغّل السكربت بلا --check")
            return 1
        print("ok")
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(f"كُتب {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
