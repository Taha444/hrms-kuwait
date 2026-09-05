# -*- coding: utf-8 -*-
"""مكافأة نهاية الخدمة: حاسبة + دورة حياة كاملة بفصل السلطات (QA §6)."""
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..clock import today as kuwait_today
from .. import eos as eos_engine
from .. import models, schemas
from ..database import get_db
from .. import exit_case, exit_guard
from ..deps import (assert_same_company, audit, get_current_user, require_perm,
                    require_super_admin)

router = APIRouter(prefix="/eos", tags=["eos"])


@router.get("/reasons")
def reasons():
    return eos_engine.TERMINATION_REASONS


@router.post("/calculate")
def calculate(data: schemas.EosIn,
              user: models.User = Depends(require_super_admin)):
    """P0-#9 — حاسبة حرّة (test-only). super_admin فقط.

    ⚠ ليست للتسويات الفعلية — النتيجة لا تُحفظ ولا تُنسب لأي موظف.
    للتسويات الرسمية استخدم /eos/for-employee بمعرّف موظف حقيقي.
    """
    try:
        result = eos_engine.calculate_eos(
            basic_salary=data.basic_salary, hire_date=data.hire_date, end_date=data.end_date,
            reason=data.reason, contract_type=data.contract_type,
            used_leave_days=data.used_leave_days, annual_leave_days=data.annual_leave_days,
            day_divisor=data.day_divisor or 26, max_months=data.max_months or 18,
        )
        result["warning"] = ("هذه حاسبة اختبار فقط — بدون موظف. "
                          "للتسويات الرسمية استخدم /eos/for-employee.")
        result["is_test_only"] = True
        return result
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
    assert_same_company(user, emp.company_id, db=db)
    if not emp.hire_date:
        raise HTTPException(status_code=400, detail="تاريخ التعيين غير مُسجّل")
    company = db.get(models.Company, emp.company_id)
    end = as_of or kuwait_today()
    _, _, _, _, decimal_years = eos_engine.service_breakdown(emp.hire_date, end)
    per_year = float(company.annual_leave_days or 30)
    accrued = round(per_year * decimal_years, 2)
    remaining = round(accrued - float(consumed_days or 0), 2)
    # تحذير صريح بدل رصيد سالب بلا تفسير (QA-P2-EOS-02)
    advance_note = (
        f"استهلك {abs(remaining)} يوم إجازة أكثر من رصيده المستحق (سلفة إجازة) — "
        "يلزم قرار وسياسة موثقة من الإدارة قبل أي خصم."
    ) if remaining < 0 else None
    return {
        "employee_id": emp.id, "name": emp.name,
        "service_years": round(decimal_years, 2),
        "annual_days_per_year": per_year,
        "accrued_days": accrued,
        "consumed_days": float(consumed_days or 0),
        "remaining_days": remaining,
        "advance_note": advance_note,
        "as_of": end.isoformat(),
    }


