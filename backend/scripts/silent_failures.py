# -*- coding: utf-8 -*-
"""مستثنًى يُلتقط فيُبتلع — أداُة مراجعٍة لا حارٌس يفرض عرًفا.

**لماذا أداٌة لا اختبار**: كُنِست ثلاٌث وأربعون معالجًة عريضة
(``except Exception``) في ``app/`` ولم يكن فيها عطٌل واحد — كلُّها تراجٌع
مقصود بشرحه. فحاٌرس يُفشِل السويت على شيفرٍة سليمة حاٌرس يُحذَف بعد
أسبوعين، ويذهب معه ما كان يحرسه.

فالكنُس يُطبَع لمن يراجع، ويرتّب المواضع بما يقرّب الأخطر: **معالجٌة
عريضة، لا تُبلِّغ بشيء، ولا تُعلِّل**.

وثلاثُة أشياء تُعَدّ بلاًغا ولا يُخطَأ فيها بعد اليوم:

- سجٌل أو رفٌع أو تدقيق.
- **إعادُة فشٍل يقرؤه النداء**: ``return False, "…"`` تقرير لا ابتلاع، وهو
  ما أنذر كنسي كاذًبا فيه أوَّل مرة.
- **حمولٌة تقول «تعذّر»**: فحوُص الصحة تُسنِد قيمًة بديلة وتُخرِجها، فالقارئ
  يرى الفشل في الجواب.

والمستثنى **الضيّق** (``except ValueError``) يُستثنى ببنيته: النوُع هو
شرُحه.

الاستخدام::

    .venv/Scripts/python.exe scripts/silent_failures.py

يُخرج ``0`` دائًما — أداُة نظٍر لا حكم.
"""
from __future__ import annotations

import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = ROOT / "app"

BROAD = ("Exception", "BaseException", "bare")

#: ما يجعل المعالجَة مُبلِّغة.
REPORTS = ("logger", "logging", "log.", "print(", "audit(", "raise",
           "capture", "return False", "return None", "failed.append",
           "errors.append", "return {", "detail=")

AR = re.compile(r"[؀-ۿ]")


def scan() -> list[dict]:
    out = []
    for p in sorted(APP.rglob("*.py")):
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines()
        for h in ast.walk(ast.parse(text)):
            if not isinstance(h, ast.ExceptHandler):
                continue
            t = h.type
            name = (getattr(t, "id", None) or getattr(t, "attr", None)
                    or ("tuple" if isinstance(t, ast.Tuple) else "bare"))
            if name not in BROAD:
                continue
            lo, hi = h.lineno, getattr(h, "end_lineno", h.lineno)
            body = "\n".join(lines[lo - 1:hi])
            ctx = "\n".join(lines[max(0, lo - 4):hi])
            out.append({
                "file": str(p.relative_to(ROOT).as_posix()),
                "line": lo,
                "reports": any(k in body for k in REPORTS),
                "explained": ("#" in body
                              or ("#" in ctx and bool(AR.search(ctx)))
                              or ('"""' in ctx and bool(AR.search(ctx)))),
                "body": body.strip().splitlines()[:3],
            })
    return out


def main() -> int:
    rows = scan()
    mute = [r for r in rows if not r["reports"] and not r["explained"]]
    quiet = [r for r in rows if not r["reports"] and r["explained"]]
    loud = [r for r in rows if r["reports"]]

    print(f"معالجاٌت عريضة: {len(rows)}")
    print(f"  تُبلِّغ (سجٌل · رفٌع · إعادُة فشٍل · حمولٌة تقول «تعذّر»): {len(loud)}")
    print(f"  تسكت بعلٍّة مكتوبة: {len(quiet)}")
    print(f"  **تسكت بلا بلاٍغ ولا علّة**: {len(mute)}")

    if mute:
        print("\nتُراجَع أوًّلا:")
        for r in mute:
            print(f"\n  {r['file']}:{r['line']}")
            for one in r["body"]:
                print("     ", one)
    else:
        print("\nلا معالجًة تسكت بلا بلاٍغ ولا علّة.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
