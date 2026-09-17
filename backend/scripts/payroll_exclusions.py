# -*- coding: utf-8 -*-
"""من يخرج من المسيّر بحالته لا بمدّة خدمته — تقريرٌ لا تعديل.

**بعد قرار المالك (2026-09-17)** يبقى خارجه من انتهت خدمته بلا تاريخ إنهاء.

**السلسلة المقيسة** (محاكاةٌ على القاعدة مع ``rollback``):

``compute_payroll`` يختار ``Employee.status == "active"`` وحده، ثم يُحسن
تناسبَ الشهر الجزئي بـ``hire_date``/``termination_date``. و
``EMP_STATUSES`` فيها سبعُ حالات، وشاشةُ ملف الموظف تضبط أيًّا منها
(``POST /employees/{id}/status``). فالنتيجة على راتب 2,500:

======================  ==========================
الحالة                  المسيّر
======================  ==========================
نشط                     2500.000
**في إجازة**            **غائبٌ عن المسيّر**
موقوف                   غائب
مستقيل / متقاعد         غائب
======================  ==========================

**وأثقلُها «في إجازة»**: الإجازةُ السنوية مدفوعة، والنظامُ يسجّلها صفوفَ
``Leave`` يقرؤها المسيّرُ فلا يعدّها غيابًا. فالحالةُ تكرارٌ لما يُسجَّل —
وضبطُها يُسقط **راتبَ الشهر كلّه**.

**والشهرُ الأخير بعد التسوية**: ``settle_case`` يكتب ``terminated`` و
``termination_date`` معًا. فإن سُوِّيت الخدمةُ قبل تشغيل مسيّر الشهر
الأخير سقط الموظف منه كلّه — ومنطقُ التناسب الذي كُتب لهذا الشهر بعينه لا
يبلغه (إنهاءٌ في 20/9 على 2,500 = 1,666.667 لا يُدفع). والتسويةُ
(``indemnity + leave_payout``) لا تحمله.

**وقد حُسم**: «في إجازة» و«موقوف» يُدفعان، ومن انتهت خدمته بتاريخٍ يُدفع شهرَه
الأخير (قرار المالك 2026-09-17). والجدولُ أعلاه حالُ ما قبل القرار.

الاستخدام::

    .venv/Scripts/python.exe scripts/payroll_exclusions.py --period 2026-09
    .venv/Scripts/python.exe scripts/payroll_exclusions.py --period 2026-09 --company 1

لا يكتب شيئًا. يُخرج ``0`` دائمًا.
"""
from __future__ import annotations

import argparse
import calendar
import pathlib
import sys
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import or_, select  # noqa: E402

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402

_LABELS = {"vacation": "في إجازة", "suspended": "موقوف", "resigned": "مستقيل",
           "retired": "متقاعد", "terminated": "منتهية خدمته", "archived": "مؤرشف"}


def report(period: str, company_id: int | None = None) -> list[dict]:
    y, m = (int(x) for x in period.split("-"))
    p_start = date(y, m, 1)
    p_end = date(y, m, calendar.monthrange(y, m)[1])
    db = SessionLocal()
    try:
        # **بعد قرار المالك (2026-09-17)**: «في إجازة» و«موقوف» يُدفعان، ومن
        # انتهت خدمته بتاريخٍ يُدفع شهرَه الأخير. فالباقي خارج المسيّر هو من
        # انتهت خدمته **بلا تاريخٍ مُسجَّل** — لا يُتناسَب له.
        from app.deps import PAYABLE_STATUSES
        q = select(models.Employee).where(
            models.Employee.status.notin_(PAYABLE_STATUSES),
            models.Employee.termination_date.is_(None),
            or_(models.Employee.non_payroll.is_(False),
                models.Employee.non_payroll.is_(None)))
        if company_id is not None:
            q = q.where(models.Employee.company_id == company_id)
        out = []
        for e in db.scalars(q).all():
            # عمل في الشهر بمدة خدمته — ومع ذلك خارج المسيّر بحالته.
            if e.hire_date and e.hire_date > p_end:
                continue
            if e.termination_date and e.termination_date < p_start:
                continue
            basic = float(e.basic_salary or 0)
            end = min(p_end, e.termination_date) if e.termination_date else p_end
            start = max(p_start, e.hire_date) if e.hire_date else p_start
            days = (end - start).days + 1
            owed = round(basic / 30 * min(days, 30), 3) if basic else 0.0
            out.append({"id": e.id, "name": e.name, "company_id": e.company_id,
                        "status": e.status, "days": days, "owed": owed,
                        "termination_date": e.termination_date})
        return out
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", required=True, help="YYYY-MM")
    ap.add_argument("--company", type=int, default=None)
    args = ap.parse_args()

    rows = report(args.period, args.company)
    print(f"مسيّر {args.period}: من عمل في الشهر ويخرج منه بحالته — {len(rows)}")
    total = 0.0
    for r in rows:
        total += r["owed"]
        label = _LABELS.get(r["status"], r["status"])
        tail = f" (إنهاء {r['termination_date']})" if r["termination_date"] else ""
        print(f"  #{r['id']:<5} {r['name'][:26]:26} {label:14} "
              f"{r['days']:>2} يوم ≈ {r['owed']:>10.3f} د.ك{tail}")
    if rows:
        print(f"\n  المجموع التقريبي غير المدفوع: {round(total, 3)} د.ك "
              "(أساسيٌّ بمقسوم 30، بلا بدلات ولا إضافي)")
        print("\n— هؤلاء انتهت خدمتُهم بلا تاريخ إنهاء: يُسجَّل التاريخ من ملف الموظف "
              "فيُدفع شهرُهم الأخير بالتناسب.")
    else:
        print("\nلا أحد — كلُّ من عمل في الشهر على المسيّر.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
