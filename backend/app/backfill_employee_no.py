# -*- coding: utf-8 -*-
"""P7-29 — تعبئة الأرقام الوظيفية الناقصة، **بفحص قبل الكتابة**.

المنطق موجود (:func:`app.employee_no.backfill_missing`) والناقص كان
الطريق إليه: دالة يناديها من يعرفها ليست أداة تشغيل. ومن يحتاجها على
بيئة عميل لا يفتح مفسّر بايثون ليكتب استدعاًء.

**والفحص قبل الكتابة ليس تزيًُّنا**: الرقم الوظيفي يدخل العقود والمسيّر
والمراسلات، وتوليده لثمانية وعشرين موظًفا بأمر واحد بلا أن يرى أحد ما
سيُكتب هو ما يُصعِّب التراجع. فالتشغيل الافتراضي **قراءة**، والكتابة
تحتاج ``--apply`` صريحة.

التشغيل::

    python -m app.backfill_employee_no                 # فحص فقط
    python -m app.backfill_employee_no --company 1
    python -m app.backfill_employee_no --apply
"""
from __future__ import annotations

import sys

from sqlalchemy import select

from . import employee_no, models
from .database import SessionLocal


def preview(db, company_id: int | None = None) -> list[dict]:
    """من سيأخذ رقًما، وما الرقم — بلا كتابة.

    يُولَّد الرقم في الذاكرة ثم يُتراجَع عنه: العرض يجب أن يُري ما سيقع
    فعًلا، لا تقريًبا له. وقاعدة توليد تختلف بين المعاينة والتطبيق تجعل
    المعاينة عديمة القيمة.
    """
    q = select(models.Employee).where(models.Employee.employee_no.is_(None))
    if company_id is not None:
        q = q.where(models.Employee.company_id == company_id)

    rows = []
    for emp in db.scalars(q).all():
        code = employee_no.generate(db, emp)
        rows.append({"id": emp.id, "name": emp.name,
                     "company_id": emp.company_id, "employee_no": code})
    db.rollback()                      # معاينة لا كتابة
    return rows


def main() -> int:
    args = sys.argv[1:]
    company_id = None
    if "--company" in args:
        i = args.index("--company")
        if i + 1 < len(args):
            company_id = int(args[i + 1])
    apply_changes = "--apply" in args

    db = SessionLocal()
    try:
        rows = preview(db, company_id)
        if not rows:
            print("لا موظف بلا رقم وظيفي — لا شيء يُعبَّأ.")
            return 0

        print("=" * 66)
        print(f"موظفون بلا رقم وظيفي: {len(rows)}")
        print("=" * 66)
        for r in rows:
            print(f"  #{r['id']:<6} {r['name'][:28]:<30} → {r['employee_no']}")
        print("=" * 66)

        if not apply_changes:
            print("\nفحص فقط — لم يتغيّر شيء. أعد التشغيل مع --apply للكتابة.")
            return 0

        made = employee_no.backfill_missing(db, company_id)
        print(f"\nكُتب رقم لـ{made} موظًفا.")
        # الأرقام تدخل العقود والمسيّر: من يراجع لاحًقا يحتاج أن يعرف
        # أنها وُلّدت دفعًة لا أنها أُدخلت واحًدا واحًدا.
        print("سُجّلت دفعة واحدة — راجعها قبل إصدار أي مستند يحملها.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
