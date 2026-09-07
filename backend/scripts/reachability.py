# -*- coding: utf-8 -*-
"""نقطة بلا طريق — أي نقاط `/api` لا يصلها شيء من الواجهة؟

**لماذا سكرِبت لا قياس مرّة**: كُنس النمط مرة واحدة (2026-09-05) فوجد
ثماني نقاط، وبُنيت لها شاشات. ثم أُضيفت نقاط بعدها، وعاد النمط في
واحدة منها على الأقل (`/branches/{id}/supervisors/{uid}`) ولم يكشفها
شيء — لأن القياس كان في رأس من أجراه لا في المستودع.

**وغياب المدخل ليس نقص ميزة بل عطٌل مخفيّ**: ما لا طريق إليه لا
يُستعمَل، وما لا يُستعمَل لا تُكتشف أعطاله. وكلّ شاشة بُنيت في الكنس
الأول كشفت عند بنائها عيًبا أعمق من غياب الواجهة نفسه.

**والمطابقة على المقاطع الثابتة**: مسار الواجهة يُكتب قالًبا
(``/employees/${id}/timeline``) فلا يطابق نصُّه نصَّ الخادم. فيُقاس أن
مقاطعه الثابتة تظهر بالترتيب داخل نصّ واحد في مصدر الواجهة.

الاستعمال::

    python -m scripts.reachability            # الملخّص وغير الموصول
    python -m scripts.reachability --all      # كل النقاط وحكم كلٍّ
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONT = ROOT / "frontend" / "src"

#: نقاط تشغيلية بطبعها: تُستدعى من سطر أوامر أو مهمة مجدولة أو شاشة
#: الكشك، لا من واجهة الموظّف. وإدراجها هنا **قرار مكتوب** لا صمت.
OPERATIONAL = (
    "/break-glass", "/run-digest", "/backfill", "/kiosk", "/healthz",
    "/health", "/manifest", "/metrics", "/openapi", "/docs", "/redoc",
    "/seed", "/erase", "/smoke", "/__",
)


def _files() -> list[str]:
    """نصوص ملفات الواجهة، كلٌّ على حدة — الملفات مقسومة بالشاشات."""
    parts = []
    for p in FRONT.rglob("*"):
        if p.suffix in (".ts", ".tsx", ".js", ".jsx") and p.is_file():
            parts.append(p.read_text(encoding="utf-8", errors="ignore"))
    return parts


def _segments(path: str) -> list[str]:
    """المقاطع الثابتة وحدها — المتغيّرة تُكتب قوالب في الواجهة."""
    return [s for s in path.strip("/").split("/") if s and not s.startswith("{")]


def _ordered(segs: list[str], blob: str) -> bool:
    """المقاطع بالترتيب داخل نصٍّ واحد — يسمح بـ``${...}`` بينها."""
    pattern = r"[^\n\"'`]*".join(re.escape(s) for s in segs)
    return re.search(pattern, blob) is not None


def _reachable(path: str, blob: str, files: list[str]) -> bool:
    """هل يصل الواجهةَ طريٌق إلى هذه النقطة؟

    **والمطابقة على مستويين**: المسار قد يُبنى من قطعتين
    (``const ep = "gov-contract/generate"`` ثم ``/employees/${id}/${ep}``)
    فلا تظهر مقاطعه كلّها في نصٍّ واحد. فيُقبل أيًضا أن تظهر **كلّها داخل
    ملف واحد** — الملفات هنا مقسومة بالشاشات، فاجتماعها في واحد قرينة
    كافية للفرز البشري بعده.

    **والنافذة محدودة عمًدا**: قبول ظهور المقاطع في أي موضع من الملف
    أخفى أخطر ما وجده هذا المسح — شاشة الرواتب فيها ``payroll`` و
    ``runs``، وكلمة ``approve`` في ملف آخر، فبدا المسار موصوًلا وهو
    مقطوع. فتُشترط المجاورة: مقاطع نداء واحد يكتبها المبرمج متلاصقة.
    """
    segs = _segments(path)
    if not segs:
        return True
    if _ordered(segs, blob):
        return True
    near = r".{0,400}?".join(re.escape(s) for s in segs)
    return any(re.search(near, text, re.S) for text in files)


def scan() -> tuple[list[tuple[str, str]], list[tuple[str, str]], int]:
    sys.path.insert(0, str(ROOT / "backend"))
    from app.main import app

    seen: set[tuple[str, str]] = set()
    for r in app.routes:
        path = getattr(r, "path", "")
        if not path.startswith("/api"):
            continue
        for method in sorted(getattr(r, "methods", set()) or set()):
            if method in ("HEAD", "OPTIONS"):
                continue
            seen.add((method, path))

    files = _files()
    blob = "\n".join(files)
    unreachable, operational = [], []
    for method, path in sorted(seen):
        rest = path[len("/api"):]
        if any(op in rest for op in OPERATIONAL):
            operational.append((method, path))
        elif not _reachable(rest, blob, files):
            unreachable.append((method, path))
    return unreachable, operational, len(seen)


def main() -> int:
    ap = argparse.ArgumentParser(description="نقطة بلا طريق")
    ap.add_argument("--all", action="store_true", help="يطبع كل النقاط")
    args = ap.parse_args()

    unreachable, operational, total = scan()
    print(f"نقاط /api: {total} · تشغيلية بطبعها: {len(operational)} · "
          f"بلا طريق من الواجهة: {len(unreachable)}")
    if args.all:
        print("\n— تشغيلية (مستثناة بقرار مكتوب):")
        for m, p in operational:
            print(f"  {m:6} {p}")
    if unreachable:
        print("\n— بلا طريق: كل واحدة إمّا عطل مخفيّ أو استثناء يُكتب في OPERATIONAL")
        for m, p in unreachable:
            print(f"  {m:6} {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
