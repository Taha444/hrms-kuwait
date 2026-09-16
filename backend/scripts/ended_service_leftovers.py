# -*- coding: utf-8 -*-
"""ما تركه الماضي لمن انتهت خدمته — تقريرٌ لا تعديل.

**السياق**: الإنهاءُ صار يُعطّل الحساب (``revoke_employee_access``)، والدخولُ
يرفض من انتهت خدمته، ومصادرُ المعتمِدين لا تختاره. لكنّ من أُنهيت خدمتُه
**قبل** ذلك يبقى أثرُه في القاعدة:

1. **حسابٌ ما زال ``is_active``** — لا يدخل، لكن شاشةَ المستخدمين تعرضه نشطًا.
2. **مهامٌّ مفتوحةٌ في صندوقه** — أُسندت إليه قبل الإصلاح، ولا يفتحها أحد.
3. **تفويضاتٌ قائمة** منه أو إليه.

وهذا التقريرُ يسمّيها لتُعالَج **من الشاشة** (تعطيلُ الحساب من «المستخدمين»،
وإعادةُ إسناد المهمة، وإلغاءُ التفويض) — فيبقى في التدقيق من فعل ولماذا.

الاستخدام::

    .venv/Scripts/python.exe scripts/ended_service_leftovers.py
    .venv/Scripts/python.exe scripts/ended_service_leftovers.py --company 1

لا يكتب شيئًا. يُخرج ``0`` دائمًا.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import or_, select  # noqa: E402

from app import models  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.deps import INACTIVE_EMPLOYMENT  # noqa: E402


def report(company_id: int | None = None) -> dict:
    db = SessionLocal()
    try:
        q = (select(models.User, models.Employee)
             .join(models.Employee, models.Employee.id == models.User.employee_id)
             .where(models.Employee.status.in_(INACTIVE_EMPLOYMENT)))
        if company_id is not None:
            q = q.where(models.Employee.company_id == company_id)
        pairs = db.execute(q).all()
        out = {"accounts": [], "tasks": [], "delegations": []}
        for u, e in pairs:
            if u.is_active:
                out["accounts"].append((u.id, u.civil_id, u.role, e.name, e.status))
            for t in db.scalars(select(models.Task).where(
                    models.Task.assignee_user_id == u.id,
                    models.Task.status.in_(("open", "in_progress")))).all():
                out["tasks"].append((t.id, t.type, (t.title or "")[:50], e.name))
            for d in db.scalars(select(models.ApprovalDelegation).where(
                    models.ApprovalDelegation.is_active == True,  # noqa: E712
                    or_(models.ApprovalDelegation.delegator_user_id == u.id,
                        models.ApprovalDelegation.delegate_user_id == u.id))).all():
                side = "منه" if d.delegator_user_id == u.id else "إليه"
                out["delegations"].append((d.id, side, e.name, d.ends_at))
        return out
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", type=int, default=None)
    args = ap.parse_args()
    out = report(args.company)

    print(f"١) حساباتٌ نشطةٌ لمن انتهت خدمته: {len(out['accounts'])}")
    for uid, cid, role, name, st in out["accounts"]:
        print(f"   #{uid:<5} {cid}  {role:18} {name[:26]:26} ({st})")
    print(f"\n٢) مهامٌّ مفتوحةٌ في صناديقهم: {len(out['tasks'])}")
    for tid, typ, title, name in out["tasks"][:40]:
        print(f"   مهمة #{tid:<6} {typ:20} {title:50} ← {name[:20]}")
    print(f"\n٣) تفويضاتٌ قائمة: {len(out['delegations'])}")
    for did, side, name, ends in out["delegations"]:
        print(f"   تفويض #{did:<5} {side} {name[:26]:26} حتى {ends}")

    if not any(out.values()):
        print("\nلا أثرَ باقٍ — لا شيء يُعالَج.")
    else:
        print("\n— يُعالَج من الشاشة: تعطيلُ الحساب من «المستخدمين»، وإعادةُ إسناد "
              "المهمة، وإلغاءُ التفويض — فيبقى في التدقيق من فعل ولماذا.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
