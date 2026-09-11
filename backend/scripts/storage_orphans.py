# -*- coding: utf-8 -*-
"""سجٌّل بلا ملف — مسٌح متكرِّر لما تَعِد به القاعدة ولا يجده التخزين.

**من أين جاء**: ``P1-01`` في سكيل دورة حياة المستند. تنزيُل مستٍند مولَّد
كان يعود ``410``: الصفّ في القاعدة والملف مفقود. والسبب المعتاد قرٌص
مؤقّت يُمحى مع كل نشرة — والسجلّ يبقى.

وبنيُة التخزين أُصلحت (``AWS-01`` مفتاٌح نسبيّ ومخزٌن واحد، و``S3`` خلفيًّة،
وعلامُة دوام تُقرأ في ``/health/deep``). **وبقي السؤال الذي لا تجيبه
البنية**: أيّ الصفوف القائمة بلا ملف الآن؟

ولا يُعرَف ذلك إلا حين يضغط مستخدٌم فيقع على ``410`` — أي أن أوّل من يكتشف
الضياع هو من يحتاج الورقة. وهذا المسح يسبقه.

**والأعمدة تُشتقّ من الوصف لا تُكتب بيٍد**: كل عمود ينتهي بـ``_path``
يُفحَص. فعموٌد جديد يدخل المسح يوم يُضاف، ولا يُنسى — وقائمٌة مكتوبة بيد
تشيخ بصمت، وهي بعينها علّة ``AWS-01`` التي دعت إلى توحيد التخزين.

يُشغَّل::

    backend/.venv/Scripts/python.exe backend/scripts/storage_orphans.py
    ... --json                # للمراقبة الآلية
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import String, select  # noqa: E402

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.config import settings  # noqa: E402
from app.storage import key_exists  # noqa: E402


def _target() -> str:
    """أيّ قاعدٍة قُرئت — **ويُعلَن دائًما**.

    مساُر SQLite النسبيّ يُحَل على مجلَّد التشغيل، فتقرأ الأداةُ قاعدًة غير
    التي يقصدها مشغّلها وتطبع «صفوٌف بلا ملف: 0». وقع ذلك في أول تشغيل من
    جذر المستودع. وتقريٌر لا يقول ما قرأ لا يُبنى عليه قرار.
    """
    url = str(getattr(settings, "database_url", "") or "—")
    if "@" in url:                      # لا تُطبَع بيانات اعتماد
        url = url.split("@", 1)[0].rsplit(":", 1)[0] + ":***@" + url.split("@", 1)[1]
    return url

#: ما يزن أثقل: ورقٌة رسمية تُفقد ليست كصورٍة شخصية تُفقد.
WEIGHT: dict[str, str] = {
    "documents": "رسمي",
    "request_documents": "رسمي",
    "user_signature_versions": "رسمي",
    "users": "توقيعات وصور",
    "attendance_records": "إثبات حضور",
}


def _looks_like_key(value: str) -> bool:
    """أهذه قيمٌة تصلح مفتاح تخزين؟

    المفتاح ``مجلَّد/اسم.امتداد``. وما لا مجلَّد له ولا امتداد ليس ملفًّا
    غائًبا بل علامٌة نصّية — والتفريق يمنع أن يغرق ضياُع ورقٍة رسمية في
    ضجيج البذرة.
    """
    v = str(value or "").strip().replace("\\", "/")
    return "/" in v and "." in v.rsplit("/", 1)[-1]


def _key_columns() -> list[tuple[object, str]]:
    """كل عمود يحمل مفتاح تخزين — مشتٌق من الوصف لا مكتوٌب بيد."""
    out = []
    for table in models.Base.metadata.tables.values():
        for col in table.columns:
            if col.name.endswith("_path") and isinstance(col.type, String):
                out.append((table, col.name))
    return sorted(out, key=lambda p: (p[0].name, p[1]))


def scan() -> dict:
    report: dict[str, dict] = {}
    db = SessionLocal()
    try:
        for table, column in _key_columns():
            col = table.columns[column]
            entry = report.setdefault(table.name, {
                "weight": WEIGHT.get(table.name, "—"), "columns": {}})
            try:
                rows = db.execute(
                    select(table.columns["id"], col).where(col.is_not(None))
                ).all()
            except Exception as exc:
                # **أداٌة تموت عند أول نقٍص تُخفي ما بعده.** قاعدٌة متأخّرة عن
                # ترحيلها تنقصها جداول، وهي بالضبط الحال التي يُحتاج فيها
                # المسح. فيُذكَر النقص ويمضي الفحص.
                db.rollback()
                entry["columns"][column] = {
                    "unreadable": str(exc).split("\n")[0][:120],
                    "rows_with_key": 0, "missing": 0, "sample": [],
                }
                continue
            # **وقيمٌة ليست مفتاًحا أصًلا ليست ملًفا ضائًعا.**
            #
            # صفوف البذرة تحمل ``(تجريبي)`` في خانة الصورة — لا مجلَّد ولا
            # امتداد. وعدّها «مفقودة» يُغرِق ضياَع ورقٍة رسمية في ثمانيٍ
            # وأربعين ضجّة، فيُقرأ التقرير مرًة ويُهمَل بعدها. والقاعدة §3
            # من الحماية: بيانات الاختبار ليست عطًلا في المنتج.
            keyed = [(rid, v) for rid, v in rows if str(v or "").strip()]
            not_keys = [(rid, v) for rid, v in keyed if not _looks_like_key(v)]
            missing = [(rid, v) for rid, v in keyed
                       if _looks_like_key(v) and not key_exists(v)]
            entry["columns"][column] = {
                "rows_with_key": len(keyed),
                "not_keys": len(not_keys),
                "missing": len(missing),
                "sample": [{"id": r, "key": v} for r, v in missing[:5]],
            }
    finally:
        db.close()
    return report


def main() -> int:
    report = scan()
    total = sum(c["missing"] for t in report.values() for c in t["columns"].values())

    readable = [1 for t in report.values() for c in t["columns"].values()
                if not c.get("unreadable")]
    if report and not readable:
        # وقع هذا فعًلا: شُغِّل من جذر المستودع فوصل قاعدًة فارغة وطبع
        # «صفوٌف بلا ملف: 0». وتقريٌر يطمئن لأنه لم يقرأ شيًئا أسوأ من
        # تقرير يصرخ.
        print("**لم يُقرأ أيّ عمود** — غالًبا قاعدٌة غير التي تقصد. "
              "شغّله من مجلد ‏backend‏ حيث يقع ملف القاعدة.", file=sys.stderr)
        return 2

    if "--json" in sys.argv:
        print(json.dumps({"database": _target(),
                          "missing_total": total, "tables": report},
                         ensure_ascii=False, indent=2))
        return 1 if total else 0

    unreadable = [f"{n}.{c}" for n, b in report.items()
                  for c, v in b["columns"].items() if v.get("unreadable")]
    print(f"القاعدة المقروءة: {_target()}")
    print(f"أعمدُة مفاتيح التخزين المفحوصة: "
          f"{sum(len(t['columns']) for t in report.values())}")
    print(f"صفوٌف بلا ملف: {total}")
    if unreadable:
        print(f"وأعمدٌة تعذّرت قراءتها ({len(unreadable)}): {unreadable}")
    print()
    for name, body in sorted(report.items()):
        for column, c in sorted(body["columns"].items()):
            if c.get("unreadable"):
                print(f"{name}.{column} [{body['weight']}] — **تعذّرت قراءته**: "
                      f"{c['unreadable']}")
                continue
            flag = "  ← مفقود" if c["missing"] else ""
            noise = (f", وليست مفاتيح {c['not_keys']}" if c.get("not_keys") else "")
            print(f"{name}.{column} [{body['weight']}] — "
                  f"بقيمة {c['rows_with_key']}{noise}, مفقود {c['missing']}{flag}")
            for s in c["sample"]:
                print(f"      #{s['id']}  {s['key']}")
    if total:
        print("\n**سجٌّل بلا ملف**: من يطلب هذه الورقة يقع على 410. أعد "
              "توليد ما يُولَّد، واطلب رفع ما يُرفَع — ولا تُترَك صامتة.")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
