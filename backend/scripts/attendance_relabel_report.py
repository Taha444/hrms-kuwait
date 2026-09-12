# -*- coding: utf-8 -*-
"""ما كان يتغيّر وسمُه لو أُعيد حساُب الحضور بالساعة الصحيحة — تقريٌر ال تعديل.

**السياق**: أُصلحت المنطقُة الزمنية في حساب الحضور
(``test_zzz_attendance_timezone.py``): كانت وردٌية بساعاٍت كويتية تُقارَن
بلحظٍة بتوقيت UTC، فالمهلُة كلُّها منزاحٌة ثالث ساعات لمصلحة المتأخّر
(«التأخير لا يُرصَد أبًدا»)، واالنصراُف المبكر يُرصَد ظلًما.

**وكلُّ سجٍّل كُتب قبل اإلصالح يحمل وسًما قِيس بالساعة الخاطئة.** والقياُس
على بيانات البذر: تسعَة عشر من أربعٍة وعشرين يتغيّر وسمُها، ثمانيَة عشر
منها ``present → late``.

**وال يُعاد الوسُم تلقائًيا، وهذا قصٌد ال تأجيل:**

- الوسُم يُبنى عليه عمٌل وقع: خصُم غياٍب في مسيٍّر اعتُمد، وإنذاٌر صدر،
  ومسيٌَّر أُقفل. وتغييُر التاريخ بأثٍر رجعي يجعل مسيًَّرا مقفًال يخالف
  بياناته.
- و``AttendanceMonthClose`` موجودٌة في النظام: للشهر إغالٌق صريح بمن أغلقه
  ومتى. **فالمغلَق ال يُمَسّ إال بإعادة فتٍح موّثقة** — وهي موجودٌة أيًضا
  (``reopened_by`` و``reopen_reason``).

فهذا التقريُر يضع الرقَم أمام صاحب القرار، مفصوًال: ما في شهٍر **مفتوح**
(يُعاد حسابه بأمان)، وما في شهٍر **مغلَق** (يحتاج إعادَة فتٍح وقراًرا).

الاستخدام::

    .venv/Scripts/python.exe scripts/attendance_relabel_report.py
    .venv/Scripts/python.exe scripts/attendance_relabel_report.py --company 1

لا يكتب شيًئا. يُخرج ``0`` دائًما.
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import sys
from datetime import timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.routers import attendance as A  # noqa: E402


def _closed_periods(db, company_id: int | None) -> set[tuple[int, str]]:
    """الأشهر المغلقة — ``(company_id, "YYYY-MM")``."""
    q = select(models.AttendanceMonthClose).where(
        models.AttendanceMonthClose.status == "closed")
    if company_id is not None:
        q = q.where(models.AttendanceMonthClose.company_id == company_id)
    return {(r.company_id, r.period) for r in db.scalars(q).all()}


def report(company_id: int | None = None) -> dict:
    db = SessionLocal()
    try:
        closed = _closed_periods(db, company_id)
        q = select(models.AttendanceRecord)
        if company_id is not None:
            q = q.where(models.AttendanceRecord.company_id == company_id)

        rows = db.scalars(q).all()
        changes: list[dict] = []
        unreadable = 0
        for rec in rows:
            if not rec.check_in_at:
                continue
            emp = db.get(models.Employee, rec.employee_id)
            if emp is None:
                continue
            moment = (rec.check_in_at if rec.check_in_at.tzinfo
                      else rec.check_in_at.replace(tzinfo=timezone.utc))
            try:
                fresh = A._compute_in_status(db, emp, moment)
            except Exception:
                unreadable += 1
                continue
            if fresh == rec.status or rec.status not in ("present", "late"):
                continue
            period = moment.astimezone(A.KUWAIT_TZ).strftime("%Y-%m")
            changes.append({
                "id": rec.id, "company_id": rec.company_id,
                "employee_id": rec.employee_id, "period": period,
                "stored": rec.status, "recomputed": fresh,
                "closed": (rec.company_id, period) in closed,
            })
        return {"total": len(rows), "changes": changes, "unreadable": unreadable}
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", type=int, default=None)
    args = ap.parse_args()

    out = report(args.company)
    ch = out["changes"]
    print(f"سجالُت الحضور المفحوصة: {out['total']}")
    if out["unreadable"]:
        print(f"  تعذّر حساُب {out['unreadable']} (ال وردّية أو بياٌن ناقص)")
    print(f"يتغيّر وسمُها بالساعة الصحيحة: {len(ch)}")
    if not ch:
        print("\nال سجّل يتغيّر وسمُه — ال قراَر مطلوًبا.")
        return 0

    by_dir = collections.Counter(f"{c['stored']} → {c['recomputed']}" for c in ch)
    print("\nواالتجاه:")
    for k, v in by_dir.most_common():
        note = ("  (كان المتأخُّر يُسجَّل حاضًرا — العطُل لمصلحة الموظف)"
                if k == "present → late" else
                "  (كان الحاضُر يُسجَّل متأخًّرا — ظلٌم يُصحَّح)"
                if k == "late → present" else "")
        print(f"  {k:22} {v}{note}")

    open_ch = [c for c in ch if not c["closed"]]
    shut_ch = [c for c in ch if c["closed"]]
    print(f"\nفي أشهٍر **مفتوحة** (يُعاد حسابها بأمان): {len(open_ch)}")
    print(f"في أشهٍر **مغلَقة** (تحتاج إعادَة فتٍح وقراًرا): {len(shut_ch)}")

    per = collections.Counter(f"{c['company_id']}/{c['period']}"
                             + (" [مغلَق]" if c["closed"] else "") for c in ch)
    print("\nبحسب الشهر:")
    for k, v in sorted(per.items()):
        print(f"  {k:24} {v}")

    print("\nال يُعاد الوسُم تلقائًيا: عليه خصُم غياٍب في مسيٍّر اعتُمد، وإنذاٌر")
    print("صدر. والمغلَُق ال يُمَسّ إال بإعادة فتٍح موّثقة (reopen_reason).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
