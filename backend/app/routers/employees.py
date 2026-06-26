# -*- coding: utf-8 -*-
"""الموظفون: CRUD مع عزل، الملف الشخصي المجمّع، الإقامات/التراخيص/الخصومات، والنقل."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import eos as eos_engine
from .. import models, schemas
from ..database import get_db
from ..deps import (
    assert_same_company,
    audit,
    get_current_user,
    require_perm,
    scope_company_id,
)

router = APIRouter(prefix="/employees", tags=["employees"])


def _get_emp(db: Session, user: models.User, emp_id: int) -> models.Employee:
    emp = db.get(models.Employee, emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    assert_same_company(user, emp.company_id)
    return emp


@router.get("", response_model=list[schemas.EmployeeOut])
def list_employees(response: Response, company_id: int | None = None, branch_id: int | None = None,
                   q: str | None = None, limit: int = 100, offset: int = 0,
                   user: models.User = Depends(require_perm("view_employee")),
                   db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    base = select(models.Employee)
    if cid is not None:
        base = base.where(models.Employee.company_id == cid)
    if branch_id:
        base = base.where(models.Employee.branch_id == branch_id)
    if q:
        base = base.where(models.Employee.name.like(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    response.headers["X-Total-Count"] = str(total)
    limit = max(1, min(limit, 500))
    stmt = base.order_by(models.Employee.name).limit(limit).offset(max(offset, 0))
    return list(db.scalars(stmt).all())


@router.post("", response_model=schemas.EmployeeOut, status_code=201)
def create_employee(data: schemas.EmployeeIn, request: Request,
                    user: models.User = Depends(require_perm("create_employee")),
                    db: Session = Depends(get_db)):
    from ..permissions import CROSS_COMPANY_ROLES

    payload = data.model_dump()
    requested_cid = payload.pop("company_id", None)
    cid = requested_cid if user.role in CROSS_COMPANY_ROLES else user.company_id
    if cid is None:
        raise HTTPException(status_code=400, detail="يجب تحديد الشركة")
    emp = models.Employee(company_id=cid, **payload)
    db.add(emp)
    db.flush()
    audit(db, user, "create_employee", "employee", emp.id, request=request)
    db.commit()
    db.refresh(emp)
    return emp


@router.get("/{emp_id}", response_model=schemas.EmployeeOut)
def get_employee(emp_id: int, user: models.User = Depends(require_perm("view_employee")),
                 db: Session = Depends(get_db)):
    return _get_emp(db, user, emp_id)


@router.put("/{emp_id}", response_model=schemas.EmployeeOut)
def update_employee(emp_id: int, data: schemas.EmployeeIn, request: Request,
                    user: models.User = Depends(require_perm("edit_employee")),
                    db: Session = Depends(get_db)):
    emp = _get_emp(db, user, emp_id)
    payload = data.model_dump()
    payload.pop("company_id", None)  # لا يُغيَّر انتماء الشركة عبر التعديل العادي
    for k, v in payload.items():
        setattr(emp, k, v)
    audit(db, user, "update_employee", "employee", emp.id, request=request)
    db.commit()
    db.refresh(emp)
    return emp


@router.post("/{emp_id}/attendance-mode")
def set_attendance_mode(emp_id: int, mode: str, request: Request,
                        user: models.User = Depends(require_perm("manage_attendance")),
                        db: Session = Depends(get_db)):
    if mode not in ("none", "qr", "gps", "both"):
        raise HTTPException(status_code=400, detail="نمط حضور غير صالح")
    emp = _get_emp(db, user, emp_id)
    emp.attendance_mode = mode
    audit(db, user, "set_attendance_mode", "employee", emp.id, detail=mode, request=request)
    db.commit()
    return {"ok": True, "attendance_mode": mode}


@router.get("/{emp_id}/profile")
def employee_profile(emp_id: int, user: models.User = Depends(require_perm("view_employee")),
                     db: Session = Depends(get_db)):
    """الملف المجمّع: البيانات + الإقامات + المستندات + الخصومات + الإجازات + الحضور."""
    emp = _get_emp(db, user, emp_id)
    permits = db.scalars(select(models.Permit).where(models.Permit.employee_id == emp_id)).all()
    docs = db.scalars(
        select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == emp_id,
            models.Document.is_current == True,  # noqa: E712
        )
    ).all()
    deductions = db.scalars(select(models.Deduction).where(models.Deduction.employee_id == emp_id)).all()
    leaves = db.scalars(select(models.Leave).where(models.Leave.employee_id == emp_id)).all()
    attendance = db.scalars(
        select(models.AttendanceRecord)
        .where(models.AttendanceRecord.employee_id == emp_id)
        .order_by(models.AttendanceRecord.check_in_at.desc()).limit(30)
    ).all()
    return {
        "employee": schemas.EmployeeOut.model_validate(emp),
        "permits": [
            {"id": p.id, "kind": p.kind, "number": p.number,
             "expiry_date": p.expiry_date, "status": p.status} for p in permits
        ],
        "documents": [
            {"id": d.id, "type": d.document_type_code, "title": d.title,
             "expiry_date": d.expiry_date, "version": d.version} for d in docs
        ],
        "deductions": [
            {"id": x.id, "amount": x.amount, "reason": x.reason, "date": x.date}
            for x in deductions
        ],
        "leaves": [
            {"id": l.id, "type": l.leave_type, "start_date": l.start_date,
             "end_date": l.end_date, "days": l.days, "status": l.status} for l in leaves
        ],
        "attendance": [
            {"id": a.id, "check_in_at": a.check_in_at, "check_out_at": a.check_out_at,
             "status": a.status, "method": a.method, "selfie_in": bool(a.selfie_in_path)}
            for a in attendance
        ],
    }


# ----------------------------- الإقامات / أذونات العمل -----------------------------

@router.post("/{emp_id}/permits")
def add_permit(emp_id: int, kind: str, number: str | None = None,
               start_date: date | None = None, expiry_date: date | None = None,
               request: Request = None,
               user: models.User = Depends(require_perm("manage_permits")),
               db: Session = Depends(get_db)):
    emp = _get_emp(db, user, emp_id)
    permit = models.Permit(company_id=emp.company_id, employee_id=emp_id, kind=kind,
                           number=number, start_date=start_date, expiry_date=expiry_date)
    db.add(permit)
    audit(db, user, "add_permit", "employee", emp_id, detail=kind, request=request)
    db.commit()
    return {"ok": True, "id": permit.id}


# ----------------------------- إنهاء الخدمة -----------------------------

@router.post("/{emp_id}/terminate")
def terminate_employee(emp_id: int, end_date: date, reason: str = "termination",
                       unused_leave_days: float = 0, request: Request = None,
                       user: models.User = Depends(require_perm("terminate_employee")),
                       db: Session = Depends(get_db)):
    """ينهي خدمة الموظف: يحسب مكافأة نهاية الخدمة وفق سياسة شركته ويؤرشف حالته."""
    emp = _get_emp(db, user, emp_id)
    if emp.status == "terminated":
        raise HTTPException(status_code=409, detail="خدمة الموظف منتهية بالفعل")
    company = db.get(models.Company, emp.company_id)
    try:
        settlement = eos_engine.calculate_eos(
            basic_salary=emp.basic_salary, hire_date=emp.hire_date, end_date=end_date,
            reason=reason, contract_type=emp.contract_type,
            unused_leave_days=unused_leave_days,
            day_divisor=company.eos_day_divisor, max_months=company.eos_max_months)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    emp.status = "terminated"
    audit(db, user, "terminate_employee", "employee", emp.id,
          detail=f"{reason} @ {end_date} = {settlement['total_settlement']} KWD", request=request)
    db.commit()
    return {"ok": True, "employee_id": emp.id, "status": "terminated", "settlement": settlement}


# ----------------------------- النقل بين الشركات -----------------------------

@router.post("/{emp_id}/transfer")
def transfer_employee(emp_id: int, to_company_id: int, note: str | None = None,
                      request: Request = None,
                      user: models.User = Depends(require_perm("transfer_employee")),
                      db: Session = Depends(get_db)):
    emp = _get_emp(db, user, emp_id)
    target = db.get(models.Company, to_company_id)
    if not target:
        raise HTTPException(status_code=404, detail="الشركة الهدف غير موجودة")
    from_company = emp.company_id
    db.add(models.Transfer(employee_id=emp_id, from_company_id=from_company,
                           to_company_id=to_company_id, transferred_by=user.id, note=note))
    emp.company_id = to_company_id
    emp.branch_id = None
    audit(db, user, "transfer_employee", "employee", emp_id,
          detail=f"{from_company}->{to_company_id}", request=request)
    db.commit()
    return {"ok": True, "from": from_company, "to": to_company_id}
