# -*- coding: utf-8 -*-
"""شرٌط لا يصدق لأحد — مسٌح متكرِّر لأقفال الواجهة بلا مفاتيح.

**من أين جاء**: كتلة التوقيع في شاشة الطلب كانت محروسة بـ``can(
"approve_request")``، ولا يحمل تلك الصلاحية **أيّ دور** إلا ``super_admin``.
فتصل الاستقالة مرحلة التوقيع ولا يملك أحٌد في الشركة زًرا يتمّها — والقاعدة
المعلَنة للمالك تمنع منح ``super_admin`` أصًلا. أي قفٌل لا مفتاح له.

ولم يُمسك ذلك باختبار لأن اختبارات المسار تنادي الخادم مباشًرة: تمرّ من
باب لا يفتحه أحٌد من الشاشة.

**ما يقيسه**: كل ``can("X")`` في الواجهة، ثم:

- ``DEAD``    — لا دور افتراضي يحملها ولا هي في كتالوج الصلاحيات: قفٌل بلا مفتاح.
- ``GRANT``   — ليست في أي دور افتراضي لكنها تُسنَد يدًوا: تعمل بعد إسناٍد واعٍ.
- ``OK``      — يحملها دوٌر واحد على الأقل افتراضًيا.

يُشغَّل::

    backend/.venv/Scripts/python.exe backend/scripts/ui_permission_gaps.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import permissions as P  # noqa: E402

CAN_RE = re.compile(r'\bcan\(\s*["\']([a-z0-9_]+)["\']')


def main() -> int:
    src = ROOT / "frontend" / "src"
    uses: dict[str, list[str]] = {}
    for f in sorted(src.rglob("*.tsx")) + sorted(src.rglob("*.ts")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        # التعليقات تذكر الصلاحيات المهجورة لتشرحها — فلا تُعدّ استعماًلا.
        #
        # وتعليقات JSX متعدّدة الأسطر لا تبدأ أسطُرها بعلامة: يبدأ التعليق
        # بـ``{/*`` ثم تتلوه أسطٌر نًصّا محًضا. ففحص بداية السطر وحده كان
        # يعدّ شرح العطل عطًلا قائًما — أي أن أداة القياس تُبلّغ عن نفسها.
        in_block = False
        for line_no, line in enumerate(text.splitlines(), 1):
            stripped = line.lstrip()
            if in_block:
                if "*/" in line:
                    in_block = False
                    line = line.split("*/", 1)[1]
                else:
                    continue
            if "/*" in line and "*/" not in line.split("/*", 1)[1]:
                in_block = True
                line = line.split("/*", 1)[0]
            line = re.sub(r"/\*.*?\*/", "", line)
            if stripped.startswith("//"):
                continue
            line = line.split("//", 1)[0]
            for perm in CAN_RE.findall(line):
                uses.setdefault(perm, []).append(
                    f"{f.relative_to(ROOT).as_posix()}:{line_no}")

    holders: dict[str, list[str]] = {}
    for role, perms in P.ROLE_DEFAULT_PERMS.items():
        if role == "super_admin":
            continue  # المالك يمنع منحه، فلا يُحتسب مفتاًحا
        for perm in perms:
            holders.setdefault(perm, []).append(role)

    catalog = set(P._ALL)
    dead, grant = [], []
    for perm in sorted(uses):
        if holders.get(perm):
            continue
        (grant if perm in catalog else dead).append(perm)

    print(f"صلاحيات مستعمَلة في الواجهة: {len(uses)}")
    print(f"OK — يحملها دوٌر افتراضي: {len(uses) - len(dead) - len(grant)}\n")

    for label, group, note in (
        ("DEAD — قفٌل بلا مفتاح", dead, "ليست في أي دور ولا في الكتالوج"),
        ("GRANT — تحتاج إسناًدا يدوًيا", grant, "في الكتالوج ولا يحملها دوٌر افتراضي"),
    ):
        if not group:
            continue
        print(f"{label} ({len(group)}) — {note}")
        for perm in group:
            print(f"  {perm}")
            for where in uses[perm][:6]:
                print(f"      {where}")
        print()

    return 1 if dead else 0


if __name__ == "__main__":
    raise SystemExit(main())
