# -*- coding: utf-8 -*-
"""تجديد الإقامة (DEMO-001/002): طلب مبكر/عادي + خطوات المندوب والموظف.

يعيد استخدام خزنة المستندات (Document) لحفظ العقود والنسخ الموقّعة وإذن العمل
والبطاقة المدنية مع الاحتفاظ بالنسخ القديمة.
"""
import os
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
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

    # المندوب يرفع العقدين (بانتظار رفع العقود)
    if doc_kind in R.CONTRACT_DOCS:
        if not is_pro:
            raise HTTPException(status_code=403, detail="رفع العقود خاص بالمندوب")
        if rn.status != R.AWAITING_CONTRACTS:
            raise HTTPException(status_code=409, detail="الحالة لا تسمح برفع العقود")
        await _save_doc(db, user, request, "renewal", rn.id, rn.company_id, doc_kind,
                        "عقد حكومي" if doc_kind == R.DOC_CONTRACT_GOV else "عقد داخلي", file)
        if all(_has(db, "renewal", rn.id, c) for c in R.CONTRACT_DOCS):
            rn.status = R.AWAITING_SIGNATURE
            _notify_stage(db, rn)

    # الموظف يرفع النسخ الموقّعة (بانتظار توقيع الموظف)
    elif doc_kind in R.SIGNED_DOCS:
        if not (is_owner_emp or is_pro):
            raise HTTPException(status_code=403, detail="خاص بالموظف صاحب الطلب")
        if rn.status != R.AWAITING_SIGNATURE:
            raise HTTPException(status_code=409, detail="الحالة لا تسمح برفع الموقّع")
        await _save_doc(db, user, request, "renewal", rn.id, rn.company_id, doc_kind,
                        "موقّع حكومي" if doc_kind == R.DOC_SIGNED_GOV else "موقّع داخلي", file)
        if all(_has(db, "renewal", rn.id, c) for c in R.SIGNED_DOCS):
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

    # الموظف يرفع البطاقة المدنية (مكتملة)
    elif doc_kind == R.DOC_CIVIL_CARD:
        if not (is_owner_emp or is_pro):
            raise HTTPException(status_code=403, detail="خاص بالموظف صاحب الطلب")
        if rn.status != R.AWAITING_CIVIL_CARD:
            raise HTTPException(status_code=409, detail="الحالة لا تسمح برفع البطاقة")
        await _save_doc(db, user, request, "employee", emp.id, rn.company_id,
                        R.DOC_CIVIL_CARD, "البطاقة المدنية الجديدة", file)
        rn.status = R.COMPLETED
        _notify_stage(db, rn)
    else:
        raise HTTPException(status_code=400, detail="نوع مستند غير معروف")

    db.commit()
    return _serialize(db, rn)
