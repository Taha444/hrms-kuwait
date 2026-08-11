# -*- coding: utf-8 -*-
"""تجديد الإقامة (DEMO-001/002): طلب مبكر/عادي + خطوات المندوب والموظف.

يعيد استخدام خزنة المستندات (Document) لحفظ العقود والنسخ الموقّعة وإذن العمل
والبطاقة المدنية مع الاحتفاظ بالنسخ القديمة.
"""
import os
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, renewal as R
from ..config import settings
from ..database import get_db
from ..deps import assert_same_company, audit, get_current_user, get_user_perms
from ..notifications import (create_task, notify_employee_self, notify_from_template,
                             notify_roles, users_by_role)
from ..permissions import has_permission
from ..safe_files import read_limited, unique_path

router = APIRouter(prefix="/renewals", tags=["renewals"])


# ----------------------------- مساعدات -----------------------------

def _is_pro(user, perms):
    return (user.role == "super_admin" or has_permission(user.role, perms, "manage_permits")
            or has_permission(user.role, perms, "process_delegate_tasks"))


def _get_renewal(db, user, rid) -> models.ResidencyRenewal:
    rn = db.get(models.ResidencyRenewal, rid)
    if not rn:
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة")
    assert_same_company(user, rn.company_id, db=db)
    return rn


async def _save_doc(db, user, request, entity_type, entity_id, company_id,
                    code, title, upload: UploadFile, expiry_date: date | None = None):
    """يحفظ ملفًا كمستند بنُسخ (الأحدث is_current) — يُبقي القديم."""
    folder = os.path.join(settings.upload_dir, "renewals")
    fpath = unique_path(folder, upload.filename, prefix=f"{entity_type}_{entity_id}_{code}_")
    with open(fpath, "wb") as f:
        f.write(await read_limited(upload))
    prev = db.scalars(select(models.Document).where(
        models.Document.entity_type == entity_type, models.Document.entity_id == entity_id,
        models.Document.document_type_code == code, models.Document.is_current == True)).all()  # noqa: E712
    ver = max((d.version for d in prev), default=0) + 1
    for d in prev:
        d.is_current = False
    doc = models.Document(company_id=company_id, entity_type=entity_type, entity_id=entity_id,
                          document_type_code=code, title=title, file_path=fpath,
                          mime=upload.content_type, expiry_date=expiry_date,
                          version=ver, is_current=True, uploaded_by=user.id)
    db.add(doc)
    db.flush()  # حتى يراه فحص اكتمال المستندات مباشرةً
    audit(db, user, "renewal_upload", "renewal", entity_id, detail=code, request=request)
    return doc


def _renewal_docs(db, rn) -> list[dict]:
    """مستندات المعاملة (عقود/موقّعة) + إذن العمل والبطاقة من ملف الموظف."""
    out = []
    rows = db.scalars(select(models.Document).where(
        models.Document.entity_type == "renewal", models.Document.entity_id == rn.id)).all()
    for d in rows:
        out.append(_doc_row(db, d))
    # أحدث إذن عمل/بطاقة مدنية من ملف الموظف مرتبطة بالتجديد
    for code in (R.DOC_WORK_PERMIT, R.DOC_CIVIL_CARD):
        d = db.scalar(select(models.Document).where(
            models.Document.entity_type == "employee", models.Document.entity_id == rn.employee_id,
            models.Document.document_type_code == code, models.Document.is_current == True))  # noqa: E712
        if d:
            out.append(_doc_row(db, d))
    return out


def _doc_row(db, d) -> dict:
    up = db.get(models.User, d.uploaded_by) if d.uploaded_by else None
    return {"id": d.id, "type": d.document_type_code, "title": d.title, "version": d.version,
            "uploaded_by": up.full_name if up else None,
            "created_at": d.created_at, "is_current": d.is_current}


def _has(db, entity_type, entity_id, code) -> bool:
    return bool(db.scalar(select(models.Document.id).where(
        models.Document.entity_type == entity_type, models.Document.entity_id == entity_id,
        models.Document.document_type_code == code, models.Document.is_current == True)))  # noqa: E712


