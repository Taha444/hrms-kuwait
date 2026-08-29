# -*- coding: utf-8 -*-
"""SIG-H3 — أي نقاط الـAPI لا تستدعيها الواجهة؟

**لماذا هذا الجرد**: بلاغ قال إن ``/me/signature/history`` «يرجع فارًغا».
والتحقيق أظهر أن النقطة سليمة وأن الواجهة **لا تستدعيها أصًلا**. وبناء
ميزة لنقطة مهجورة شغل ضائع، وحذف نقطة مستعمَلة كسر — والفرق بينهما لا
يُعرف بالحدس.

**والجرد دليل لا حكم.** غياب الاسم من ملفات الواجهة لا يعني الهجر:
- نقاط يستدعيها التكامل الخارجي أو الأدوات أو الاختبارات
- مسارات تُبنى ديناميكًيا (``api.get(`/x/${id}/y`)``) فلا يطابقها نصّ ثابت
- نقاط تُقصد للمستقبل القريب

فالمخرَج قائمة **مرشَّحين للفحص**، تُقرأ ويُقرَّر فيها واحدة واحدة.

التشغيل::

    python -m app.endpoint_inventory
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"

#: بادئة المسارات في الواجهة: ``api`` مضبوط على ``/api`` فالنداءات بلا هذه.
API_PREFIX = "/api"


def _frontend_text() -> str:
    parts = []
    for f in FRONTEND.rglob("*"):
        if f.suffix in (".ts", ".tsx", ".js", ".jsx") and f.is_file():
            try:
                parts.append(f.read_text(encoding="utf-8"))
            except OSError:
                continue
    return "\n".join(parts)


def _segments(path: str) -> list[str]:
    """أجزاء المسار الثابتة — ما لا يتغيّر بمعرّف.

    ``/renewals/{rid}/finalize`` ← ``['renewals', 'finalize']``. والواجهة
    تكتبها داخل قالب نصّي، فالبحث عن الجزء الثابت هو ما يطابقها.
    """
    return [s for s in path.strip("/").split("/")
            if s and not s.startswith("{")]


def unused_endpoints() -> list[dict]:
    from .main import app

    text = _frontend_text()
    out = []
    for route in app.routes:
        path = getattr(route, "path", "")
        methods = sorted(getattr(route, "methods", set()) - {"HEAD", "OPTIONS"})
        if not path.startswith(API_PREFIX) or not methods:
            continue
        rel = path[len(API_PREFIX):]
        segs = _segments(rel)
        if not segs:
            continue
        # يُعدّ مستعمًلا إن ظهرت كل أجزائه الثابتة متتالية في نصّ الواجهة
        pattern = ".{0,80}".join(re.escape(s) for s in segs)
        if re.search(pattern, text, re.S):
            continue
        out.append({"path": path, "methods": methods})
    return out


def main() -> int:
    rows = unused_endpoints()
    print("=" * 72)
    print(f"نقاط لم يُعثر لها على استدعاء في الواجهة: {len(rows)}")
    print("=" * 72)
    for r in rows:
        print(f"  {','.join(r['methods']):<12} {r['path']}")
    print("=" * 72)
    print("\nهذه **مرشَّحون للفحص** لا قائمة حذف: قد يستدعيها تكامل خارجي")
    print("أو أداة أو اختبار، وقد تُبنى مساراتها ديناميكًيا فلا يطابقها نصّ.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