@router.post("/for-employee")
def for_employee(data: schemas.EosForEmployeeIn,
                 user: models.User = Depends(require_perm("calculate_eos")),
                 db: Session = Depends(get_db)):
    emp = db.get(models.Employee, data.employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    assert_same_company(user, emp.company_id, db=db)
    company = db.get(models.Company, emp.company_id)
    try:
        result = eos_engine.calculate_eos(
            basic_salary=emp.basic_salary, hire_date=emp.hire_date, end_date=data.end_date,
            reason=data.reason, contract_type=emp.contract_type,
            used_leave_days=data.used_leave_days, annual_leave_days=company.annual_leave_days,
            day_divisor=company.eos_day_divisor, max_months=company.eos_max_months,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result["employee"] = {"id": emp.id, "name": emp.name, "job_title": emp.job_title}
    # V2.2 §30 (DOC-13) — حسبة مبدئية لا أمر صرف.
    #
    # ROOT CAUSE: الحاسبة تُعيد رقًما نهائي الشكل بلا وسم، فيُنسخ في رسالة أو
    # يُطبع ويُقرأ التزاًما بالدفع — بينما هو تقدير قبل إخلاء الطرف وقبل خصم
    # العهد. الرقم الصحيح في سياق خاطئ يصير وعًدا لا يملك أحد الوفاء به.
    result["is_preliminary"] = True
    result["not_for_payment"] = True
    result["disclaimer"] = (
        "حسبة مبدئية غير صالحة للصرف — تصبح نهائية بعد إخلاء الطرف واعتماد "
        "التسوية. لا رقم صرف ولا مرجع دفع مرتبط بها."
    )
    return result


# ==========================================================================
# QA §6 — دورة حياة إنهاء الخدمة الكاملة (9 مراحل بفصل سلطات)
# ==========================================================================
# initiated → calculated → approved → clearance → acknowledged
#           → settled   (والطباعة/الحفظ في document_status لا هنا — AP-04)

EOS_FLOW = ["initiated", "calculated", "approved", "clearance", "acknowledged",
            "settled"]

# الأدوار المخوّلة لكل انتقال (super_admin يمرّ دائمًا للطوارئ)
_STAGE_ROLES = {
    "calculated": ("accountant",),
    "approved": ("accountant", "company_manager", "hr"),  # يُقيَّد لاحقًا بـSoD
    "clearance": ("hr",),
    "settled": ("accountant",),
    "printed": ("hr",),
    "filed": ("hr",),
}


def _get_case(db: Session, user: models.User, case_id: int) -> models.EosCase:
    case = db.get(models.EosCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="حالة إنهاء الخدمة غير موجودة")
    assert_same_company(user, case.company_id, db=db)
    return case


def _require_stage(case: models.EosCase, expected: str) -> None:
    if case.status != expected:
        raise HTTPException(status_code=409, detail=(
            f"الحالة الحالية '{case.status}' لا تسمح بهذا الإجراء — المطلوب '{expected}'"
        ))


def _require_role(user: models.User, stage: str) -> None:
    if user.role == "super_admin":
        return
    allowed = _STAGE_ROLES.get(stage)
    if allowed and user.role not in allowed:
        raise HTTPException(status_code=403, detail=(
            f"هذه المرحلة ({stage}) مخوّلة لـ{'/'.join(allowed)} فقط"
        ))


def _serialize_case(db: Session, case: models.EosCase) -> dict:
    emp = db.get(models.Employee, case.employee_id)
    return {
        "id": case.id, "reference_no": case.reference_no,
        "document_status": getattr(case, "document_status", "PENDING"),
        "status": case.status,
        "stage_index": EOS_FLOW.index(case.status) if case.status in EOS_FLOW else -1,
        "total_stages": len(EOS_FLOW),
        "employee_id": case.employee_id,
        "employee_name": emp.name if emp else None,
        "employee_no": emp.employee_no if emp else None,
        "termination_date": case.termination_date,
        "termination_reason": case.termination_reason,
        "used_leave_days": case.used_leave_days,
        "settlement": case.settlement_json,
        "initiated_by": case.initiated_by, "initiated_at": case.initiated_at,
        "calculated_by": case.calculated_by, "calculated_at": case.calculated_at,
        "approved_by": case.approved_by, "approved_at": case.approved_at,
        "clearance_by": case.clearance_by, "clearance_at": case.clearance_at,
        "clearance_notes": case.clearance_notes,
        "acknowledged_at": case.acknowledged_at,
        "acknowledgment_note": case.acknowledgment_note,
        "settled_by": case.settled_by, "settled_at": case.settled_at,
        "payment_reference": case.payment_reference,
        "printed_by": case.printed_by, "printed_at": case.printed_at,
        "filed_by": case.filed_by, "filed_at": case.filed_at,
        "filing_location": case.filing_location,
        "created_at": case.created_at,
    }


def _advance(db: Session, user: models.User, request: Request, case: models.EosCase,
             new_status: str, detail: str, **extra_after) -> None:
    before = {"status": case.status}
    case.status = new_status
    audit(db, user, f"eos_{new_status}", "eos_case", case.id,
          detail=detail, request=request, company_id=case.company_id,
          correlation_id=f"eos:{case.id}",
          before=before, after={"status": new_status, **extra_after})


@router.post("/cases", status_code=201)
def initiate_case(request: Request, employee_id: int,
                  termination_date: date, reason: str,
                  user: models.User = Depends(require_perm("terminate_employee")),
                  db: Session = Depends(get_db)):
    """QA §6 — المرحلة 1: HR يفتح حالة إنهاء خدمة.

    لا يُحسَب شيء هنا — الحساب مرحلة مستقلة يقوم بها المحاسب من بيانات
    الموظف المسجّلة (فصل سلطات).
    """
    emp = db.get(models.Employee, employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    assert_same_company(user, emp.company_id, db=db)
    # QA-18 — سجل وصول/صلاحية لا وظيفة: لا مستحق نهاية خدمة عليه، فحسابه
    # يخلق التزاًما ماليا لا وجود له.
    # P6-27 — لا يُفتح خروج ثانٍ بجانب خروج قائم: تاريخان لمغادرة واحدة.
    exit_guard.assert_single_exit(db, emp.id)
    # P6-27 — الإنشاء من مصدر واحد يستدعيه هذا الراوتر ومسار الطلبات
    # مًعا. كان مكتوًبا هنا وحده، فربطُ الطلبات به كان يعني نسخة ثانية.
    case = exit_case.open_case(
        db, emp, termination_date=termination_date, reason=reason,
        actor_user_id=user.id)
    audit(db, user, "eos_initiated", "eos_case", case.id,
          detail=f"employee={emp.id} reason={reason} date={termination_date}",
          request=request, company_id=emp.company_id,
          correlation_id=f"eos:{case.id}",
          after={"status": "initiated", "employee_id": emp.id})
    db.commit()
    return _serialize_case(db, case)


@router.post("/cases/{case_id}/calculate")
def calculate_case(case_id: int, request: Request, used_leave_days: float = 0,
                   user: models.User = Depends(require_perm("calculate_eos")),
                   db: Session = Depends(get_db)):
    """QA §6 — المرحلة 2: المالية تحسب التسوية من سجل الموظف.

    الراتب وتاريخ التعيين يُقرآن من قاعدة البيانات — لا يُقبلان من الإدخال،
    فلا يمكن إنتاج رقم تسوية من قيم افتراضية أو مُدخَلة يدويًا.
    """
    case = _get_case(db, user, case_id)
    _require_stage(case, "initiated")
    _require_role(user, "calculated")

    emp = db.get(models.Employee, case.employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    if not emp.basic_salary or not emp.hire_date:
        raise HTTPException(status_code=400, detail=(
            f"بيانات الموظف ناقصة (الراتب/تاريخ التعيين) — أكمل الملف قبل الحساب"
        ))
    company = db.get(models.Company, case.company_id)
    try:
        result = eos_engine.calculate_eos(
            basic_salary=emp.basic_salary, hire_date=emp.hire_date,
            end_date=case.termination_date, reason=case.termination_reason,
            contract_type=emp.contract_type, used_leave_days=used_leave_days,
            annual_leave_days=company.annual_leave_days,
            day_divisor=company.eos_day_divisor, max_months=company.eos_max_months,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    case.used_leave_days = used_leave_days
    case.settlement_json = result
    case.calculated_by = user.id
    case.calculated_at = datetime.now(timezone.utc)
    _advance(db, user, request, case, "calculated",
             detail=f"total={result.get('total_settlement')}",
             total_settlement=result.get("total_settlement"))
    db.commit()
    return _serialize_case(db, case)


@router.post("/cases/{case_id}/approve")
def approve_case(case_id: int, request: Request, note: str | None = None,
                 user: models.User = Depends(require_perm("approve_termination")),
                 db: Session = Depends(get_db)):
    """QA §6 — المرحلة 3: اعتماد التسوية. فصل سلطات: لا يعتمدها من حسبها."""
    case = _get_case(db, user, case_id)
    _require_stage(case, "calculated")
    if case.calculated_by == user.id and user.role != "super_admin":
        raise HTTPException(status_code=403, detail=(
            "لا يمكنك اعتماد تسوية حسبتها بنفسك — فصل السلطات إلزامي"
        ))
    # لا يعتمد الموظف تسويته الخاصة
    if user.employee_id and user.employee_id == case.employee_id:
        raise HTTPException(status_code=403, detail="لا يمكنك اعتماد تسوية تخصّك")

    case.approved_by = user.id
    case.approved_at = datetime.now(timezone.utc)
    _advance(db, user, request, case, "approved", detail=note or "-",
             approved_by=user.id, approver_role=user.role)
    db.commit()
    return _serialize_case(db, case)


@router.post("/cases/{case_id}/clearance")
def clearance_case(case_id: int, request: Request, notes: str,
                   user: models.User = Depends(require_perm("terminate_employee")),
                   db: Session = Depends(get_db)):
    """QA §6 — المرحلة 4: إخلاء الطرف (عهد/مستندات/تسليم). HR."""
    case = _get_case(db, user, case_id)
    _require_stage(case, "approved")
    _require_role(user, "clearance")
    if not notes or not notes.strip():
        raise HTTPException(status_code=400, detail="تفاصيل إخلاء الطرف مطلوبة")

    case.clearance_by = user.id
    case.clearance_at = datetime.now(timezone.utc)
    case.clearance_notes = notes.strip()
    _advance(db, user, request, case, "clearance", detail=notes.strip()[:200])
    db.commit()
    return _serialize_case(db, case)


@router.post("/cases/{case_id}/acknowledge")
def acknowledge_case(case_id: int, request: Request, note: str | None = None,
                     user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """QA §6 — المرحلة 5: إقرار الموظف باطّلاعه على التسوية. الموظف نفسه فقط."""
    case = _get_case(db, user, case_id)
    _require_stage(case, "clearance")
    if user.employee_id != case.employee_id and user.role != "super_admin":
        raise HTTPException(status_code=403, detail=(
            "الإقرار يوقّعه الموظف صاحب التسوية بنفسه"
        ))

    case.acknowledged_at = datetime.now(timezone.utc)
    case.acknowledgment_note = (note or "").strip() or None
    _advance(db, user, request, case, "acknowledged", detail=note or "-")
    db.commit()
    return _serialize_case(db, case)


@router.post("/cases/{case_id}/settle")
def settle_case(case_id: int, request: Request, payment_reference: str,
                user: models.User = Depends(require_perm("run_payroll")),
                db: Session = Depends(get_db)):
    """QA §6 — المرحلة 6: تأكيد الصرف الفعلي مع مرجع الدفع. المحاسب."""
    case = _get_case(db, user, case_id)
    _require_stage(case, "acknowledged")
    _require_role(user, "settled")
    if not payment_reference or not payment_reference.strip():
        raise HTTPException(status_code=400, detail="مرجع الدفع مطلوب")

    case.settled_by = user.id
    case.settled_at = datetime.now(timezone.utc)
    case.payment_reference = payment_reference.strip()
    # V2.2 §3.3 (AP-04) — الصرف يُنهي الحالة. الطباعة حدث على المستند لا
    # مرحلة في الحالة: تسوية مصروفة لا تصير "غير مكتملة" لأن أحًدا لم يطبعها.
    _advance(db, user, request, case, "settled",
             detail=f"payment_ref={payment_reference.strip()}",
             payment_reference=payment_reference.strip())
    case.document_status = "READY"
    # الآن يُطبَّق الفصل فعليًا على ملف الموظف
    emp = db.get(models.Employee, case.employee_id)
    if emp:
        _before = {"status": emp.status,
                   "termination_date": str(emp.termination_date or "")}
        emp.status = "terminated"
        emp.termination_date = case.termination_date
        emp.termination_reason = case.termination_reason
        import json as _json
        emp.eos_settlement_json = _json.dumps(case.settlement_json, ensure_ascii=False)
        # P6-28 — الخروج حدث على **ملف الموظف** لا على الحالة وحدها.
        #
        # كانت ست خطوات تُدقَّق كلها على ``eos_case`` وصفر على الموظف،
        # بينما ملفه هو ما يتغيّر: يصير ``terminated`` ويُجمَّد
        # (BLOCKED_EMPLOYEE_STATUSES) فلا يُفتح له طلب. فمن يفتح الملف
        # ويسأل «متى أُغلق ومن أغلقه وبأي سند؟» لا يجد سطًرا — والأثر
        # موجود تحت رقم حالة يجب أن يعرفه سلًفا ليصل إليه.
        #
        # ``correlation_id`` هو نفسه الذي تحمله خطوات الحالة، فيُقرأ
        # الطرفان مًعا: ملف الموظف يقول ماذا جرى، والحالة تقول كيف.
        audit(db, user, "employee_terminated", "employee", emp.id,
              detail=(f"إنهاء خدمة عبر الحالة {case.reference_no} — "
                      f"{case.termination_reason or '-'} @ "
                      f"{case.termination_date} | مرجع الدفع "
                      f"{payment_reference.strip()}"),
              request=request, company_id=emp.company_id,
              correlation_id=f"eos:{case.id}",
              before=_before,
              after={"status": "terminated",
                     "termination_date": str(case.termination_date),
                     "eos_case_id": case.id,
                     "eos_reference_no": case.reference_no})
    db.commit()
    return _serialize_case(db, case)


@router.post("/cases/{case_id}/print")
def print_case(case_id: int, request: Request,
               user: models.User = Depends(require_perm("terminate_employee")),
               db: Session = Depends(get_db)):
    """QA §6 — المرحلة 7→8: تسجيل الطباعة."""
    case = _get_case(db, user, case_id)
    _require_stage(case, "settled")
    _require_role(user, "printed")
    if case.document_status == "FILED":
        raise HTTPException(status_code=409, detail="المستند محفوظ بالفعل")
    case.printed_by = user.id
    case.printed_at = datetime.now(timezone.utc)
    case.document_status = "PRINTED"
    audit(db, user, "eos_document_printed", "eos_case", case.id, request=request)
    db.commit()
    return _serialize_case(db, case)


@router.post("/cases/{case_id}/file")
def file_case(case_id: int, request: Request, filing_location: str,
              user: models.User = Depends(require_perm("terminate_employee")),
              db: Session = Depends(get_db)):
    """QA §6 — المرحلة 9: الأرشفة النهائية (مكان الحفظ الورقي). حالة نهائية."""
    case = _get_case(db, user, case_id)
    _require_stage(case, "settled")
    _require_role(user, "filed")
    if case.document_status != "PRINTED":
        raise HTTPException(status_code=409, detail="يُطبع المستند قبل أرشفته")
    if not filing_location or not filing_location.strip():
        raise HTTPException(status_code=400, detail="مكان الأرشفة مطلوب")
    case.filed_by = user.id
    case.filed_at = datetime.now(timezone.utc)
    case.filing_location = filing_location.strip()
    case.document_status = "FILED"
    audit(db, user, "eos_document_filed", "eos_case", case.id,
          detail=filing_location.strip(), request=request)
    db.commit()
    return _serialize_case(db, case)


@router.get("/cases")
def list_cases(status: str | None = None, employee_id: int | None = None,
               user: models.User = Depends(require_perm("view_employee")),
               db: Session = Depends(get_db)):
    """قائمة حالات إنهاء الخدمة ضمن نطاق المستخدم."""
    from ..deps import scope_company_id
    cid = scope_company_id(user, None)
    q = select(models.EosCase)
    if cid is not None:
        q = q.where(models.EosCase.company_id == cid)
    if status:
        q = q.where(models.EosCase.status == status)
    if employee_id:
        q = q.where(models.EosCase.employee_id == employee_id)
    rows = db.scalars(q.order_by(models.EosCase.created_at.desc())).all()
    return [_serialize_case(db, c) for c in rows]


@router.get("/cases/{case_id}")
def get_case(case_id: int, user: models.User = Depends(require_perm("view_employee")),
             db: Session = Depends(get_db)):
    case = _get_case(db, user, case_id)
    return _serialize_case(db, case)