def _serialize(db, rn, lang="ar") -> dict:
    emp = db.get(models.Employee, rn.employee_id)
    return {
        "id": rn.id, "employee_id": rn.employee_id,
        "employee_name": emp.name if emp else None,
        "renewal_type": rn.renewal_type, "status": rn.status,
        "status_label": R.status_label(rn.status, lang),
        "reason": rn.reason, "notes": rn.notes, "reject_reason": rn.reject_reason,
        "days_left_at_request": rn.days_left_at_request,
        "created_at": rn.created_at, "documents": _renewal_docs(db, rn),
        # R4 §7 — Government transaction metadata (surfaced to UI)
        "gov_reference_no": rn.gov_reference_no,
        "fees_amount": rn.fees_amount,
        "fees_receipt_no": rn.fees_receipt_no,
        "new_permit_number": rn.new_permit_number,
        "new_expiry_date": rn.new_expiry_date,
        "finalized_at": rn.finalized_at,
        "finalized_by": rn.finalized_by,
        "hr_verified_at": rn.hr_verified_at,
        "hr_verified_by": rn.hr_verified_by,
        "hr_verification_note": rn.hr_verification_note,
    }


# ----------------------------- إنشاء الطلب -----------------------------

@router.post("", status_code=201)
def create_renewal(employee_id: int | None = Form(None), permit_id: int | None = Form(None),
                   reason: str | None = Form(None), notes: str | None = Form(None),
                   request: Request = None,
                   user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """ينشئ طلب تجديد إقامة. مقدّم الطلب الموظف نفسه (أو المندوب نيابةً)."""
    perms = get_user_perms(user, db)
    eid = employee_id or user.employee_id
    if not eid:
        raise HTTPException(status_code=400, detail="لم يُحدَّد الموظف")
    emp = db.get(models.Employee, eid)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    assert_same_company(user, emp.company_id, db=db)
    # الصلاحية: الموظف نفسه أو المندوب نيابةً
    if user.employee_id != eid and not _is_pro(user, perms):
        raise HTTPException(status_code=403, detail="لا يمكنك تقديم الطلب لهذا الموظف")

    # الإقامة محل التجديد: المحددة أو أحدث إقامة سارية للموظف
    permit = db.get(models.Permit, permit_id) if permit_id else db.scalar(
        select(models.Permit).where(models.Permit.employee_id == eid,
                                    models.Permit.kind == "residency",
                                    models.Permit.status == "active").order_by(models.Permit.expiry_date))
    if not permit or not permit.expiry_date:
        raise HTTPException(status_code=400, detail="لا توجد إقامة سارية بتاريخ انتهاء لهذا الموظف")
    days_left = (permit.expiry_date - date.today()).days
    rtype = R.classify(days_left)
    if rtype is None:
        raise HTTPException(status_code=400,
                            detail="لا يمكن التجديد قبل 90 يومًا من الانتهاء")
    if rtype == "early" and not (reason and reason.strip()):
        raise HTTPException(status_code=400, detail="سبب التجديد المبكر إلزامي")

    # منع تكرار معاملة مفتوحة لنفس الإقامة
    open_exists = db.scalar(select(models.ResidencyRenewal.id).where(
        models.ResidencyRenewal.permit_id == permit.id,
        models.ResidencyRenewal.status.notin_([R.REJECTED, R.COMPLETED])))
    if open_exists:
        raise HTTPException(status_code=409, detail="توجد معاملة تجديد مفتوحة لهذه الإقامة")

    status = R.PENDING_MANAGER if rtype == "early" else R.AWAITING_CONTRACTS
    rn = models.ResidencyRenewal(
        company_id=emp.company_id, employee_id=eid, permit_id=permit.id, renewal_type=rtype,
        status=status, reason=reason, notes=notes, days_left_at_request=days_left,
        created_by=user.id)
    db.add(rn)
    db.flush()
    audit(db, user, "create_renewal", "renewal", rn.id, detail=f"{rtype} ({days_left}d)", request=request)
    _notify_stage(db, rn)
    db.commit()
    return _serialize(db, rn)


def _notify_stage(db, rn):
    """إشعار المسؤول عن المرحلة الحالية."""
    name = (db.get(models.Employee, rn.employee_id).name if rn.employee_id else "")
    if rn.status == R.PENDING_MANAGER:
        for u in users_by_role(db, rn.company_id, ["company_manager"]):
            notify_from_template(
                db, code="NTF-033", assignee_user_id=u.id, company_id=rn.company_id,
                context={"request_type": "تجديد إقامة مبكر", "employee_name": name},
                related_entity_type="renewal", related_entity_id=rn.id,
                dedup_key=f"renewal_mgr:{rn.id}:u{u.id}")
    elif rn.status == R.PENDING_HR:
        for u in users_by_role(db, rn.company_id, ["hr"]):
            notify_from_template(
                db, code="NTF-033", assignee_user_id=u.id, company_id=rn.company_id,
                context={"request_type": "تجديد إقامة مبكر (شؤون الموظفين)", "employee_name": name},
                related_entity_type="renewal", related_entity_id=rn.id,
                dedup_key=f"renewal_hr:{rn.id}:u{u.id}")
    elif rn.status == R.AWAITING_CONTRACTS:
        for u in users_by_role(db, rn.company_id, ["delegate"]):
            notify_from_template(
                db, code="NTF-015", assignee_user_id=u.id, company_id=rn.company_id,
                context={"employee_name": name},
                related_entity_type="renewal", related_entity_id=rn.id,
                dedup_key=f"renewal_pro:{rn.id}:u{u.id}")
    elif rn.status == R.AWAITING_SIGNATURE:
        emp_user = db.scalar(select(models.User).where(models.User.employee_id == rn.employee_id))
        if emp_user:
            notify_from_template(
                db, code="NTF-016", assignee_user_id=emp_user.id, company_id=rn.company_id,
                related_entity_type="renewal", related_entity_id=rn.id,
                dedup_key=f"renewal_sign:{rn.id}")
    elif rn.status == R.CONTRACTS_SIGNED:
        notify_roles(db, rn.company_id, ["delegate"], type="renew_residency",
                     title=f"تم رفع العقود الموقّعة: {name}",
                     detail="حمّل النسخ الموقّعة واستكمل إجراءات التجديد.",
                     related_entity_type="renewal", related_entity_id=rn.id,
                     dedup_key=f"renewal_signed:{rn.id}")
    elif rn.status == R.AWAITING_CIVIL_CARD:
        emp_user = db.scalar(select(models.User).where(models.User.employee_id == rn.employee_id))
        if emp_user:
            notify_from_template(
                db, code="NTF-017", assignee_user_id=emp_user.id, company_id=rn.company_id,
                related_entity_type="renewal", related_entity_id=rn.id,
                dedup_key=f"renewal_card:{rn.id}")
    elif rn.status == R.COMPLETED:
        notify_roles(db, rn.company_id, ["delegate", "hr"], type="request_update",
                     title=f"اكتملت معاملة تجديد الإقامة: {name}",
                     detail="رفع الموظف البطاقة المدنية الجديدة. المعاملة مكتملة.",
                     related_entity_type="renewal", related_entity_id=rn.id,
                     dedup_key=f"renewal_done:{rn.id}")


# ----------------------------- عرض -----------------------------

@router.get("")
def list_renewals(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    perms = get_user_perms(user, db)
    q = select(models.ResidencyRenewal).order_by(models.ResidencyRenewal.created_at.desc())
    if user.role not in ("super_admin", "company_owner"):
        q = q.where(models.ResidencyRenewal.company_id == user.company_id)
    # الموظف العادي: طلباته فقط
    if not _is_pro(user, perms) and not has_permission(user.role, perms, "approve_request") \
            and user.role not in ("super_admin", "company_owner"):
        q = q.where(models.ResidencyRenewal.employee_id == (user.employee_id or -1))
    return [_serialize(db, rn) for rn in db.scalars(q).all()]


@router.get("/{rid}")
def get_renewal(rid: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    rn = _get_renewal(db, user, rid)
    perms = get_user_perms(user, db)
    if not _is_pro(user, perms) and not has_permission(user.role, perms, "approve_request") \
            and user.employee_id != rn.employee_id and user.role not in ("super_admin", "company_owner"):
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة")
    return _serialize(db, rn)


@router.get("/{rid}/document/{doc_type}")
def download_renewal_document(rid: int, doc_type: str,
                              user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """تنزيل مستند تجديد (عقد/موقّع) أو مستند الموظف المرتبط (إذن عمل/بطاقة مدنية)."""
    rn = _get_renewal(db, user, rid)
    perms = get_user_perms(user, db)
    if not _is_pro(user, perms) and not has_permission(user.role, perms, "approve_request") \
            and user.employee_id != rn.employee_id and user.role not in ("super_admin", "company_owner"):
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة")

    if doc_type in R.CONTRACT_DOCS + R.SIGNED_DOCS:
        entity_type, entity_id = "renewal", rn.id
    elif doc_type in (R.DOC_WORK_PERMIT, R.DOC_CIVIL_CARD):
        entity_type, entity_id = "employee", rn.employee_id
    else:
        raise HTTPException(status_code=400, detail="نوع مستند غير معروف")

    doc = db.scalar(select(models.Document).where(
        models.Document.entity_type == entity_type, models.Document.entity_id == entity_id,
        models.Document.document_type_code == doc_type, models.Document.is_current == True))  # noqa: E712
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="لا توجد نسخة محفوظة")
    return FileResponse(doc.file_path, filename=os.path.basename(doc.file_path),
                        media_type=doc.mime or "application/octet-stream")


# ----------------------------- موافقات (مبكر) -----------------------------

@router.post("/{rid}/decide")
def decide_renewal(rid: int, decision: str = Form(...), reject_reason: str | None = Form(None),
                   request: Request = None,
                   user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """موافقة/رفض مرحلة (المدير ثم الشؤون) للتجديد المبكر."""
    rn = _get_renewal(db, user, rid)
    perms = get_user_perms(user, db)
    if not has_permission(user.role, perms, "approve_request"):
        raise HTTPException(status_code=403, detail="لا تملك صلاحية اعتماد الطلبات")
    # مطابقة الدور للمرحلة
    stage_role = {R.PENDING_MANAGER: "company_manager", R.PENDING_HR: "hr"}.get(rn.status)
    if stage_role is None:
        raise HTTPException(status_code=409, detail="لا يمكن اتخاذ قرار في هذه الحالة")
    if user.role != stage_role and user.role != "super_admin":
        raise HTTPException(status_code=403, detail="لست المعتمِد لهذه المرحلة")

    if decision == "rejected":
        if not (reject_reason and reject_reason.strip()):
            raise HTTPException(status_code=400, detail="سبب الرفض إلزامي")
        rn.status = R.REJECTED
        rn.reject_reason = reject_reason
        notify_employee_self(db, rn.employee_id, type="request_update",
                             title="رُفض طلب تجديد الإقامة",
                             detail=f"سبب الرفض: {reject_reason}",
                             related_entity_type="renewal", related_entity_id=rn.id,
                             dedup_key=f"renewal_reject:{rn.id}")
        audit(db, user, "renewal_rejected", "renewal", rn.id, detail=reject_reason, request=request)
    elif decision == "approved":
        rn.status = R.PENDING_HR if rn.status == R.PENDING_MANAGER else R.AWAITING_CONTRACTS
        audit(db, user, "renewal_approved", "renewal", rn.id, detail=stage_role, request=request)
        _notify_stage(db, rn)
    else:
        raise HTTPException(status_code=400, detail="قرار غير صالح")
    db.commit()
    return _serialize(db, rn)


# ----------------------------- المندوب: تغيير الحالة يدويًا -----------------------------

@router.post("/{rid}/renewing")
def mark_renewing(rid: int, request: Request = None,
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """المندوب يعلن بدء إجراءات التجديد الحكومية (جاري التجديد)."""
    rn = _get_renewal(db, user, rid)
    perms = get_user_perms(user, db)
    if not _is_pro(user, perms):
        raise HTTPException(status_code=403, detail="خاص بالمندوب")
    if rn.status != R.CONTRACTS_SIGNED:
        raise HTTPException(status_code=409, detail="الحالة لا تسمح بذلك")
    rn.status = R.RENEWING
    audit(db, user, "renewal_renewing", "renewal", rn.id, request=request)
    db.commit()
    return _serialize(db, rn)


# ----------------------------- رفع المستندات (يقود الحالة) -----------------------------

@router.post("/{rid}/upload")
async def upload_renewal_doc(rid: int, doc_kind: str = Form(..., alias="doc_type"),
                             file: UploadFile = File(...),
                             request: Request = None,
                             user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """يرفع مستندًا حسب المرحلة ويقود الحالة للأمام."""
    rn = _get_renewal(db, user, rid)
    perms = get_user_perms(user, db)
    emp = db.get(models.Employee, rn.employee_id)
    is_pro = _is_pro(user, perms)
    is_owner_emp = user.employee_id == rn.employee_id

    # المندوب يرفع العقود (بانتظار رفع العقود). R9 §1: يكفي العقد الحكومي.
    if doc_kind in R.ACCEPTED_CONTRACT_DOCS:
        if not is_pro:
            raise HTTPException(status_code=403, detail="رفع العقود خاص بالمندوب")
        if rn.status != R.AWAITING_CONTRACTS:
            raise HTTPException(status_code=409, detail="الحالة لا تسمح برفع العقود")
        await _save_doc(db, user, request, "renewal", rn.id, rn.company_id, doc_kind,
                        "عقد حكومي" if doc_kind == R.DOC_CONTRACT_GOV else "عقد داخلي", file)
        # R9 §1: التجديد يحتاج فقط العقد الحكومي للانتقال — العقد الداخلي اختياري
        if all(_has(db, "renewal", rn.id, c) for c in R.REQUIRED_CONTRACT_DOCS):
            rn.status = R.AWAITING_SIGNATURE
            _notify_stage(db, rn)

    # الموظف يرفع النسخ الموقّعة (بانتظار توقيع الموظف). R9 §1: يكفي الموقّع الحكومي.
    elif doc_kind in R.ACCEPTED_SIGNED_DOCS:
        if not (is_owner_emp or is_pro):
            raise HTTPException(status_code=403, detail="خاص بالموظف صاحب الطلب")
        if rn.status != R.AWAITING_SIGNATURE:
            raise HTTPException(status_code=409, detail="الحالة لا تسمح برفع الموقّع")
        await _save_doc(db, user, request, "renewal", rn.id, rn.company_id, doc_kind,
                        "موقّع حكومي" if doc_kind == R.DOC_SIGNED_GOV else "موقّع داخلي", file)
        if all(_has(db, "renewal", rn.id, c) for c in R.REQUIRED_SIGNED_DOCS):
            rn.status = R.CONTRACTS_SIGNED
            _notify_stage(db, rn)

    # المندوب يرفع إذن العمل الجديد (جاري التجديد → بانتظار البطاقة)
    elif doc_kind == R.DOC_WORK_PERMIT:
        if not is_pro:
            raise HTTPException(status_code=403, detail="خاص بالمندوب")
        if rn.status != R.RENEWING:
            raise HTTPException(status_code=409, detail="عيّن الحالة (جاري التجديد) أولًا")
        await _save_doc(db, user, request, "employee", emp.id, rn.company_id,
                        R.DOC_WORK_PERMIT, "إذن العمل الجديد", file)
        rn.status = R.AWAITING_CIVIL_CARD
        _notify_stage(db, rn)

    # الموظف يرفع البطاقة المدنية — ينتقل لتحقق HR (R4 §7)
    elif doc_kind == R.DOC_CIVIL_CARD:
        if not (is_owner_emp or is_pro):
            raise HTTPException(status_code=403, detail="خاص بالموظف صاحب الطلب")
        if rn.status != R.AWAITING_CIVIL_CARD:
            raise HTTPException(status_code=409, detail="الحالة لا تسمح برفع البطاقة")
        await _save_doc(db, user, request, "employee", emp.id, rn.company_id,
                        R.DOC_CIVIL_CARD, "البطاقة المدنية الجديدة", file)
        # R4-A — بدل التنقّل المباشر لـCOMPLETED، نمرّ عبر PENDING_HR_VERIFY
        rn.status = R.PENDING_HR_VERIFY
        _notify_stage(db, rn)
    else:
        raise HTTPException(status_code=400, detail="نوع مستند غير معروف")

    db.commit()
    return _serialize(db, rn)


# ==============================================================================
# R4 §7 — Government Transaction Finalization + HR Verification
# ==============================================================================

@router.post("/{rid}/finalize")
def finalize_renewal(rid: int, request: Request,
                     gov_reference_no: str = Form(...),
                     fees_amount: float = Form(...),
                     fees_receipt_no: str = Form(...),
                     new_permit_number: str = Form(...),
                     new_expiry_date: date = Form(...),
                     user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """R4 §7 — المندوب يعبّي بيانات المعاملة الحكومية بعد إتمامها في وزارة الداخلية:
    الرقم المرجعي + الرسوم + الإيصال + رقم الإقامة الجديد + تاريخ الانتهاء الجديد.

    ينقل الحالة إلى AWAITING_CIVIL_CARD (بانتظار الموظف يرفع البطاقة المدنية الجديدة).
    """
    rn = _get_renewal(db, user, rid)
    from ..deps import get_user_perms
    perms = get_user_perms(user, db)
    if not _is_pro(user, perms):
        raise HTTPException(status_code=403, detail="فقط المندوب يقدر يُتمم المعاملة الحكومية")
    # R4/R6 — finalize مسموحة قبل رفع البطاقة المدنية أو بعده (المندوب قد يعبّي
    # البيانات قبل استلام البطاقة من الموظف)
    if rn.status not in (R.RENEWING, R.CONTRACTS_SIGNED, R.WITH_DELEGATE, R.AWAITING_CIVIL_CARD):
        raise HTTPException(status_code=409,
                          detail=f"الحالة الحالية ({rn.status}) لا تسمح بإدخال بيانات المعاملة الحكومية")
    # التحقق من صحة القيم
    if not gov_reference_no.strip():
        raise HTTPException(status_code=400, detail="الرقم المرجعي الحكومي إلزامي")
    if fees_amount < 0:
        raise HTTPException(status_code=400, detail="قيمة الرسوم لا يمكن أن تكون سالبة")
    if new_expiry_date <= date.today():
        raise HTTPException(status_code=400,
                          detail="تاريخ انتهاء الإقامة الجديد يجب أن يكون في المستقبل")

    rn.gov_reference_no = gov_reference_no.strip()
    rn.fees_amount = fees_amount
    rn.fees_receipt_no = fees_receipt_no.strip()
    rn.new_permit_number = new_permit_number.strip()
    rn.new_expiry_date = new_expiry_date
    rn.finalized_at = datetime.utcnow()
    rn.finalized_by = user.id
    # لو الحالة awaiting_civil_card بالفعل، نُبقيها (المندوب أكمل بيانات متأخّرة)
    if rn.status != R.AWAITING_CIVIL_CARD:
        rn.status = R.AWAITING_CIVIL_CARD
    _notify_stage(db, rn)
    audit(db, user, "finalize_renewal", "residency_renewal", rn.id, request=request,
          detail=f"gov_ref={gov_reference_no}, new_permit={new_permit_number}",
          company_id=rn.company_id,
          after={"gov_reference_no": gov_reference_no, "fees_amount": fees_amount,
                "new_permit_number": new_permit_number,
                "new_expiry_date": new_expiry_date.isoformat()})
    db.commit()
    return _serialize(db, rn)


@router.post("/{rid}/hr-verify")
def hr_verify_renewal(rid: int, request: Request,
                     note: str | None = Form(None),
                     user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """R4 §7 — HR يتحقق من تطابق بيانات المعاملة (رقم/تاريخ الإقامة الجديدة + الرسوم)
    مع الوثائق المرفوعة، ويغلق المعاملة (COMPLETED) + يحدّث Permit الأصلي بالبيانات الجديدة."""
    rn = _get_renewal(db, user, rid)
    if user.role not in ("hr", "super_admin"):
        raise HTTPException(status_code=403,
                          detail="التحقق من إتمام معاملة التجديد لـHR/الإدارة العليا فقط")
    if rn.status != R.PENDING_HR_VERIFY:
        raise HTTPException(status_code=409, detail="المعاملة ليست في مرحلة تحقق HR")
    if not rn.gov_reference_no or not rn.new_permit_number or not rn.new_expiry_date:
        raise HTTPException(status_code=400,
                          detail="بيانات المعاملة الحكومية ناقصة — لا يمكن التحقق")

    rn.hr_verified_at = datetime.utcnow()
    rn.hr_verified_by = user.id
    rn.hr_verification_note = (note or "").strip() or None
    rn.status = R.COMPLETED

    # R6-E §7 — Archive old permit + create the new one atomically.
    # نُميّز القديم بحالة "renewed" (مش expired) — semantic أدق للتاريخ.
    if rn.permit_id:
        old_permit = db.get(models.Permit, rn.permit_id)
        if old_permit:
            old_permit.status = "renewed"
    new_permit = models.Permit(
        company_id=rn.company_id, employee_id=rn.employee_id,
        kind="residency", number=rn.new_permit_number,
        start_date=date.today(), expiry_date=rn.new_expiry_date,
        status="active",
    )
    db.add(new_permit)

    _notify_stage(db, rn)
    audit(db, user, "hr_verify_renewal", "residency_renewal", rn.id, request=request,
          detail=f"verified→{rn.new_permit_number} exp {rn.new_expiry_date}",
          company_id=rn.company_id)
    db.commit()
    return _serialize(db, rn)


# ==========================================================================
# R8 §3 — توليد العقد الحكومي لتجديد الإقامة
# ==========================================================================
# القاعدة الحاكمة: عند التجديد نحتاج **فقط** العقد الحكومي (بلا عقد الشركة).
# عقد الشركة يُوقَّع مرة واحدة عند التعيين. النموذج يُقرأ من DocumentTemplate
# بكود "GOV-CONTRACT-RENEWAL" (يُضاف من الإدارة عبر /templates بعد الحصول على
# نموذج وزارة الداخلية الرسمي). البيانات تُملأ تلقائيًا من الموظف/الشركة.

@router.post("/{rid}/gov-contract/generate")
def generate_gov_contract(rid: int, request: Request,
                          format: str = "html",
                          user: models.User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """R8 §3 — يُولّد العقد الحكومي لطلب تجديد. يستخدم template بكود
    GOV-CONTRACT-RENEWAL ويُعبّئ بيانات الموظف والشركة تلقائيًا (authoritative).
    format=html (افتراضي) → JSON مع HTML للمعاينة/الطباعة.
    format=pdf → يُعيد FileResponse مباشرة (application/pdf) — R9 §5."""
    from ..routers.templates import _resolve_authoritative_data, _fill_html, _generate_reference_no
    import hashlib

    rn = _get_renewal(db, user, rid)
    perms = get_user_perms(user, db)
    if not (_is_pro(user, perms) or user.employee_id == rn.employee_id):
        raise HTTPException(status_code=403, detail="فقط المندوب أو الموظف صاحب الطلب")

    emp = db.get(models.Employee, rn.employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")

    # ابحث عن قالب العقد الحكومي (يُنشأ يدويًا من إدارة القوالب مرة واحدة)
    tpl = db.scalar(select(models.DocumentTemplate).where(
        models.DocumentTemplate.code == "GOV-CONTRACT-RENEWAL",
        models.DocumentTemplate.is_active == True,  # noqa: E712
    ))
    if not tpl:
        raise HTTPException(status_code=404, detail=(
            "قالب العقد الحكومي (GOV-CONTRACT-RENEWAL) غير موجود. "
            "لإضافته: /templates → إنشاء قالب جديد بكود GOV-CONTRACT-RENEWAL "
            "وضع نص وزارة الداخلية الرسمي مع placeholders {{employee_name}}، "
            "{{civil_id}}، {{passport_number}}، {{nationality}}، {{job_title}}، "
            "{{company_name}}، {{company_name_en}}، {{commercial_reg}}، "
            "{{basic_salary}}، {{date_today}}، {{ref_no}}."
        ))

    # حقول العقد الحكومي — كلها authoritative (لا يعدّلها المستخدم)
    ctx = _resolve_authoritative_data(db, emp, extras={})
    company = db.get(models.Company, rn.company_id)
    permit = db.get(models.Permit, rn.permit_id) if rn.permit_id else None
    ctx.update({
        "renewal_id": str(rn.id),
        "old_permit_number": (permit.number if permit else "") or "",
        "old_permit_expiry": (permit.expiry_date.isoformat() if permit and permit.expiry_date else ""),
        "company_file_number": (company.file_number if company else "") or "",
    })
    reference_no = _generate_reference_no(db, "GOV-REN", rn.company_id, tpl.version or 1)
    ctx["ref_no"] = reference_no

    rendered = _fill_html(tpl, ctx)

    # R9 §5 — لو طُلب PDF نُنتج ملف PDF ثنائي بدل HTML
    if (format or "").lower() == "pdf":
        from ..pdf_export import render_html_contract_pdf
        pdf_bytes = render_html_contract_pdf(
            rendered,
            title=f"العقد الحكومي — تجديد إقامة {emp.name}",
            subtitle=(db.get(models.Company, rn.company_id).name if rn.company_id else ""),
            reference_no=reference_no,
        )
        mime = "application/pdf"
        ext = "pdf"
        content_bytes = pdf_bytes
    else:
        mime = "text/html"
        ext = "html"
        content_bytes = rendered.encode("utf-8")
    checksum = hashlib.sha256(content_bytes).hexdigest()

    # احفظ كـissued document على الموظف مربوط بالتجديد
    folder = os.path.join(settings.upload_dir, "gov_contracts")
    os.makedirs(folder, exist_ok=True)
    safe_ref = reference_no.replace("/", "_")
    fpath = os.path.join(folder, f"{safe_ref}.{ext}")
    with open(fpath, "wb") as f:
        f.write(content_bytes)

    # FIX — versioning: إعادة التوليد تأخذ version+1 وتُنزّل السابق (نسخة حالية واحدة فقط)
    doc_code = f"gov_contract_renewal_{rn.id}"
    prev = db.scalars(select(models.Document).where(
        models.Document.entity_type == "employee",
        models.Document.entity_id == emp.id,
        models.Document.document_type_code == doc_code,
    )).all()
    next_version = max((d.version for d in prev), default=0) + 1
    for d in prev:
        d.is_current = False

    doc = models.Document(
        company_id=rn.company_id, entity_type="employee", entity_id=emp.id,
        document_type_code=doc_code,
        title=f"العقد الحكومي — تجديد إقامة {emp.name}",
        file_path=fpath, mime=mime,
        version=next_version, is_current=True, uploaded_by=user.id,
        is_issued=True, reference_no=reference_no,
        template_version=tpl.version or 1, checksum_sha256=checksum,
        generated_at=datetime.utcnow(), generated_by=user.id,
    )
    db.add(doc)
    db.flush()
    audit(db, user, "generate_gov_contract", "residency_renewal", rn.id,
          detail=f"gov contract → {reference_no} ({ext})", request=request, company_id=rn.company_id)
    db.commit()

    if (format or "").lower() == "pdf":
        return FileResponse(fpath, filename=f"{safe_ref}.pdf", media_type=mime)
    return {
        "ok": True, "html": rendered,
        "document_id": doc.id, "reference_no": reference_no,
        "checksum_sha256": checksum,
        "note": "اطبع العقد → الموظف يوقّعه → ارفع النسخة الموقّعة عبر upload بـdoc_type=renewal_signed_gov",
    }
