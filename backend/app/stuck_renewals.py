# -*- coding: utf-8 -*-
"""RNW-D2 — حصر المعاملات العالقة في القفلة المزدوجة.

**الأداة تقرأ ولا تكتب.** عمًدا: التحرير يتمّ من داخل النظام على يد
المندوب، بحسابه، فيُسجَّل في التدقيق باسمه وتُرسَل إشعاراته. سكربت يعدّل
الحالة مباشرة في القاعدة ينجز الشيء نفسه ظاهرًيا ويترك معاملة تغيّرت بلا
فاعل ولا سبب — وهذا أسوأ من بقائها عالقة.

فما تفعله هذه: تقول **كم** و**أيّها** و**ما الناقص في كلٍّ**، ليُعرف حجم
العمل قبل بدئه. ولو كان العدد صفًرا فالمنع وحده كفى ولا إنقاذ مطلوب.

التشغيل::

    python -m app.stuck_renewals
    python -m app.stuck_renewals --company 1
"""
from __future__ import annotations

import sys

from sqlalchemy import select

from . import models, renewal as R
from .database import SessionLocal
from .routers.renewals import GOV_DATA_FIELDS


def find_stuck(db, company_id: int | None = None) -> list[dict]:
    """المعاملات في ``pending_hr_verify`` ينقصها شيء من بيانات الحكومة."""
    q = select(models.ResidencyRenewal).where(
        models.ResidencyRenewal.status == R.PENDING_HR_VERIFY)
    if company_id:
        q = q.where(models.ResidencyRenewal.company_id == company_id)

    out = []
    for rn in db.scalars(q).all():
        missing = [label for key, label in GOV_DATA_FIELDS.items()
                   if not getattr(rn, key, None)]
        if not missing:
            continue                       # سليمة — تنتظر HR فحسب
        emp = db.get(models.Employee, rn.employee_id)
        out.append({
            "id": rn.id,
            "employee": emp.name if emp else f"#{rn.employee_id}",
            "company_id": rn.company_id,
            "updated_at": getattr(rn, "updated_at", None),
            "missing": missing,
        })
    return out


def main() -> int:
    args = sys.argv[1:]
    company_id = None
    if "--company" in args:
        i = args.index("--company")
        if i + 1 < len(args):
            company_id = int(args[i + 1])

    db = SessionLocal()
    try:
        rows = find_stuck(db, company_id)
    finally:
        db.close()

    if not rows:
        print("لا معاملات عالقة — المنع وحده كافٍ، ولا إنقاذ مطلوب.")
        return 0

    print("=" * 72)
    print(f"عالقة في «بانتظار تحقّق HR» بلا بيانات حكومة: {len(rows)}")
    print("=" * 72)
    for r in rows:
        print(f"  #{r['id']:<6} {r['employee']:<28} ينقصها: {'، '.join(r['missing'])}")
    print("=" * 72)
    print("\nالتحرير من داخل النظام: يفتح المندوب المعاملة ويُدخل بيانات")
    print("المعاملة الحكومية من مرحلتها الحالية، ثم يغلقها HR.")
    print("لا تُعدَّل الحالة في القاعدة مباشرة — تتغيّر بلا فاعل ولا سبب.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
