# -*- coding: utf-8 -*-
"""الموظفون: CRUD مع عزل، الملف الشخصي المجمّع، الإقامات/التراخيص/الخصومات، والنقل."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..clock import today as kuwait_today
from .. import eos as eos_engine
from .. import leave_balance as leave_balance_service
from .. import models, schemas
from ..storage import file_response, save_at_key
from ..database import get_db
from .. import exit_guard
from ..deps import (
    assert_same_company,
    audit,
    get_current_user,
    get_user_perms,
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


@router.get("")
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
    rows = list(db.scalars(stmt).all())

    # سياسة الحقول تُطبَّق هنا كما تُطبَّق على مسار التفصيل. كانت مكتوبة
    # هناك وحده، فبقي السرد يعيد الجواز والراتب لكل من يستطيع سرد
    # الموظفين — ومنهم مسؤول الفرع. ومن أراد البيانات لا يفتح ملًفا واحًدا
    # بل يفتح القائمة.
    #
    # وأُزيل ``response_model`` عمًدا: Pydantic يعيد بناء الحقول المحذوفة
    # بقيمة None، فيعود التسريب في ثوب «لا يوجد جواز».
    from ..field_policy import redact_employees

    perms = get_user_perms(user, db)
    payload = [schemas.EmployeeOut.model_validate(r).model_dump() for r in rows]
    return redact_employees(payload, user, perms)


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
    # PILOT-P0-6 — نولّد الرقم الوظيفي الرسمي بعد الـflush علشان employee.id يكون متوفر
    from .. import employee_no as _emp_no
    _emp_no.generate(db, emp)
    audit(db, user, "create_employee", "employee", emp.id,
          detail=f"employee_no={emp.employee_no}", request=request)
    db.commit()
    db.refresh(emp)
    return emp


@router.get("/{emp_id}")
def get_employee(emp_id: int, user: models.User = Depends(require_perm("view_employee")),
                 db: Session = Depends(get_db)):
    emp = _get_emp(db, user, emp_id)
    # سياسة الحقول من app/field_policy — لا نسخة ثالثة هنا.
    #
    # **العطل**: كانت هذه الدالة تحمل قائمتها الخاصة، وتُنقّي للمحاسب
    # والمندوب وحدهما. فمسؤول الفرع — وهو لا يملك ``view_documents`` —
    # كان يأخذ الجواز صريًحا من هذا المسار بينما يمنعه مسار الملف الكامل.
    # قاعدة واحدة في ثلاثة مواضع: أحدها يُصان واثنان يُنسيان.
    from ..field_policy import redact_employee

    perms = get_user_perms(user, db)
    out = redact_employee(
        schemas.EmployeeOut.model_validate(emp).model_dump(),
        user, perms, employee_id=emp.id)
    # هل يجوز توجيه إنذار لهذا الموظف؟ الواجهة تُخفي بند الإنذارات بناًء عليه،
    # فلا تحمل نسخة ثانية من قائمة الأدوار المعفاة تنحرف عن قاعدة الخادم.
    from ..permissions import may_receive_warning
    holder = db.scalar(select(models.User).where(models.User.employee_id == emp.id))
    out["may_receive_warning"] = may_receive_warning(holder.role) if holder else True
    return out


# R3-C §4 — الحقول اللي كل تعديل عليها يُسجَّل في EmployeeFieldChange (سجل نسخي دائم)
#
# PERM-03 — وُسِّعت لتشمل إعدادات الحضور والوظيفة الفعلية وساعات الدوام ومكان
# الدوام. كانت مقصورة على السبعة المالية/التعاقدية، فتعديل نمط حضور موظف أو
# إعفاؤه من البصم لم يكن يظهر في "سجل التعديلات" إطلاقًا — وهي بالضبط
# التعديلات التي يُسأل عنها لاحًقا: من أعفى هذا الموظف من الحضور ومتى ولماذا.
CRITICAL_FIELDS = {
    # مالية وتعاقدية
    "basic_salary", "actual_salary", "hire_date", "job_title",
    "contract_type", "contract_start_date", "contract_end_date",
    # الوظيفة الفعلية وساعات الدوام
    "actual_job_title", "work_hours_type", "official_work_hours", "actual_work_hours",
    # إعدادات الحضور — إعفاء موظف من البصم قرار رقابي يجب أن يُسأل عنه
    "attendance_mode", "attendance_exempt", "attendance_exempt_reason", "shift_id",
    # مكان الدوام الرسمي والفعلي
    "branch_id", "actual_branch_id",
}


@router.put("/{emp_id}", response_model=schemas.EmployeeOut)
def update_employee(emp_id: int, data: schemas.EmployeeCreateIn, request: Request,
                    effective_date: date | None = None, change_reason: str | None = None,
                    user: models.User = Depends(require_perm("edit_employee")),
                    db: Session = Depends(get_db)):
    """R3-C — يقبل effective_date اختياري: لو موجود، التغييرات على الحقول الحرجة
    تُسجَّل بتاريخ سريان مستقبلي (مفيد لزيادة راتب تسري الشهر القادم).
    الافتراضي: effective_date = اليوم = تسري فورًا."""
    emp = _get_emp(db, user, emp_id)
    payload = data.model_dump()
    payload.pop("company_id", None)  # لا يُغيَّر انتماء الشركة عبر التعديل العادي
    _assert_no_duplicates(db, emp.company_id, payload.get("civil_id"),
                          payload.get("passport_number"), exclude_id=emp.id)
    _assert_branch_in_scope(db, user, payload.get("branch_id"), payload.get("actual_branch_id"))

    # PERM-02 — إعدادات الحضور تُعدَّل من هنا أيًضا، فتسري عليها نفس ضوابط
    # endpoint السياسة المخصص بدل أن يكون الـPUT بابًا خلفيًا يتخطّاها:
    #  1) SEC2-17 — mode='none' يشترط إعفاًء صريًحا بسبب موثّق
    #  2) فصل الصلاحيات — تغيير سياسة الحضور يستلزم manage_attendance، ولا
    #     يكفي edit_employee وحدها (وإلا صار من يعدّل الأسماء يُعفي من البصم)
    _ATT_FIELDS = ("attendance_mode", "attendance_exempt", "attendance_exempt_reason",
                   "shift_id")
    att_changed = any(getattr(emp, f, None) != payload.get(f) for f in _ATT_FIELDS)
    if att_changed:
        from ..deps import get_user_perms
        from ..permissions import has_permission
        if not has_permission(user.role, get_user_perms(user, db), "manage_attendance"):
            raise HTTPException(
                status_code=403,
                detail="تعديل إعدادات الحضور يتطلب صلاحية إدارة الحضور")
        if payload.get("attendance_mode") == "none" and not (
                payload.get("attendance_exempt")
                and (payload.get("attendance_exempt_reason") or "").strip()):
            raise HTTPException(
                status_code=400,
                detail="نمط 'بدون حضور' يتطلب إعفاًء صريًحا مع سبب موثّق")

    # R3-C — التقاط snapshot قبل + تسجيل التغييرات الحرجة في جدول التاريخ
    eff = effective_date or kuwait_today()
    for k, v in payload.items():
        old = getattr(emp, k, None)
        if k in CRITICAL_FIELDS and old != v:
            db.add(models.EmployeeFieldChange(
                company_id=emp.company_id, employee_id=emp.id, field_name=k,
                old_value=None if old is None else str(old),
                new_value=None if v is None else str(v),
                effective_date=eff, changed_by=user.id, reason=change_reason,
            ))
        setattr(emp, k, v)
    audit(db, user, "update_employee", "employee", emp.id, request=request)
    db.commit()
    db.refresh(emp)
    return emp


@router.get("/{emp_id}/change-history")
def employee_change_history(emp_id: int,
                            user: models.User = Depends(require_perm("view_employee")),
                            db: Session = Depends(get_db)):
    """R3-C §4 — سجل التغييرات الحرجة على ملف الموظف (راتب/تعيين/عقد/مسمى).
    يُعرَض بترتيب زمني تنازلي مع تاريخ التسجيل + تاريخ السريان + المُنفِّذ + السبب."""
    from ..deps import assert_role_allowed
    emp = _get_emp(db, user, emp_id)
    # المحاسب يشوف تغييرات الرواتب فقط، PRO لا يشوف شيئًا
    assert_role_allowed(user, {"delegate"}, emp_id,
                       reason="سجل التعديلات لـHR/الإدارة والمحاسب فقط")
    rows = db.scalars(select(models.EmployeeFieldChange).where(
        models.EmployeeFieldChange.employee_id == emp_id,
    ).order_by(models.EmployeeFieldChange.changed_at.desc())).all()
    # تنقية للمحاسب: يشوف الحقول المالية فقط
    is_self = user.employee_id == emp.id
    if user.role == "accountant" and not is_self:
        rows = [r for r in rows if r.field_name in {"basic_salary", "actual_salary"}]
    return [{
        "id": r.id, "field_name": r.field_name,
        "old_value": r.old_value, "new_value": r.new_value,
        "effective_date": r.effective_date.isoformat(),
        "changed_at": r.changed_at.isoformat() + "Z",
        "changed_by": r.changed_by,
        "changed_by_name": (db.get(models.User, r.changed_by).full_name
                            if r.changed_by and db.get(models.User, r.changed_by) else None),
        "reason": r.reason,
    } for r in rows]


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
    """الملف المجمّع: البيانات + الإقامات + المستندات + الخصومات + الإجازات + الحضور.

    R2 §2 — نطاق العرض حسب الدور:
      - المحاسب: بيانات الرواتب فقط (راتب/بدلات/خصومات/إضافي/بنك)؛ يُخفى:
        الجواز، الرقم المدني، العنوان، المستندات الشخصية، الإجازات، الإنذارات، EOS.
      - المندوب (PRO): بيانات حكومية فقط (إقامات/جوازات/تراخيص)؛ يُخفى:
        الراتب، تاريخ التعيين، المسمى الوظيفي، العقد.
    """
    emp = _get_emp(db, user, emp_id)
    # الإقامات/أذونات العمل شأن حكومي → تُعرَض للمندوب/الإدارة العليا فقط
    from ..permissions import has_permission
    from ..deps import get_user_perms
    perms = get_user_perms(user, db)
    is_admin = user.role == "super_admin"
    is_self = user.employee_id == emp.id  # R2 §3 — الموظف يرى ملفه كاملاً حتى لو دوره إداري
    is_accountant = user.role == "accountant" and not is_self
    is_pro = user.role == "delegate" and not is_self
    can_gov = is_admin or has_permission(user.role, perms, "manage_permits")
    can_view_actual = is_admin or has_permission(user.role, perms, "view_actual_salary")
    can_edit_actual = is_admin or has_permission(user.role, perms, "edit_actual_salary")
    # PII (رقم مدني، جواز): يراها بالكامل الموارد البشرية والمندوب فقط، ويُخفى جزئيًا لباقي
    # الأدوار (V1.4 RBAC.Field-Level Permissions). لا يُخفى للموظف نفسه.
    can_view_pii = is_admin or user.role in ("hr", "delegate") or (user.employee_id == emp.id)
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
    from ..masking import mask_civil_id, mask_passport
    emp_out = schemas.EmployeeOut.model_validate(emp).model_dump()
    if not can_view_pii:
        emp_out["civil_id"] = mask_civil_id(emp_out.get("civil_id"))
        emp_out["passport_number"] = mask_passport(emp_out.get("passport_number"))

    # R2-A — المحاسب: يمسح كل الحقول الهوياتية/العقدية من الـpayload
    #        (لا يحتاجها لتشغيل الرواتب — الاسم + الرقم الوظيفي كافيان للتعرّف)
    ACCOUNTANT_STRIP = {
        "civil_id", "passport_number", "passport_expiry", "date_of_birth",
        "address", "nationality", "gender", "marital_status", "email", "phone",
        "personal_photo_path", "health_insurance",
        "contract_type", "contract_start_date", "contract_end_date",
    }
    # R2-B — المندوب (PRO): يمسح الحقول المالية/العقدية
    PRO_STRIP = {
        "basic_salary", "actual_salary", "hire_date", "job_title",
        "contract_type", "contract_start_date", "contract_end_date",
    }
    if is_accountant:
        for k in ACCOUNTANT_STRIP:
            if k in emp_out: emp_out[k] = None
    if is_pro:
        for k in PRO_STRIP:
            if k in emp_out: emp_out[k] = None

    # QA-23 (بسيط) — تبويب نهاية الخدمة كان يظهر فارًغا لمسؤول الفرع: قائمة
    # التبويبات كانت تُشتقّ من view_scope وحده (تسمية دور خشنة) لا من الصلاحيات،
    # فكل من ليس محاسًبا ولا مندوًبا يرى كل التبويبات ثم يصطدم بـ403 داخلها.
    # الخادم هو من يحدّد التبويبات الآن، من الصلاحية نفسها التي يفرضها /eos.
    from ..deps import get_user_perms
    from ..permissions import has_permission

    _doc_type_names = {r.code: r.name for r in db.scalars(select(models.DocumentType)).all()}
    _assigned = get_user_perms(user, db)
    _can_eos = (has_permission(user.role, _assigned, "calculate_eos")
                or has_permission(user.role, _assigned, "terminate_employee"))
    _scope = ("accountant" if is_accountant else "pro" if is_pro else "full")
    _tabs_by_scope = {
        "accountant": ["employment", "history"],
        "pro": ["documents"],
        "full": ["personal", "employment", "documents", "leave", "eos", "warnings", "history"],
    }
    allowed_tabs = [t for t in _tabs_by_scope[_scope] if t != "eos" or _can_eos or is_self]

    return {
        "employee": emp_out,
        "pii_masked": not can_view_pii,
        # R2 §2 — العلامة اللي الفرونت يستخدمها لتخفي التبويبات الممنوعة
        "view_scope": _scope,
        # مصدر واحد للتبويبات: الصلاحيات لا تسمية الدور
        "allowed_tabs": allowed_tabs,
        # الراتب الفعلي يُعرَض/يُعدَّل حسب الصلاحية المالية فقط
        "actual_salary": emp.actual_salary if can_view_actual else None,
        "can_view_actual_salary": can_view_actual,
        "can_edit_actual_salary": can_edit_actual,
        "created_by_name": (db.get(models.User, emp.created_by).full_name
                            if emp.created_by and db.get(models.User, emp.created_by) else None),
        # QA-05 — كل أرقام الرصيد من مصدر واحد بأسماء صريحة. كان الملف يعرض
        # العمود المخزَّن ونهاية الخدمة تحسب المستحق التراكمي، وكلاهما يُسمّى
        # "رصيد الإجازات" — فظهر 30 هنا و92.16 هناك.
        "leave_balance_detail": leave_balance_service.leave_balance(
            db, emp, db.get(models.Company, emp.company_id)),
        # يبقى للتوافق مع أي مستهلك قديم — وهو نفسه usable_days
        "leave_balance": emp.annual_leave_balance,
        "leave_ledger": [
            {"id": x.id, "kind": x.kind, "days": x.days,
             "balance_before": x.balance_before, "balance_after": x.balance_after,
             "leave_type": x.leave_type, "request_id": x.request_id,
             "note": x.note, "created_at": x.created_at}
            for x in db.scalars(
                select(models.LeaveLedger)
                .where(models.LeaveLedger.employee_id == emp.id)
                .order_by(models.LeaveLedger.created_at.desc())
                .limit(100)
            ).all()
        ],
        # مكان الدوام الرسمي/الفعلي — الأعمدة تحفظ المعرّفات، والواجهة تعرض
        # الاسم؛ حلّه هنا يوفّر على كل شاشة جلب قائمة الفروع لتترجم رقًما
        "official_branch_name": (db.get(models.Branch, emp.branch_id).name
                                 if emp.branch_id and db.get(models.Branch, emp.branch_id) else None),
        "actual_branch_name": (db.get(models.Branch, emp.actual_branch_id).name
                               if emp.actual_branch_id
                               and db.get(models.Branch, emp.actual_branch_id) else None),
        # نتيجة نهاية الخدمة المحفوظة (إن وُجدت)
        "saved_eos": (__import__("json").loads(emp.eos_settlement_json)
                      if emp.eos_settlement_json else None),
        "termination_date": emp.termination_date,
        "termination_reason": emp.termination_reason,
        "permits": [
            {"id": p.id, "kind": p.kind, "number": p.number,
             "expiry_date": p.expiry_date, "status": p.status} for p in permits
        ],
        # QA-14 — الاسم البشري من جدول أنواع المستندات لا الكود الخام. الاسم
        # مسجَّل في document_types أصًلا، وكانت الواجهة تطبع الكود لأنه ما وصلها.
        # ونضيف تاريخ الرفع ليفرّق المستخدم بين مستندين بنفس الاسم والإصدار.
        "documents": [
            {"id": d.id, "type": d.document_type_code,
             "type_label": _doc_type_names.get(d.document_type_code, d.document_type_code),
             "title": d.title, "expiry_date": d.expiry_date, "version": d.version,
             "uploaded_at": getattr(d, "created_at", None)} for d in docs
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
    # R2-D — المحاسب/PRO ممنوعان (إنذارات = HR domain)
    from ..deps import assert_role_allowed
    assert_role_allowed(user, {"accountant", "delegate"}, emp_id,
                       reason="الإنذارات/الجزاءات تخص شؤون الموظفين فقط")
    if kind not in EVENT_KINDS:
        raise HTTPException(status_code=400, detail="نوع حدث غير صالح")
    emp = _get_emp(db, user, emp_id)
    # الإنذار لا يُوجَّه لمن هو فوق الشؤون القانونية في التسلسل. الفحص هنا على
    # الخادم لا في الواجهة: إخفاء الزر لا يمنع طلًبا مباشًرا على المسار.
    if kind in ("warning", "penalty"):
        from ..permissions import may_receive_warning
        holder = db.scalar(select(models.User).where(models.User.employee_id == emp.id))
        if holder and not may_receive_warning(holder.role):
            raise HTTPException(
                status_code=403,
                detail="لا يجوز توجيه إنذار أو جزاء لصاحب هذا الدور")
    ev = models.EmployeeEvent(company_id=emp.company_id, employee_id=emp.id, kind=kind,
                              title=title, detail=detail, amount=amount,
                              date=date_val or kuwait_today(), created_by=user.id)
    db.add(ev)
    db.flush()
    audit(db, user, f"employee_{kind}", "employee", emp.id, detail=title, request=request)
    db.commit()
    return {"ok": True, "id": ev.id}


@router.get("/{emp_id}/events")
def list_events(emp_id: int, user: models.User = Depends(require_perm("view_employee")),
                db: Session = Depends(get_db)):
    # R2-D — المحاسب/PRO ممنوعان من رؤية الإنذارات (فصل الواجبات)
    from ..deps import assert_role_allowed
    assert_role_allowed(user, {"accountant", "delegate"}, emp_id,
                       reason="الإنذارات لـHR والإدارة فقط")
    emp = _get_emp(db, user, emp_id)
    rows = db.scalars(select(models.EmployeeEvent).where(
        models.EmployeeEvent.employee_id == emp.id).order_by(models.EmployeeEvent.date.desc())).all()
    return [{"id": e.id, "kind": e.kind, "title": e.title, "detail": e.detail,
             "amount": e.amount, "date": e.date} for e in rows]


# ----------------------------- الخط الزمني (Timeline) -----------------------------

@router.get("/{emp_id}/timeline")
def employee_timeline(emp_id: int, user: models.User = Depends(require_perm("view_employee")),
                      db: Session = Depends(get_db)):
    """سجل زمني موحّد لكل أحداث الموظف (إنشاء، مستندات، إقامات، إجازات، إنذارات...).

    R2-D — يُنقّى المحتوى حسب دور العارض:
      - المحاسب: أحداث الرواتب/المكافآت/الترقيات فقط (بلا مستندات/إجازات/إنذارات)
      - المندوب: مستندات/إقامات فقط (بلا راتب/إجازات)
    """
    emp = _get_emp(db, user, emp_id)
    is_self = user.employee_id == emp.id
    is_accountant = user.role == "accountant" and not is_self
    is_pro = user.role == "delegate" and not is_self
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

    # R2-D — تنقية الـtimeline حسب دور العارض (فصل الواجبات)
    if is_accountant:
        ACC_CATS = {"create", "bonus", "promotion", "penalty"}  # لا مستندات/إقامات/إجازات/إنذارات
        items = [x for x in items if x["category"] in ACC_CATS]
    elif is_pro:
        PRO_CATS = {"create", "document", "permit"}  # لا إجازات/راتب/إنذارات
        items = [x for x in items if x["category"] in PRO_CATS]
    items.sort(key=lambda x: x["at"], reverse=True)
    return {"employee": {"id": emp.id, "name": emp.name, "status": emp.status}, "timeline": items}


# ----------------------------- إنهاء الخدمة (PILOT-P0-8) -----------------------------
# دورة إنهاء الخدمة الآمنة (منع التنفيذ الفوري):
#   1) HR يحضّر مسودة عبر POST /terminate            → status لا يتغير، مسودة في pending_termination_json
#   2) المحاسب يعتمد عبر POST /terminate/approve     → لا يزال pending، فقط توثيق سلطة مالية
#   3) HR/المحاسب ينفّذ عبر POST /terminate/execute   → هنا فقط يصبح status="terminated"
#   إمكانية POST /terminate/cancel لإلغاء مسودة معلّقة قبل التنفيذ.
#
# قواعد الرفض (bad inputs):
# - hire_date غير موجود / السبب غير معروف / basic_salary ≤ 0 / end_date < hire_date
# - الموظف مؤرشف/منتهي/عليه مسودة معلقة سابقة (لا يُسمح بتحضيرين متوازيين)
# - المُعتمِد لا يجوز أن يكون هو نفسه المُحضِّر (فصل السلطات)

def _validate_termination_inputs(emp: models.Employee, end_date: date, reason: str) -> None:
    if not emp.hire_date:
        raise HTTPException(status_code=400,
                            detail="لا يمكن حساب المكافأة: تاريخ التعيين غير مُسجّل للموظف")
    if reason not in eos_engine.TERMINATION_REASONS:
        raise HTTPException(status_code=400,
                            detail=f"سبب إنهاء غير معتمد: {reason}")
    if end_date < emp.hire_date:
        raise HTTPException(status_code=400,
                            detail="تاريخ الإنهاء يسبق تاريخ التعيين")
    if not emp.basic_salary or float(emp.basic_salary) <= 0:
        raise HTTPException(status_code=400,
                            detail="الراتب الأساسي للموظف غير محدد أو ≤ 0 — لا يمكن حساب المكافأة")


@router.post("/{emp_id}/terminate")
def prepare_termination(emp_id: int, end_date: date, reason: str = "termination",
                        used_leave_days: int = 0, request: Request = None,
                        user: models.User = Depends(require_perm("terminate_employee")),
                        db: Session = Depends(get_db)):
    """PILOT-P0-8 — تحضير مسودة إنهاء الخدمة (لا فصل فوري).

    HR يحسب المكافأة ويخزنها كمسودة. تحتاج اعتماد المحاسب + تنفيذ منفصل قبل تغيير الحالة.
    """
    import json
    emp = _get_emp(db, user, emp_id)
    if emp.status == "terminated":
        raise HTTPException(status_code=409, detail="خدمة الموظف منتهية بالفعل")
    if emp.status == "archived":
        raise HTTPException(status_code=409, detail="الموظف مؤرشف — لا يمكن إنهاء خدمته")
    if emp.pending_termination_json:
        raise HTTPException(status_code=409,
                            detail="يوجد مسودة إنهاء خدمة معلقة — الغِها أولاً قبل تحضير غيرها")
    # P6-27 — وكل باب كان يحرس نفسه ويجهل الآخرَين. الشرط أعلاه يمنع
    # مسودتين، ولا يمنع مسودًة بجانب حالة نهاية خدمة أو طلب REQEOS —
    # قِستُه ففُتحت الثلاثة للموظف نفسه بثلاثة تواريخ وحسابين.
    exit_guard.assert_single_exit(db, emp.id)
    if used_leave_days is not None and used_leave_days < 0:
        raise HTTPException(status_code=400, detail="أيام الإجازة المستهلكة لا يمكن أن تكون سالبة")
    _validate_termination_inputs(emp, end_date, reason)
    company = db.get(models.Company, emp.company_id)
    try:
        settlement = eos_engine.calculate_eos(
            basic_salary=emp.basic_salary, hire_date=emp.hire_date, end_date=end_date,
            reason=reason, contract_type=emp.contract_type,
            used_leave_days=used_leave_days, annual_leave_days=company.annual_leave_days,
            day_divisor=company.eos_day_divisor, max_months=company.eos_max_months)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    settlement["_end_date"] = str(end_date)
    settlement["_reason"] = reason
    emp.pending_termination_json = json.dumps(settlement, ensure_ascii=False)
    emp.pending_termination_prepared_by = user.id
    emp.pending_termination_prepared_at = datetime.utcnow()
    emp.pending_termination_approved_by = None
    emp.pending_termination_approved_at = None
    audit(db, user, "prepare_termination", "employee", emp.id,
          detail=f"{reason} @ {end_date} = {settlement['total_settlement']} KWD (draft)",
          request=request)
    db.commit()
    return {"ok": True, "employee_id": emp.id, "status": emp.status,
            "stage": "prepared", "settlement": settlement}


@router.post("/{emp_id}/terminate/approve")
def approve_termination(emp_id: int, request: Request = None,
                        user: models.User = Depends(require_perm("approve_termination")),
                        db: Session = Depends(get_db)):
    """PILOT-P0-8 — اعتماد المسودة (يشترط مختلف المُحضِّر)."""
    emp = _get_emp(db, user, emp_id)
    if not emp.pending_termination_json:
        raise HTTPException(status_code=404, detail="لا توجد مسودة إنهاء خدمة معلقة")
    if emp.pending_termination_prepared_by == user.id and user.role != "super_admin":
        raise HTTPException(status_code=403,
                            detail="لا يمكن اعتماد مسودة حضّرتها بنفسك — فصل السلطات إلزامي")
    emp.pending_termination_approved_by = user.id
    emp.pending_termination_approved_at = datetime.utcnow()
    audit(db, user, "approve_termination", "employee", emp.id,
          detail="approved for execution", request=request)
    db.commit()
    return {"ok": True, "employee_id": emp.id, "stage": "approved"}


@router.post("/{emp_id}/terminate/clearance")
def clearance_termination(emp_id: int, request: Request = None,
                          clearance_note: str | None = None,
                          user: models.User = Depends(require_perm("terminate_employee")),
                          db: Session = Depends(get_db)):
    """V2.2 §13 — إخلاء الطرف: تأكيد أن الموظف سلم عهدته وأخلى مسؤولياته
    (يأتي بعد approve وقبل execute).
    """
    emp = _get_emp(db, user, emp_id)
    if not emp.pending_termination_json:
        raise HTTPException(status_code=404, detail="لا توجد مسودة إنهاء خدمة")
    if not emp.pending_termination_approved_at:
        raise HTTPException(status_code=409, detail="المسودة غير معتمدة — يشترط approve أولاً")
    emp.pending_termination_cleared_by = user.id
    emp.pending_termination_cleared_at = datetime.utcnow()
    emp.pending_termination_clearance_note = (clearance_note or "").strip() or None
    audit(db, user, "termination_clearance", "employee", emp.id,
          detail=(clearance_note or "cleared")[:200], request=request)
    db.commit()
    return {"ok": True, "employee_id": emp.id, "stage": "cleared"}


@router.post("/{emp_id}/terminate/acknowledge")
def acknowledge_termination(emp_id: int, request: Request = None,
                            user: models.User = Depends(get_current_user),
                            db: Session = Depends(get_db)):
    """V2.2 §13 — إقرار الموظف بالتسوية (يقر بموافقته على أرقام EOS).
    يستدعيها الموظف نفسه أو HR نيابة عنه بتفويض واضح في audit."""
    emp = _get_emp(db, user, emp_id)
    if not emp.pending_termination_json:
        raise HTTPException(status_code=404, detail="لا توجد مسودة إنهاء خدمة")
    if not emp.pending_termination_cleared_at:
        raise HTTPException(status_code=409, detail="يشترط إتمام إخلاء الطرف أولاً")
    # لو الموظف نفسه أو HR
    is_own = user.employee_id == emp.id
    is_hr = user.role in ("hr", "super_admin", "company_manager")
    if not (is_own or is_hr):
        raise HTTPException(status_code=403,
                            detail="فقط الموظف أو HR يمكنه إقرار التسوية")
    emp.pending_termination_acknowledged_at = datetime.utcnow()
    audit(db, user, "termination_acknowledged", "employee", emp.id,
          detail=f"by {'self' if is_own else 'hr:'+str(user.id)}", request=request)
    db.commit()
    return {"ok": True, "employee_id": emp.id, "stage": "acknowledged"}


@router.post("/{emp_id}/terminate/execute")
def execute_termination(emp_id: int, request: Request = None,
                        user: models.User = Depends(require_perm("terminate_employee")),
                        db: Session = Depends(get_db)):
    """PILOT-P0-8 — تنفيذ الإنهاء بعد الاعتماد + إخلاء الطرف + إقرار الموظف.
    V2.2 §13: كل الـstages التمهيدية إجبارية قبل التنفيذ."""
    import json
    emp = _get_emp(db, user, emp_id)
    if emp.status == "terminated":
        raise HTTPException(status_code=409, detail="خدمة الموظف منتهية بالفعل")
    if not emp.pending_termination_json:
        raise HTTPException(status_code=404, detail="لا توجد مسودة إنهاء خدمة")
    if not emp.pending_termination_approved_at:
        raise HTTPException(status_code=409, detail="المسودة غير معتمدة بعد — لا يمكن تنفيذها")
    # V2.2 §13 — نطلب الـstages التمهيدية (مع تخفيف لل super_admin كحالة طارئة)
    if user.role != "super_admin":
        if not emp.pending_termination_cleared_at:
            raise HTTPException(status_code=409, detail="يشترط إخلاء الطرف قبل التنفيذ")
        if not emp.pending_termination_acknowledged_at:
            raise HTTPException(status_code=409, detail="يشترط إقرار الموظف قبل التنفيذ")
    settlement = json.loads(emp.pending_termination_json)
    end_date = settlement.pop("_end_date", None)
    reason = settlement.pop("_reason", "termination")
    emp.status = "terminated"
    emp.termination_date = date.fromisoformat(end_date) if end_date else kuwait_today()
    emp.termination_reason = reason
    emp.eos_settlement_json = json.dumps(settlement, ensure_ascii=False)
    emp.pending_termination_json = None
    emp.pending_termination_prepared_by = None
    emp.pending_termination_prepared_at = None
    emp.pending_termination_approved_by = None
    emp.pending_termination_approved_at = None
    emp.pending_termination_cleared_by = None
    emp.pending_termination_cleared_at = None
    emp.pending_termination_clearance_note = None
    emp.pending_termination_acknowledged_at = None
    audit(db, user, "terminate_employee", "employee", emp.id,
          detail=f"{reason} @ {end_date} = {settlement['total_settlement']} KWD (executed)",
          request=request)
    db.commit()
    return {"ok": True, "employee_id": emp.id, "status": "terminated",
            "stage": "executed", "settlement": settlement}


@router.post("/{emp_id}/terminate/cancel")
def cancel_termination(emp_id: int, request: Request = None,
                       user: models.User = Depends(require_perm("terminate_employee")),
                       db: Session = Depends(get_db)):
    """PILOT-P0-8 — إلغاء المسودة قبل التنفيذ."""
    emp = _get_emp(db, user, emp_id)
    if not emp.pending_termination_json:
        raise HTTPException(status_code=404, detail="لا توجد مسودة معلقة لإلغائها")
    emp.pending_termination_json = None
    emp.pending_termination_prepared_by = None
    emp.pending_termination_prepared_at = None
    emp.pending_termination_approved_by = None
    emp.pending_termination_approved_at = None
    emp.pending_termination_cleared_by = None
    emp.pending_termination_cleared_at = None
    emp.pending_termination_clearance_note = None
    emp.pending_termination_acknowledged_at = None
    audit(db, user, "cancel_termination_draft", "employee", emp.id, request=request)
    db.commit()
    return {"ok": True, "stage": "cancelled"}


# ----------------------------- Employee ID Backfill (§6) -----------------------------

@router.post("/backfill-employee-no")
def backfill_employee_numbers(company_id: int | None = None, request: Request = None,
                              user: models.User = Depends(require_perm("manage_users")),
                              db: Session = Depends(get_db)):
    """V2.2 §6 — يعطي employee_no لأي موظف قديم بدون رقم داخل الشركة.
    Idempotent — الموظفين اللي عندهم رقم بالفعل ما يتغيروا."""
    from .. import employee_no as _en
    cid = scope_company_id(user, company_id)
    count = _en.backfill_missing(db, company_id=cid)
    audit(db, user, "backfill_employee_no", "company", cid or 0,
          detail=f"count={count}", request=request)
    db.commit()
    return {"ok": True, "backfilled": count}


# ----------------------------- سياسة الحضور (SEC2-17) -----------------------------

@router.post("/{emp_id}/attendance-policy")
def set_attendance_policy(emp_id: int, mode: str, exempt: bool = False,
                          exempt_reason: str | None = None,
                          request: Request = None,
                          user: models.User = Depends(require_perm("manage_attendance")),
                          db: Session = Depends(get_db)):
    """SEC2-17 — تعيين سياسة حضور صريحة لموظف (HR أو مسؤول حضور).

    القاعدة:
      - mode ∈ {qr, gps, both} → attendance_exempt=False
      - mode='none' → يشترط exempt=True + exempt_reason ≠ فارغ (توثيق صريح)
    """
    if mode not in ("none", "qr", "gps", "both"):
        raise HTTPException(status_code=400, detail="نمط حضور غير صالح")
    emp = _get_emp(db, user, emp_id)
    if mode == "none":
        if not exempt or not (exempt_reason and exempt_reason.strip()):
            raise HTTPException(
                status_code=400,
                detail="mode='none' يتطلب exempt=True + سبب موثّق (attendance_exempt_reason)",
            )
    before = f"{emp.attendance_mode}/exempt={emp.attendance_exempt}"
    emp.attendance_mode = mode
    emp.attendance_exempt = bool(exempt)
    emp.attendance_exempt_reason = (exempt_reason or "").strip() or None if exempt else None
    emp.attendance_exempt_approved_by = user.id if exempt else None
    emp.attendance_exempt_approved_at = datetime.utcnow() if exempt else None
    after = f"{emp.attendance_mode}/exempt={emp.attendance_exempt}"
    audit(db, user, "set_attendance_policy", "employee", emp.id,
          detail=f"{before} → {after}", request=request)
    db.commit()
    return {"ok": True, "employee_id": emp.id, "mode": emp.attendance_mode,
            "exempt": emp.attendance_exempt, "reason": emp.attendance_exempt_reason}


@router.get("/attendance-policy/pending")
def list_employees_without_policy(company_id: int | None = None,
                                  user: models.User = Depends(require_perm("view_attendance")),
                                  db: Session = Depends(get_db)):
    """SEC2-17 — قائمة الموظفين الـactive الذين لم تُثبَّت لهم سياسة حضور صريحة.
    (mode='none' AND attendance_exempt=False) — للـHR للمعالجة قبل قفل الحضور/الرواتب.
    """
    from sqlalchemy import and_, or_
    cid = scope_company_id(user, company_id)
    q = select(models.Employee).where(
        models.Employee.status == "active",
        models.Employee.attendance_mode == "none",
        or_(models.Employee.attendance_exempt.is_(False),
            models.Employee.attendance_exempt.is_(None)),
    )
    if cid is not None:
        q = q.where(models.Employee.company_id == cid)
    rows = db.scalars(q.order_by(models.Employee.name)).all()
    return [{"id": e.id, "name": e.name, "employee_no": e.employee_no,
             "company_id": e.company_id, "branch_id": e.branch_id,
             "hire_date": e.hire_date} for e in rows]


# =============================================================================
# R7-G §4 — Salary Change Approval Workflow (maker-checker)
# HR/Manager يقترح، Manager/Owner/super_admin يعتمد. المُقترِح ≠ المُعتمِد.
# =============================================================================
CHANGEABLE_FIELDS = {"basic_salary", "actual_salary", "hire_date", "job_title",
                    "contract_type"}

#: تسمية بشرية لكل حقل — بلاغ يقول ``basic_salary`` يخاطب الجدول لا
#: القارئ. وهو درس QA-14 نفسه: الاسم لا الكود. (قِستُه في المتصفّح:
#: عنوان المهمة ظهر بالعمود الخام.)
_FIELD_LABEL = {
    "basic_salary": "الراتب الأساسي",
    "actual_salary": "الراتب الفعلي",
    "hire_date": "تاريخ التعيين",
    "job_title": "المسمى الوظيفي",
    "contract_type": "نوع العقد",
}


@router.post("/{emp_id}/salary-change-request", status_code=201)
def propose_salary_change(emp_id: int, field_name: str, new_value: str,
                          effective_date: date, reason: str,
                          request: Request = None,
                          user: models.User = Depends(require_perm("edit_employee")),
                          db: Session = Depends(get_db)):
    """R7-G — يقترح تغييرًا على حقل حرج (راتب/تاريخ تعيين/عقد). الحالة تصبح pending
    بانتظار اعتماد مستخدم آخر. لا يُطبَّق على الموظف حتى الاعتماد."""
    if field_name not in CHANGEABLE_FIELDS:
        raise HTTPException(status_code=400,
                          detail=f"لا يمكن اقتراح تغيير على '{field_name}' — الحقول المسموحة: {sorted(CHANGEABLE_FIELDS)}")
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="سبب التغيير إلزامي")
    emp = _get_emp(db, user, emp_id)
    old = getattr(emp, field_name, None)
    req = models.SalaryChangeRequest(
        company_id=emp.company_id, employee_id=emp.id,
        field_name=field_name,
        old_value=None if old is None else str(old),
        new_value=new_value,
        effective_date=effective_date,
        reason=reason.strip(),
        proposed_by=user.id,
    )
    db.add(req)
    db.flush()

    # **اقتراح لا يعلم به أحد ورقة في درج.**
    #
    # كان يُسجَّل ويُدقَّق ثم يصمت: لا بلاغ ولا طابور، والقائمة الوحيدة
    # داخل ملف الموظف. فلا يعلم المعتمِد إلا إن فتح ذلك الملف مصادفًة —
    # وراتب ينتظر اعتماًدا لا يجده أحد يبقى معلًَّقا إلى الأبد.
    #
    # والمبلَّغون هم من يملك القرار فعًلا (انظر ``decide_salary_change``):
    # بلاغ لمن لا يملك الإجراء خبر لا عمل.
    from ..notifications import create_task, users_by_role

    for u in users_by_role(db, emp.company_id,
                           ["company_manager", "company_owner"]):
        if u.id == user.id:
            continue  # فصل الواجبات: المقترِح لا يعتمد اقتراحه
        create_task(
            db, company_id=emp.company_id, type="approvals",
            assignee_user_id=u.id,
            title=f"اعتماد تغيير حقل حرج: {_FIELD_LABEL.get(field_name, field_name)}",
            detail=(f"{emp.name} — {_FIELD_LABEL.get(field_name, field_name)}: "
                    f"{old} ← {new_value} "
                    f"(اعتباًرا من {effective_date}). السبب: {reason.strip()}"),
            related_entity_type="employee", related_entity_id=emp.id,
            severity="warning", dedup_key=f"salary_change:{req.id}",
        )

    audit(db, user, "propose_salary_change", "employee", emp.id,
          detail=f"{field_name}: {old} → {new_value}", request=request)
    db.commit()
    return {"ok": True, "request_id": req.id, "status": "pending"}


def _close_change_tasks(db: Session, req: models.SalaryChangeRequest) -> None:
    """يغلق بلاغ الاعتماد بعد القرار.

    ومهمة تبقى مفتوحة بعد انتهاء عملها تُعلّم قارئها أن الصندوق يكذب
    فيتوقّف عن قراءته — وهو الدرس نفسه من ``_close_open_tasks``.
    """
    for t in db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "employee",
            models.Task.related_entity_id == req.employee_id,
            models.Task.status.in_(("open", "in_progress")),
    )).all():
        if (t.dedup_key or "") == f"salary_change:{req.id}":
            t.status = "done"


@router.get("/{emp_id}/salary-change-requests")
def list_salary_change_requests(emp_id: int,
                                user: models.User = Depends(require_perm("view_employee")),
                                db: Session = Depends(get_db)):
    _get_emp(db, user, emp_id)  # scope check
    rows = db.scalars(select(models.SalaryChangeRequest).where(
        models.SalaryChangeRequest.employee_id == emp_id,
    ).order_by(models.SalaryChangeRequest.proposed_at.desc())).all()
    return [{
        "id": r.id, "field_name": r.field_name,
        "old_value": r.old_value, "new_value": r.new_value,
        "effective_date": r.effective_date.isoformat(),
        "reason": r.reason, "status": r.status,
        "proposed_by": r.proposed_by,
        "proposed_by_name": (db.get(models.User, r.proposed_by).full_name
                            if r.proposed_by and db.get(models.User, r.proposed_by) else None),
        "proposed_at": r.proposed_at.isoformat() + "Z",
        "approved_by": r.approved_by,
        "approved_by_name": (db.get(models.User, r.approved_by).full_name
                            if r.approved_by and db.get(models.User, r.approved_by) else None),
        "approved_at": r.approved_at.isoformat() + "Z" if r.approved_at else None,
        "rejected_reason": r.rejected_reason,
    } for r in rows]


@router.get("/salary-change-requests/pending")
def pending_salary_changes(user: models.User = Depends(require_perm("view_employee")),
                           db: Session = Depends(get_db)):
    """المعلَّق من تغييرات الحقول الحرجة في الشركة — طابور المعتمِد.

    **ولماذا لزم**: القائمة الوحيدة كانت داخل ملف الموظف، فمن يملك
    القرار لا يجد ما ينتظره إلا بفتح الملفات واحًدا واحًدا. والبلاغ
    يقول إن هناك عًملا؛ وهذه تقول **ما هو** مجموًعا.
    """
    cid = user.company_id
    q = select(models.SalaryChangeRequest).where(
        models.SalaryChangeRequest.status == "pending")
    if cid is not None:
        q = q.where(models.SalaryChangeRequest.company_id == cid)
    rows = db.scalars(q.order_by(
        models.SalaryChangeRequest.proposed_at.desc())).all()
    out = []
    for r in rows:
        emp = db.get(models.Employee, r.employee_id)
        who = db.get(models.User, r.proposed_by) if r.proposed_by else None
        out.append({
            "id": r.id, "employee_id": r.employee_id,
            "employee_name": emp.name if emp else None,
            "field_name": r.field_name,
            "old_value": r.old_value, "new_value": r.new_value,
            "effective_date": r.effective_date.isoformat(),
            "reason": r.reason,
            "proposed_by": r.proposed_by,
            "proposed_by_name": who.full_name if who else None,
            "proposed_at": r.proposed_at.isoformat() + "Z",
        })
    return out


@router.post("/salary-change-requests/{req_id}/decide")
def decide_salary_change(req_id: int, decision: str, request: Request = None,
                        note: str | None = None,
                        user: models.User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """R7-G §4 — يعتمد أو يرفض. المُقترِح لا يقدر يعتمد نفسه (فصل واجبات)."""
    if decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="القرار: approved أو rejected")
    req = db.get(models.SalaryChangeRequest, req_id)
    if not req:
        raise HTTPException(status_code=404, detail="طلب التغيير غير موجود")
    if req.status != "pending":
        raise HTTPException(status_code=409,
                          detail=f"الطلب مغلق (الحالة: {req.status}) — لا يمكن اتخاذ قرار جديد")
    # المُعتمِد لازم يكون مدير الشركة/صاحبها/الإدارة العليا
    if user.role not in ("company_manager", "company_owner", "super_admin"):
        raise HTTPException(status_code=403,
                          detail="اعتماد تغييرات الرواتب لمدير الشركة/الإدارة العليا فقط")
    # فصل الواجبات: المُقترِح ≠ المُعتمِد
    if req.proposed_by == user.id and user.role != "super_admin":
        raise HTTPException(status_code=403,
                          detail="لا يمكنك اعتماد اقتراح قدّمته بنفسك (فصل الواجبات)")
    # scope check
    assert_same_company(user, req.company_id, db=db)

    if decision == "rejected":
        req.status = "rejected"
        req.rejected_reason = (note or "").strip() or None
        req.approved_by = user.id  # نسجل من رفض
        req.approved_at = datetime.utcnow()
        _close_change_tasks(db, req)
        audit(db, user, "reject_salary_change", "employee", req.employee_id,
              detail=f"{req.field_name} rejected: {req.rejected_reason}", request=request)
        db.commit()
        return {"ok": True, "status": "rejected"}

    # approved → طبّق التغيير + سجّل EmployeeFieldChange نهائي + قفل الطلب
    emp = db.get(models.Employee, req.employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    # convert new_value حسب نوع الحقل
    coerced = req.new_value
    if req.field_name in ("basic_salary", "actual_salary"):
        try:
            coerced = float(req.new_value)
        except ValueError:
            raise HTTPException(status_code=400, detail="قيمة رقمية غير صالحة")
    elif req.field_name == "hire_date":
        try:
            coerced = date.fromisoformat(req.new_value)
        except ValueError:
            raise HTTPException(status_code=400, detail="تاريخ غير صالح")
    setattr(emp, req.field_name, coerced)
    # قيّد التاريخ نهائيًا في EmployeeFieldChange
    change = models.EmployeeFieldChange(
        company_id=emp.company_id, employee_id=emp.id,
        field_name=req.field_name,
        old_value=req.old_value, new_value=req.new_value,
        effective_date=req.effective_date, changed_by=user.id,
        reason=f"[approval #{req.id}] {req.reason}",
    )
    db.add(change)
    db.flush()
    req.status = "applied"
    req.approved_by = user.id
    req.approved_at = datetime.utcnow()
    req.applied_change_id = change.id
    _close_change_tasks(db, req)
    audit(db, user, "apply_salary_change", "employee", emp.id,
          detail=f"{req.field_name}: {req.old_value} → {req.new_value} (approved)",
          request=request)
    db.commit()
    return {"ok": True, "status": "applied", "change_id": change.id}


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


# ==========================================================================
# R9 — تعيين جديد: توليد العقد الحكومي + عقد الشركة (New Hire flow)
# ==========================================================================
# القاعدة الحاكمة: عند التعيين نحتاج عقدين — عقد الشركة (COMPANY-CONTRACT-HIRE)
# وعقد حكومي (GOV-CONTRACT-HIRE). العقدين يُطبعا للتوقيع ثم تُرفَع النسخ الموقّعة
# لملف الموظف. البيانات تُملأ من مصدر السلطة (لا تعديل من الفورم).

def _generate_hire_contract(db: Session, user: models.User, request: Request,
                            emp: models.Employee, tpl_code: str, title_ar: str,
                            format: str = "html"):
    """داخلي: يولّد عقد بكود template محدد ويحفظه كـissued document على الموظف.

    format='html' → dict فيه HTML للطباعة عبر المتصفح (رد JSON)
    format='pdf'  → FileResponse مباشرة (R9 §5)
    """
    import hashlib
    import os
    from ..config import settings
    from .templates import _resolve_authoritative_data, _fill_html, _generate_reference_no

    tpl = db.scalar(select(models.DocumentTemplate).where(
        models.DocumentTemplate.code == tpl_code,
        models.DocumentTemplate.is_active == True,  # noqa: E712
    ))
    if not tpl:
        raise HTTPException(status_code=404, detail=(
            f"قالب العقد ({tpl_code}) غير موجود. لإضافته: /templates → إنشاء قالب "
            f"جديد بهذا الكود مع placeholders {{employee_name}}، {{civil_id}}، "
            f"{{basic_salary}}، {{company_name}}، {{date_today}}، {{ref_no}}."
        ))

    ctx = _resolve_authoritative_data(db, emp, extras={})
    reference_no = _generate_reference_no(db, tpl_code, emp.company_id, tpl.version or 1)
    ctx["ref_no"] = reference_no
    rendered = _fill_html(tpl, ctx)

    # R9 §5 — pdf output لو مطلوب
    is_pdf = (format or "").lower() == "pdf"
    if is_pdf:
        from ..pdf_export import render_html_contract_pdf
        company = db.get(models.Company, emp.company_id)
        content_bytes = render_html_contract_pdf(
            rendered, title=f"{title_ar} — {emp.name}",
            subtitle=(company.name if company else ""), reference_no=reference_no,
        )
        mime = "application/pdf"; ext = "pdf"
    else:
        content_bytes = rendered.encode("utf-8")
        mime = "text/html"; ext = "html"
    checksum = hashlib.sha256(content_bytes).hexdigest()

    # AWS-01 — عبر طبقة التخزين. المفتاح محدَّد لأن الرقم المرجعي جزء
    # من هويّة العقد: إعادة التوليد تكتب فوق نسخته لا تُنشئ يتيمة ثانية.
    safe_ref = reference_no.replace("/", "_")
    fpath = save_at_key(content_bytes, f"hire_contracts/{safe_ref}.{ext}")

    doc_type_code = f"{tpl_code.lower().replace('-', '_')}_{emp.id}"
    # FIX — versioning: كل توليد جديد يأخذ version+1 ويُنزّل السابق من is_current.
    # قبل الإصلاح كان كل توليد يكتب version=1 و is_current=True بلا تنزيل السابق،
    # فينتج عدة نسخ "حالية" لنفس العقد وتاريخ نسخ يرجع دائمًا لـv1.
    prev = db.scalars(select(models.Document).where(
        models.Document.entity_type == "employee",
        models.Document.entity_id == emp.id,
        models.Document.document_type_code == doc_type_code,
    )).all()
    next_version = max((d.version for d in prev), default=0) + 1
    for d in prev:
        d.is_current = False

    doc = models.Document(
        company_id=emp.company_id, entity_type="employee", entity_id=emp.id,
        document_type_code=doc_type_code,
        title=f"{title_ar} — {emp.name}",
        file_path=fpath, mime=mime,
        version=next_version, is_current=True, uploaded_by=user.id,
        is_issued=True, reference_no=reference_no,
        template_version=tpl.version or 1, checksum_sha256=checksum,
        generated_at=datetime.utcnow(), generated_by=user.id,
    )
    db.add(doc)
    db.flush()
    audit(db, user, "generate_hire_contract", "employee", emp.id,
          detail=f"{tpl_code} → {reference_no} ({ext})", request=request,
          company_id=emp.company_id)
    if is_pdf:
        from fastapi.responses import FileResponse
        return file_response(fpath, filename=f"{safe_ref}.pdf", media_type=mime)
    return {
        "ok": True, "html": rendered,
        "document_id": doc.id, "reference_no": reference_no,
        "checksum_sha256": checksum, "template_code": tpl_code,
    }


@router.post("/{emp_id}/gov-contract/generate")
def generate_employee_gov_contract(emp_id: int, request: Request,
                                   format: str = "html",
                                   user: models.User = Depends(require_perm("upload_documents")),
                                   db: Session = Depends(get_db)):
    """R9 — يُولّد العقد الحكومي للتعيين (GOV-CONTRACT-HIRE) بيانات الموظف تلقائيًا.
    يُحفظ كـissued document على الموظف مع reference_no وchecksum.
    format=pdf يُعيد FileResponse مباشرة (R9 §5)."""
    emp = _get_emp(db, user, emp_id)
    result = _generate_hire_contract(db, user, request, emp,
                                     "GOV-CONTRACT-HIRE", "العقد الحكومي — تعيين",
                                     format=format)
    db.commit()
    return result


@router.post("/{emp_id}/company-contract/generate")
def generate_employee_company_contract(emp_id: int, request: Request,
                                      format: str = "html",
                                      user: models.User = Depends(require_perm("upload_documents")),
                                      db: Session = Depends(get_db)):
    """R9 — يُولّد عقد العمل بين الشركة والعامل (COMPANY-CONTRACT-HIRE).
    format=pdf يُعيد FileResponse مباشرة."""
    emp = _get_emp(db, user, emp_id)
    result = _generate_hire_contract(db, user, request, emp,
                                     "COMPANY-CONTRACT-HIRE", "عقد العمل",
                                     format=format)
    db.commit()
    return result
