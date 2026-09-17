# -*- coding: utf-8 -*-
"""انصراٌف مَنسيٌّ يُدفَع إضافًيا — تقريٌر لا تعديل.

**السلسلُة المقيسة**، من أوّلها إلى المال:

1. الموظُف يبصم حضوًرا وينسى الانصراف، فيبقى السجلُّ مفتوًحا.
2. ومساُر الانصراف **بلا قيد تاريخ**: يأخذ أحدَث سجٍّل مفتوٍح أيًّا كان يومُه
   ويُغلقه بـ``now``. فمن نسي أمس يبصم انصراًفا اليوم فتُغلَق مدٌّة تمتدّ
   أربًعا وعشرين ساعًة أو أكثر. (وهذا نفسه يمنع الحجَب الأبدي — فالموظُف
   ليس محجوًبا، لكنّ الرقَم يتضخّم.)
3. ``_finalize_out`` يحسب ``worked_minutes`` فرَق اللحظتين **بلا سقف**، ثم
   ``overtime_minutes = worked − shift_minutes``.
4. و``payroll`` يدفعه::

       overtime_pay = hourly * OVERTIME_RATE * (overtime_minutes / 60)
       gross = earned_basic + overtime_pay + allowances

**فنسياٌن واحٌد يُغلَق بعد أربٍع وعشرين ساعًة يدفع خمَس عشرة ساعَة إضافّي.**
وعلى متوسط الراتب في هذه القاعدة (850.385 د.ك): الساعُة الإضافية 4.429
د.ك، فالسجلُّ الواحد **66.436 د.ك**؛ وبعد ثمانٍ وأربعين ساعًة 172.734 د.ك.

**والعلاُج مُعلٌَن ولم يُبنَ**: ``Branch.auto_checkout_minutes`` — عمٌود على
الفرع، افتراضُه خمَس عشرة دقيقة، يقبله ``BranchIn`` و``BranchUpdate``،
**ولا يقرؤه شيٌء في النظام** ولا تعرضه الواجهة. فالمخطَُّط يعِد بانصراٍف
تلقائيٍّ لا يقع.

**والعلاُج اليدويُّ بلا باب**: ``PUT /attendance/{id}/correct`` موجوٌد
ويصحّح ``check_out_at`` بسبٍب موثَّق — **ولا شاشَة تناديه**.

**ولا يُصلَح هذا هنا**: سقُف الدقائق يغيّر رقًما يُدفَع، والقاعدُة أن
Payroll لا يُمسّ بلا اعتماد. فيُقاس ويوضَع الرقُم أمام صاحب القرار.

**وقد حُسم** (قرار المالك 2026-09-17): الإضافيُّ لا يُدفع إلا بطلب «عمل إضافي»
مكتمل، والمنسيُّ يُغلق عند نهاية الوردية + ``auto_checkout_minutes``. فهذا
التقرير يقيس الآن السجلّاتِ التاريخية وما سُجّل قبل القرار.

الاستخدام::

    .venv/Scripts/python.exe scripts/overtime_exposure.py
    .venv/Scripts/python.exe scripts/overtime_exposure.py --company 1

لا يكتب شيًئا. يُخرج ``0`` دائًما.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.payroll import OVERTIME_RATE  # noqa: E402

#: ما يُعَدّ إضافًيا غيَر معقول — تجاوُز وردّيٍة كاملة مرًة أخرى.
_SUSPECT_OT_MINUTES = 480


def _hourly(emp: models.Employee) -> float:
    """المعدُّل الساعي كما يحسبه ``payroll`` نفسه — لا صيغٌة ثانية تنحرف."""
    sal = float(emp.basic_salary or 0)
    daily = sal / 30 if sal else 0.0
    return daily / 8 if daily else 0.0


def report(company_id: int | None = None) -> dict:
    db = SessionLocal()
    try:
        q = select(models.AttendanceRecord)
        if company_id is not None:
            q = q.where(models.AttendanceRecord.company_id == company_id)
        rows = db.scalars(q).all()

        open_rows, inflated = [], []
        for r in rows:
            emp = db.get(models.Employee, r.employee_id)
            if emp is None:
                continue
            if r.check_out_at is None:
                open_rows.append((r, emp))
                continue
            if (r.overtime_minutes or 0) > _SUSPECT_OT_MINUTES:
                pay = round(_hourly(emp) * OVERTIME_RATE
                            * ((r.overtime_minutes or 0) / 60), 3)
                inflated.append((r, emp, pay))
        return {"total": len(rows), "open": open_rows, "inflated": inflated}
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", type=int, default=None)
    args = ap.parse_args()

    out = report(args.company)
    print(f"سجلاُت الحضور المفحوصة: {out['total']}")
    print(f"معدُّل الإضافي: {OVERTIME_RATE} × الساعة، "
          f"والسقُف: لا سقف (هذا هو البند)")

    print(f"\n**سجلاٌت مفتوحٌة الآن**: {len(out['open'])}")
    for r, emp in out["open"][:20]:
        print(f"  #{r.id}  {emp.name}  حضور {r.check_in_at}  — كلُّ ساعٍة تمرّ "
              f"تزيد الإضافّي عند أول بصمِة انصراف")

    inf = out["inflated"]
    print(f"\n**سجلاٌت إضافيُّها يتجاوز {_SUSPECT_OT_MINUTES} دقيقة**: {len(inf)}")
    total = 0.0
    for r, emp, pay in sorted(inf, key=lambda x: -x[2])[:20]:
        total += pay
        print(f"  #{r.id}  {emp.name:22} {r.overtime_minutes:>5} دقيقة "
              f"({(r.overtime_minutes or 0)/60:>5.1f} ساعة) = {pay:>9.3f} د.ك")
    if inf:
        allsum = round(sum(p for _r, _e, p in inf), 3)
        print(f"\n  المجموُع على كل السجلات المشبوهة: {allsum} د.ك")
        per = collections.Counter(e.id for _r, e, _p in inf)
        print(f"  ويخصُّ {len(per)} موظًفا")

    if not out["open"] and not inf:
        print("\nلا سجلَّ مفتوًحا ولا إضافًيا متضخًّما اليوم — والبنُد بنيويٌّ "
              "لا واقعيٌّ بعد: أوُّل نسياٍن يُنشئه.")

    print("\n— ولا يُصلَح هذا هنا: سقُف الدقائق يغيّر رقًما يُدفَع.")
    print("  والعلاُج المعلَن ``Branch.auto_checkout_minutes`` لم يُبنَ،")
    print("  والعلاُج اليدويُّ ``PUT /attendance/{id}/correct`` بلا شاشة.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
