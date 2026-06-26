# -*- coding: utf-8 -*-
"""مكافأة نهاية الخدمة: حاسبة حرّة + حساب لموظف وفق سياسة شركته."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import eos as eos_engine
from .. import models, schemas
from ..database import get_db
from ..deps import assert_same_company, require_perm

router = APIRouter(prefix="/eos", tags=["eos"])


@router.get("/reasons")
def reasons():
    return eos_engine.TERMINATION_REASONS


@router.post("/calculate")
def calculate(data: schemas.EosIn, user: models.User = Depends(require_perm("calculate_eos"))):
    try:
        return eos_engine.calculate_eos(
            basic_salary=data.basic_salary, hire_date=data.hire_date, end_date=data.end_date,
            reason=data.reason, contract_type=data.contract_type,
            unused_leave_days=data.unused_leave_days,
            day_divisor=data.day_divisor or 26, max_months=data.max_months or 18,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/leave-balance")
def leave_balance(employee_id: int, consumed_days: float = 0, as_of: date | None = None,
                  user: models.User = Depends(require_perm("calculate_eos")),
                  db: Session = Depends(get_db)):
    """يحسب رصيد الإجازات المستحق تلقائيًا حسب مدة الخدمة؛ المستخدم يُدخل المستهلَك فقط."""
    emp = db.get(models.Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    assert_same_company(user, emp.company_id)
    if not emp.hire_date:
        raise HTTPException(status_code=400, detail="تاريخ التعيين غير مُسجّل")
    company = db.get(models.Company, emp.company_id)
    end = as_of or date.today()
    _, _, _, _, decimal_years = eos_engine.service_breakdown(emp.hire_date, end)
    per_year = float(company.annual_leave_days or 30)
    accrued = round(per_year * decimal_years, 2)
    remaining = round(accrued - float(consumed_days or 0), 2)
    return {
        "employee_id": emp.id, "name": emp.name,
        "service_years": round(decimal_years, 2),
        "annual_days_per_year": per_year,
        "accrued_days": accrued,
        "consumed_days": float(consumed_days or 0),
        "remaining_days": remaining,
        "as_of": end.isoformat(),
    }


@router.post("/for-employee")
def for_employee(data: schemas.EosForEmployeeIn,
                 user: models.User = Depends(require_perm("calculate_eos")),
                 db: Session = Depends(get_db)):
    emp = db.get(models.Employee, data.employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    assert_same_company(user, emp.company_id)
    company = db.get(models.Company, emp.company_id)
    try:
        result = eos_engine.calculate_eos(
            basic_salary=emp.basic_salary, hire_date=emp.hire_date, end_date=data.end_date,
            reason=data.reason, contract_type=emp.contract_type,
            unused_leave_days=data.unused_leave_days,
            day_divisor=company.eos_day_divisor, max_months=company.eos_max_months,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result["employee"] = {"id": emp.id, "name": emp.name, "job_title": emp.job_title}
    return result
