# -*- coding: utf-8 -*-
"""من يعمل على غير ترخيص تسجيله — تنبيهٌ تفتيشي (قرار المالك 2026-09-17).

``Employee.license_id`` ترخيصُ التسجيل (وبه تُعَدّ السعة)، و
``actual_license_id`` الترخيصُ الذي يعمل عليه فعلًا. كان الثاني حقلًا لم يُملأ
قطّ ولا تعرضه الواجهة — فالمخطَّط يوهم بمتابعةٍ لا تقع. واختلافُهما مخاطرةُ
تفتيش: عاملٌ مسجَّلٌ على ترخيصٍ ويعمل على غيره.

مصدرٌ واحد يقرؤه ملفُّ الموظف ومركزُ العمليات.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .deps import INACTIVE_EMPLOYMENT


def is_mismatch(emp: models.Employee) -> bool:
    return (emp.actual_license_id is not None
            and emp.actual_license_id != emp.license_id)


def mismatches(db: Session, company_id: int | None) -> list[dict]:
    q = select(models.Employee).where(
        models.Employee.actual_license_id.isnot(None),
        models.Employee.status.notin_(INACTIVE_EMPLOYMENT))
    if company_id is not None:
        q = q.where(models.Employee.company_id == company_id)
    out = []
    names = {}

    def _name(lid):
        if lid is None:
            return None
        if lid not in names:
            lic = db.get(models.License, lid)
            names[lid] = (lic.name if lic else None)
        return names[lid]

    for e in db.scalars(q.order_by(models.Employee.name)).all():
        if not is_mismatch(e):
            continue
        out.append({"employee_id": e.id, "name": e.name, "employee_no": e.employee_no,
                    "branch_id": e.branch_id,
                    "license_id": e.license_id, "license_name": _name(e.license_id),
                    "actual_license_id": e.actual_license_id,
                    "actual_license_name": _name(e.actual_license_id)})
    return out
