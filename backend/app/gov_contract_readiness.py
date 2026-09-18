# -*- coding: utf-8 -*-
"""من لن يصدر له عقدٌ حكومي — ولماذا، قبل أن يُضغط الزرّ.

العقدُ صار يُملأ على نموذج الهيئة نفسه، وحقلٌ ناقص يوقف إصداره ويسمّيه
(قرار المالك 2026-09-17). وهو صحيح لورقٍة تُقدَّم للهيئة — لكنه يعني أن
موظف الموارد يكتشف النقصَ موظًفا موظًفا عند الضغط، وأن نقًصا في الشركة
(ممثّلها أو محافظة فرعها) يوقف عقودَ الجميع دفعًة واحدة.

فهنا القائمُة كلُّها مقدًَّما، من القاعدة نفسها التي يوقف بها المولِّد —
لا قائمة ثانية تنحرف عنها: ``gov_contract_form.missing_fields``.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import gov_contract_data, gov_contract_form, models
from .deps import INACTIVE_EMPLOYMENT

#: ما مصدرُه الشركة أو فرعها لا الموظف — يُعرض مرًة للشركة لا لكل موظف.
COMPANY_LEVEL = {"company_name", "company_rep_name", "company_civil_id", "labour_dept"}


def readiness(db: Session, company_id: int) -> dict:
    """``{company_missing: [...], employees: [{id, name, employee_no, missing}]}``."""
    from .routers.templates import _resolve_authoritative_data

    company = db.get(models.Company, company_id)
    employees = db.scalars(select(models.Employee).where(
        models.Employee.company_id == company_id,
        models.Employee.status.notin_(INACTIVE_EMPLOYMENT),
        models.Employee.non_payroll.isnot(True),
    ).order_by(models.Employee.name)).all()

    company_missing: set[str] = set()
    rows = []
    labels = gov_contract_form.REQUIRED
    for emp in employees:
        ctx = _resolve_authoritative_data(db, emp, extras={})
        ctx.update(gov_contract_data.contract_context(db, emp, company))
        values = gov_contract_form.values_from(ctx)
        missing_keys = [k for k in labels if not str(values.get(k) or "").strip()]
        company_missing.update(labels[k] for k in missing_keys if k in COMPANY_LEVEL)
        own = [labels[k] for k in missing_keys if k not in COMPANY_LEVEL]
        if own:
            rows.append({"employee_id": emp.id, "name": emp.name,
                         "employee_no": emp.employee_no, "branch_id": emp.branch_id,
                         "missing": own})
    return {"company_id": company_id,
            "company_name": company.name if company else None,
            "company_missing": sorted(company_missing),
            "employees": rows,
            "checked": len(employees)}
