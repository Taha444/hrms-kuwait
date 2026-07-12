# -*- coding: utf-8 -*-
"""الموظفون: CRUD مع عزل، الملف الشخصي المجمّع، الإقامات/التراخيص/الخصومات، والنقل."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .. import eos as eos_engine
from .. import models, schemas
from ..database import get_db
from ..deps import (
    assert_same_company,
    audit,
    get_current_user,
    require_perm,
    resolve_scope,
    scope_company_id,
)

router = APIRouter(prefix="/employees", tags=["employees"])


def _assert_no_duplicates(db: Session, cid: int, civil_id: str | None,
                          passport: str | None, exclude_id: int | None = None):
    """منع تكرار الرقم المدني ورقم الجواز داخل الشركة."""
    if civil_id:
        q = select(models.Employee.id).where(models.Employee.company_id == cid,
                                             models.Employee.civil_id == civil_id)
        if exclude_id:
            q = q.where(models.Employee.id != exclude_id)
        if db.scalar(q):
            raise HTTPException(status_code=409, detail="الرقم المدني مسجّل لموظف آخر")
    if passport:
        q = select(models.Employee.id).where(models.Employee.company_id == cid,
                                             models.Employee.passport_number == passport)
        if exclude_id:
            q = q.where(models.Employee.id != exclude_id)
        if db.scalar(q):
            raise HTTPException(status_code=409, detail="رقم الجواز مسجّل لموظف آخر")


def _assert_branch_in_scope(db: Session, user: models.User, *branch_ids: int | None):
    """من له نطاق فروع محدد لا يضيف/ينقل موظفًا إلى فرع خارج نطاقه."""
    sc = resolve_scope(user, db)
    if sc.branch_ids is None:
        return
    for bid in branch_ids:
        if bid and bid not in sc.branch_ids:
            raise HTTPException(status_code=403, detail="لا يمكنك إضافة موظف لفرع خارج نطاقك")


def _get_emp(db: Session, user: models.User, emp_id: int) -> models.Employee:
    emp = db.get(models.Employee, emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    assert_same_company(user, emp.company_id, db=db)
    sc = resolve_scope(user, db)
    if sc.branch_ids is not None and emp.branch_id not in sc.branch_ids:
        audit(db, user, "FORBIDDEN_SCOPE_ACCESS", "employee", emp.id, detail="branch_out_of_scope")
        db.commit()
        raise HTTPException(status_code=404, detail="الموظف غير موجود")  # خارج نطاق فرعك
    if sc.self_employee_id is not None and emp.id != sc.self_employee_id:
        audit(db, user, "FORBIDDEN_SCOPE_ACCESS", "employee", emp.id, detail="self_scope_only")
        db.commit()
        raise HTTPException(status_code=404, detail="الموظف غير موجود")  # خدمة ذاتية: سجله فقط
    return emp


@router.get("", response_model=list[schemas.EmployeeOut])
def list_employees(response: Response, company_id: int | None = None, branch_id: int | None = None,
                   department_id: int | None = None, q: str | None = None,
                   limit: int = 100, offset: int = 0,
                   user: models.User = Depends(require_perm("view_employee")),
                   db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    base = select(models.Employee)
    if cid is not None:
        base = base.where(models.Employee.company_id == cid)
    if branch_id:
        base = base.where(models.Employee.branch_id == branch_id)
    if department_id:
        base = base.where(models.Employee.department_id == department_id)
    # تقييد النطاق وفق المستوى: فرع/عدة فروع/خدمة ذاتية (يُفرَض على الخادم)
    sc = resolve_scope(user, db)
    if sc.branch_ids is not None:
        base = base.where(models.Employee.branch_id.in_(sc.branch_ids))
    if sc.self_employee_id is not None:
        base = base.where(models.Employee.id == sc.self_employee_id)
    if q:
        like = f"%{q.strip()}%"
        # بحث بالاسم / الرقم المدني / رقم الموظف / رقم الإقامة
        permit_emp_ids = select(models.Permit.employee_id).where(models.Permit.number.like(like))
        conds = [models.Employee.name.like(like), models.Employee.civil_id.like(like),
                 models.Employee.passport_number.like(like),
                 models.Employee.id.in_(permit_emp_ids)]
        if q.strip().isdigit():
            conds.append(models.Employee.id == int(q.strip()))
        base = base.where(or_(*conds))
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    response.headers["X-Total-Count"] = str(total)
    limit = max(1, min(limit, 500))
    stmt = base.order_by(models.Employee.name).limit(limit).offset(max(offset, 0))
    return list(db.scalars(stmt).all())


@router.post("", response_model=schemas.EmployeeOut, status_code=201)
def create_employee(data: schemas.EmployeeCreateIn, request: Request,
                    user: models.User = Depends(require_perm("create_employee")),
                    db: Session = Depends(get_db)):
    from ..permissions import CROSS_COMPANY_ROLES

    payload = data.model_dump()
    requested_cid = payload.pop("company_id", None)
    cid = requested_cid if user.role in CROSS_COMPANY_ROLES else user.company_id
    if cid is None:
        raise HTTPException(status_code=400, detail="يجب تحديد الشركة")
    _assert_no_duplicates(db, cid, payload.get("civil_id"), payload.get("passport_number"))
    _assert_branch_in_scope(db, user, payload.get("branch_id"), payload.get("actual_branch_id"))
    emp = models.Employee(company_id=cid, created_by=user.id, **payload)
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
def update_employee(emp_id: int, data: schemas.EmployeeCreateIn, request: Request,
                    user: models.User = Depends(require_perm("edit_employee")),
                    db: Session = Depends(get_db)):
    emp = _get_emp(db, user, emp_id)
    payload = data.model_dump()
    payload.pop("company_id", None)  # لا يُغيَّر انتماء الشركة عبر التعديل العادي
    _assert_no_duplicates(db, emp.company_id, payload.get("civil_id"),
                          payload.get("passport_number"), exclude_id=emp.id)
    _assert_branch_in_scope(db, user, payload.get("branch_id"), payload.get("actual_branch_id"))
    for k, v in payload.items():
        setattr(emp, k, v)
    audit(db, user, "update_employee", "employee", emp.id, request=request)
    db.commit()
    db.refresh(emp)
    return emp


@router.post("/{emp_id}/apply-ocr")
def apply_ocr(emp_id: int, data: schemas.OcrApplyIn, request: Request = None,
              user: models.User = Depends(require_perm("edit_employee")),
              db: Session = Depends(get_db)):
    """تطبيق بيانات OCR (بعد مراجعة المستخدم) على ملف الموظف — يحفظ القيم القديمة في التدقيق."""
    emp = _get_emp(db, user, emp_id)
    fields = data.model_dump(exclude_none=True)
    _assert_no_duplicates(db, emp.company_id, fields.get("civil_id"),
                          fields.get("passport_number"), exclude_id=emp.id)
    changes = []
    for k, v in fields.items():
        old = getattr(emp, k)
        if old != v:
            changes.append(f"{k}: {old if old not in (None, '') else '—'} → {v}")
            setattr(emp, k, v)
    if changes:
        audit(db, user, "apply_ocr", "employee", emp.id, detail=" | ".join(changes), request=request)
        db.commit()
    return {"ok": True, "updated": len(changes), "changes": changes}


@router.post("/{emp_id}/actual-salary")
def set_actual_salary(emp_id: int, amount: float, request: Request = None,
                      user: models.User = Depends(require_perm("edit_actual_salary")),
                      db: Session = Depends(get_db)):
    """تعديل الراتب الفعلي (صلاحية مالية خاصة) — يُسجَّل في التدقيق مع القيمة القديمة."""
    if amount < 0:
        raise HTTPException(status_code=400, detail="القيمة لا يمكن أن تكون سالبة")
    emp = _get_emp(db, user, emp_id)
    old = emp.actual_salary
    emp.actual_salary = amount
    audit(db, user, "edit_actual_salary", "employee", emp.id,
          detail=f"{old} → {amount}", request=request)
    db.commit()
    return {"ok": True, "actual_salary": amount}


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
    # الإقامات/أذونات العمل شأن حكومي → تُعرَض للمندوب/الإدارة العليا فقط
    from ..permissions import has_permission
    from ..deps import get_user_perms
    perms = get_user_perms(user, db)
    is_admin = user.role == "super_admin"
    can_gov = is_admin or has_permission(user.role, perms, "manage_permits")
    can_view_actual = is_admin or has_permission(user.role, perms, "view_actual_salary")
    can_edit_actual = is_admin or has_permission(user.role, perms, "edit_actual_salary")
    permits = db.scalars(select(models.Permit).where(
        models.Permit.employee_id == emp_id)).all() if can_gov else []
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
        # الراتب الفعلي يُعرَض/يُعدَّل حسب الصلاحية المالية فقط
        "actual_salary": emp.actual_salary if can_view_actual else None,
        "can_view_actual_salary": can_view_actual,
        "can_edit_actual_salary": can_edit_actual,
        "created_by_name": (db.get(models.User, emp.created_by).full_name
                            if emp.created_by and db.get(models.User, emp.created_by) else None),
        # نتيجة نهاية الخدمة المحفوظة (إن وُجدت)
        "saved_eos": (__import__("json").loads(emp.eos_settlement_json)
                      if emp.eos_settlement_json else None),
        "termination_date": emp.termination_date,
        "termination_reason": emp.termination_reason,
        "permits": [
            {"id": p.id, "kind": p.kind, "number": p.number,
             "expiry_date": p.expiry_date, "status": p.status} for p in permits
        ],
        "documents": [
            {"id": d.id, "type": d.document_type_code, "title": d.title,
             "expiry_date": d.expiry_date, "version": d.version} for d in docs
        ],
        # الخصومات: المبلغ حقل مالي حساس — يُخفى عمّن لا يملك view_actual_salary (FIX-013)
        # المسؤول المباشر يرى السبب والتاريخ فقط دون المبلغ؛ المحاسب/الإدارة العليا يريان التفصيل الكامل.
        "deductions": [
            {"id": x.id, "amount": x.amount if can_view_actual else None,
             "reason": x.reason, "date": x.date}
            for x in deductions
        ],
        "deductions_masked": not can_view_actual,
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


EMP_STATUSES = {"active", "vacation", "suspended", "resigned", "terminated", "retired", "archived"}
EVENT_KINDS = {"warning", "penalty", "bonus", "promotion", "note"}


@router.post("/{emp_id}/status")
def set_status(emp_id: int, status: str, request: Request = None,
               user: models.User = Depends(require_perm("edit_employee")),
               db: Session = Depends(get_db)):
    """تغيير حالة الموظف (حالة واحدة فقط في كل وقت)."""
    if status not in EMP_STATUSES:
        raise HTTPException(status_code=400, detail="حالة غير صالحة")
    emp = _get_emp(db, user, emp_id)
    old = emp.status
    emp.status = status
    audit(db, user, "employee_status", "employee", emp.id, detail=f"{old} → {status}", request=request)
    db.commit()
    return {"ok": True, "status": status}


# ----------------------------- أحداث الموارد البشرية -----------------------------

@router.post("/{emp_id}/events")
def add_event(emp_id: int, kind: str, title: str, detail: str | None = None,
              amount: float | None = None, date_val: date | None = None, request: Request = None,
              user: models.User = Depends(require_perm("edit_employee")),
              db: Session = Depends(get_db)):
    """تسجيل إنذار/جزاء/مكافأة/ترقية/ملاحظة للموظف."""
    if kind not in EVENT_KINDS:
        raise HTTPException(status_code=400, detail="نوع حدث غير صالح")
    emp = _get_emp(db, user, emp_id)
    ev = models.EmployeeEvent(company_id=emp.company_id, employee_id=emp.id, kind=kind,
                              title=title, detail=detail, amount=amount,
                              date=date_val or date.today(), created_by=user.id)
    db.add(ev)
    db.flush()
    audit(db, user, f"employee_{kind}", "employee", emp.id, detail=title, request=request)
    db.commit()
    return {"ok": True, "id": ev.id}


@router.get("/{emp_id}/events")
def list_events(emp_id: int, user: models.User = Depends(require_perm("view_employee")),
                db: Session = Depends(get_db)):
    emp = _get_emp(db, user, emp_id)
    rows = db.scalars(select(models.EmployeeEvent).where(
        models.EmployeeEvent.employee_id == emp.id).order_by(models.EmployeeEvent.date.desc())).all()
    return [{"id": e.id, "kind": e.kind, "title": e.title, "detail": e.detail,
             "amount": e.amount, "date": e.date} for e in rows]


# ----------------------------- الخط الزمني (Timeline) -----------------------------

@router.get("/{emp_id}/timeline")
def employee_timeline(emp_id: int, user: models.User = Depends(require_perm("view_employee")),
                      db: Session = Depends(get_db)):
    """سجل زمني موحّد لكل أحداث الموظف (إنشاء، مستندات، إقامات، إجازات، إنذارات...)."""
    emp = _get_emp(db, user, emp_id)
    items: list[dict] = []

    items.append({"at": emp.created_at.isoformat(), "category": "create", "text": "تم إنشاء ملف الموظف"})
    for d in db.scalars(select(models.Document).where(
            models.Document.entity_type == "employee", models.Document.entity_id == emp.id)).all():
        items.append({"at": d.created_at.isoformat(), "category": "document",
                      "text": f"رفع مستند: {d.title or d.document_type_code} (نسخة {d.version})"})
    for p in db.scalars(select(models.Permit).where(models.Permit.employee_id == emp.id)).all():
        kind = "إقامة" if p.kind == "residency" else "إذن عمل"
        items.append({"at": (p.start_date or emp.created_at.date()).isoformat() + "T00:00:00",
                      "category": "permit", "text": f"{kind} رقم {p.number} (تنتهي {p.expiry_date})"})
    for lv in db.scalars(select(models.Leave).where(models.Leave.employee_id == emp.id)).all():
        items.append({"at": lv.start_date.isoformat() + "T00:00:00", "category": "leave",
                      "text": f"إجازة من {lv.start_date} إلى {lv.end_date} ({lv.days} يوم)"})
    for ev in db.scalars(select(models.EmployeeEvent).where(models.EmployeeEvent.employee_id == emp.id)).all():
        items.append({"at": (ev.date or ev.created_at.date()).isoformat() + "T00:00:00",
                      "category": ev.kind, "text": ev.title + (f" — {ev.amount} د.ك" if ev.amount else "")})

    items.sort(key=lambda x: x["at"], reverse=True)
    return {"employee": {"id": emp.id, "name": emp.name, "status": emp.status}, "timeline": items}


# ----------------------------- إنهاء الخدمة -----------------------------

@router.post("/{emp_id}/terminate")
def terminate_employee(emp_id: int, end_date: date, reason: str = "termination",
                       used_leave_days: int = 0, request: Request = None,
                       user: models.User = Depends(require_perm("terminate_employee")),
                       db: Session = Depends(get_db)):
    """ينهي خدمة الموظف: يحسب مكافأة نهاية الخدمة وفق سياسة شركته ويؤرشف حالته.

    رصيد الإجازات يُحسب آليًا من مدة الخدمة؛ يُستقبَل المستهلَك فقط (used_leave_days).
    """
    emp = _get_emp(db, user, emp_id)
    if emp.status == "terminated":
        raise HTTPException(status_code=409, detail="خدمة الموظف منتهية بالفعل")
    company = db.get(models.Company, emp.company_id)
    try:
        settlement = eos_engine.calculate_eos(
            basic_salary=emp.basic_salary, hire_date=emp.hire_date, end_date=end_date,
            reason=reason, contract_type=emp.contract_type,
            used_leave_days=used_leave_days, annual_leave_days=company.annual_leave_days,
            day_divisor=company.eos_day_divisor, max_months=company.eos_max_months)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    emp.status = "terminated"
    # حفظ نتيجة الحسبة في ملف الموظف (DEMO-014)
    import json
    emp.termination_date = end_date
    emp.termination_reason = reason
    emp.eos_settlement_json = json.dumps(settlement, ensure_ascii=False)
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
