# -*- coding: utf-8 -*-
"""PILOT-P0-6 — توليد الرقم الوظيفي للموظف.

الصيغة: `CO{company_id:02d}-BR{branch_id:02d}-{seq:04d}`
مثال: `CO01-BR03-0007` (شركة 1، فرع 3، تسلسل 7)

قواعد:
- فريد على مستوى النظام (unique DB constraint)
- ثابت بعد التوليد — لا يتغيّر مع نقل الفرع (فيه سياسة عليا لتغييره)
- Read-only في الواجهة
- يُملأ لأي موظف لسه ما اتولّدله رقم (backfill عند أول قراءة/كتابة)
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models


def _next_sequence(db: Session, company_id: int, branch_id: int | None) -> int:
    """أعلى تسلسل مستخدم داخل الشركة/الفرع + 1."""
    prefix = f"CO{company_id:02d}-BR{(branch_id or 0):02d}-"
    highest = 0
    q = select(models.Employee.employee_no).where(
        models.Employee.employee_no.like(f"{prefix}%")
    )
    for row in db.scalars(q).all():
        try:
            seq = int(row.rsplit("-", 1)[-1])
            if seq > highest:
                highest = seq
        except (ValueError, IndexError):
            continue
    return highest + 1


def generate(db: Session, employee: models.Employee) -> str:
    """يولّد رقمًا وظيفيًا للموظف. آمن للاستدعاء مرات متعددة (idempotent)."""
    if employee.employee_no:
        return employee.employee_no
    seq = _next_sequence(db, employee.company_id, employee.branch_id)
    code = f"CO{employee.company_id:02d}-BR{(employee.branch_id or 0):02d}-{seq:04d}"
    employee.employee_no = code
    return code


def backfill_missing(db: Session, company_id: int | None = None) -> int:
    """يعطي رقمًا وظيفيًا لأي موظف بدون رقم — للحسابات القديمة قبل P0-6."""
    q = select(models.Employee).where(models.Employee.employee_no.is_(None))
    if company_id is not None:
        q = q.where(models.Employee.company_id == company_id)
    count = 0
    for emp in db.scalars(q).all():
        generate(db, emp)
        count += 1
    if count:
        db.commit()
    return count
