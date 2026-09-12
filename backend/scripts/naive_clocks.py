# -*- coding: utf-8 -*-
"""لحظٌة عاريٌة من المنطقة — أداُة مراجعٍة لعطٍل يعمل في بيئٍة ويصمت في أخرى.

**القياس**: ثالثُة أعراٍف لـ«الآن» تتعايش في النظام —

1. ``datetime.now()`` — عاريٌة بتوقيت **المضيف**.
2. ``datetime.now(timezone.utc)`` — واعيٌة بـUTC.
3. ``clock.now()`` — واعيٌة بتوقيت الكويت.

وأحَد عشر موضًعا يقرأ المحفوَظ **ويختمه UTC صراحًة**
(``replace(tzinfo=timezone.utc)``) — أي أن النظام كلَّه يفترض أن المخزون
UTC. والافتراُض صحيٌح ما دام المضيف UTC (وRailway منه)، **ويكذب على مضيٍف
كويتي بثالث ساعات**.

**ولا يُمسَك هذا الشكل باختبار**: السويُت تجري في بيئٍة واحدة، فالعرفان
يتّفقان فيها ويختلفان في غيرها. فيُمسَك بقراءة الشيفرة.

**ولا يُجعَل حارًسا يُفشِل السويت**: ستَّة عشر ملًفا تكتب عاريًة، وأكثرُها
لا أثر له (اسُم ملٍّف يُفرَّد بـ``timestamp()``). وحاٌرس يسقط على ستَّة
عشر موضًعا حاٌرس يُحذَف. فهذه أداٌة تُطبِع وتُرتّب، والقاعدُة المعلَنة في
``app/clock.py``.

الاستخدام::

    .venv/Scripts/python.exe scripts/naive_clocks.py
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = ROOT / "app"

NAIVE = re.compile(r"datetime\.now\(\s*\)|datetime\.utcnow\(\)")
AWARE = re.compile(r"datetime\.now\(\s*timezone\.utc\s*\)")

#: ما ليس لحظًة مخزَّنة: اسٌم يُفرَّد، أو فرٌق يُحسَب في السطر نفسه.
NOT_STORED = ("timestamp()", "strftime", "isoformat()", "fname", "filename")


def scan() -> dict[str, list[tuple[int, str, bool]]]:
    out: dict[str, list[tuple[int, str, bool]]] = collections.defaultdict(list)
    for p in sorted(APP.rglob("*.py")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if s.startswith("#"):
                continue
            if NAIVE.search(s) and not AWARE.search(s):
                stored = not any(k in s for k in NOT_STORED)
                out[str(p.relative_to(ROOT).as_posix())].append((i, s[:90], stored))
    return out


def aware_files() -> set[str]:
    return {str(p.relative_to(ROOT).as_posix()) for p in APP.rglob("*.py")
            if AWARE.search(p.read_text(encoding="utf-8"))}


def main() -> int:
    naive = scan()
    aware = aware_files()

    stored = {f: [r for r in rows if r[2]] for f, rows in naive.items()}
    stored = {f: rows for f, rows in stored.items() if rows}
    mixed = sorted(set(stored) & aware)

    total = sum(len(r) for r in naive.values())
    print(f"مواضُع «الآن» العارية: {total} في {len(naive)} ملًفا")
    print(f"  منها لحظاٌت **مخزَّنة**: {sum(len(r) for r in stored.values())}")
    print(f"  ملفاٌت تكتب الواعيَة أيًضا: {len(aware)}")
    print(f"\n**الأخطر — ملٌّف يكتب العرفين معًا في لحظاٍت مخزَّنة**: {len(mixed)}")
    for f in mixed:
        print(f"\n  {f}")
        for ln, text, _ in stored[f]:
            print(f"     {ln}: {text}")

    rest = sorted(set(stored) - set(mixed))
    if rest:
        print(f"\nلحظاٌت مخزَّنة عاريٌة في ملفاٍت لا تخلط ({len(rest)}):")
        for f in rest:
            print(f"  {f}: {[ln for ln, _, _ in stored[f]]}")

    print("\nالقاعدُة المعلَنة في app/clock.py: تُخزَّن بـUTC، وتُعرَض بتوقيت الكويت.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
