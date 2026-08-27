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

from .. import gov_contract_docx, models, permissions, renewal as R
from ..permissions import ROLE_LABEL_AR
from ..config import settings
from ..database import get_db
from ..deps import assert_same_company, audit, get_current_user, get_user_perms
from ..notifications import (create_task, notify_employee_self, notify_from_template,
                             notify_roles, users_by_role)
from ..permissions import has_permission
from ..safe_files import read_limited, unique_path
from ..clock import today as kuwait_today
from ..storage import file_response, key_exists, save_at_key, save_bytes

router = APIRouter(prefix="/renewals", tags=["renewals"])


# ----------------------------- مساعدات -----------------------------

def _is_pro(user, perms):
    return (user.role == "super_admin" or has_permission(user.role, perms, "manage_permits")
            or has_permission(user.role, perms, "process_delegate_tasks"))


# RNW-12 — أنواع المستندات التي يُقرأ منها. القراءة **اقتراح** يُخزَّن في
# extracted_data_json ولا يُطبَّق: تاريخ انتهاء خاطئ يعني تنبيه تجديد خاطئ،
# ويعني موظًفا تنتهي إقامته والنظام يحسبها سارية.
OCR_DOC_TYPES = {
    R.DOC_WORK_PERMIT: "work_permit",
    R.DOC_CIVIL_CARD: "civil_id",
}

#: الحقول التي لا تُغلق المعاملة بدونها (RNW-13)
ESSENTIAL_FIELDS = {
    "new_expiry_date": "تاريخ الانتهاء الجديد",
    "new_permit_number": "رقم الإقامة الجديد",
}


def _ocr_proposal(db, entity_type: str, entity_id: int, doc_kind: str) -> None:
    """يقرأ آخر مستند مرفوع من هذا النوع ويحفظ الاقتراح — ولا يطبّقه.

    الفشل يُحفَظ بسببه الظاهر: العطل الموثَّق سابًقا لم يكن أن القراءة فشلت، بل
    أن النظام **مضى كأن شيًئا لم يحدث**. الاقتراح الفاشل يبقى مخزًَّنا بثقة صفر
    وسببٍ مكتوب، فتعرضه شاشة المراجعة وتطلب إدخالًا يدوًيا بدل الصمت.
    """
    ocr_code = OCR_DOC_TYPES.get(doc_kind)
    if not ocr_code:
        return
    doc = db.scalar(select(models.Document).where(
        models.Document.entity_type == entity_type,
        models.Document.entity_id == entity_id,
        models.Document.document_type_code == doc_kind,
        models.Document.is_current == True,  # noqa: E712
    ))
    if not doc or not doc.file_path:
        return
    from .. import ocr as ocr_engine
    try:
        data = ocr_engine.extract(ocr_code, doc.file_path)
    except Exception as exc:  # noqa: BLE001 — فشل القراءة لا يُسقط رفع المستند
        data = {"_provider": "error", "_confidence": 0.0,
                "_note": f"تعذّرت قراءة المستند: {type(exc).__name__}"}
    doc.extracted_data_json = data



def _gov_contract_context(db: Session, emp: models.Employee,
                          company: models.Company | None,
                          rn: models.ResidencyRenewal) -> dict:
    """حقول النموذج الرسمي التي لا يوفّرها سياق القوالب العام.

    كلها من مصدر السلطة في القاعدة، ولا شيء منها من payload الطلب: العقد
    يُقدَّم لجهة رسمية، ومن يستطيع تحرير أجره في نموذج يستطيع تزويره.
    """
    from ..clock import today as kuwait_today

    # GC-06 — رقم الإقامة الفعلي لا كود المستند الداخلي. الكود يُطبع في
    # خانة رسمية فيبدو رقم إقامة وهو معرّف داخلي لا يعرفه أحد خارج النظام.
    residence = db.scalar(select(models.Permit).where(
        models.Permit.employee_id == emp.id,
        models.Permit.kind == "residency",
    ).order_by(models.Permit.expiry_date.desc()))

    # إدارة العمل المختصّة تتبع محافظة مقرّ العمل. وموظف بلا فرع محدَّد
    # يتبع مقرّ الشركة — فيُؤخذ من أول فرع لها يحمل محافظة. اشتقاق من
    # بيانات الشركة لا قيمة مخترعة: العقد يُقدَّم للإدارة المسمّاة فيه.
    branch = db.get(models.Branch, emp.branch_id) if emp.branch_id else None
    if branch is None or not branch.governorate:
        branch = db.scalar(select(models.Branch).where(
            models.Branch.company_id == emp.company_id,
            models.Branch.governorate.isnot(None),
        ).order_by(models.Branch.id)) or branch
    today = kuwait_today()
    start = rn.new_expiry_date if getattr(rn, "new_expiry_date", None) else today

    # GC-05 — الأجر من الراتب المعتمد في النظام لا من payload الطلب
    wage = emp.basic_salary
    return {
        "residence_no": (residence.number if residence else "") or "",
        "company_rep_name": (company.representative_name if company else "") or "",
        "company_rep_name_en": (company.representative_name_en if company else "") or "",
        "company_civil_id": (company.representative_civil_id if company else "") or "",
        "labour_dept": (branch.governorate if branch else "") or "",
        "labour_dept_en": (branch.governorate_en if branch else "") or "",
        "wage": ("" if wage is None else str(wage)),
        "contract_date": today.strftime("%d/%m/%Y"),
        "contract_start_date": start.strftime("%d/%m/%Y"),
        "day_name_en": today.strftime("%A"),
        "contract_term_ar": "سنة",
        "contract_term_en": "ONE YEAR",
    }


def _generated_contract_doc(db, rn):
    """النسخة المولّدة السارية من العقد الحكومي لهذه المعاملة.

    تُستعمل لربط ما يوقّعه الموظف بما وُلّد له بالضبط — انظر RNW-08.
    """
    emp_id = rn.employee_id
    return db.scalar(select(models.Document).where(
        models.Document.entity_type == "employee",
        models.Document.entity_id == emp_id,
        models.Document.document_type_code == f"gov_contract_renewal_{rn.id}",
        models.Document.is_current == True,  # noqa: E712
    ))


def _open_case_for_permit(db, permit_id: int):
    """المعاملة المفتوحة لهذه الإقامة إن وُجدت — المصدر الواحد للشرط.

    كان الشرط مكتوًبا مرتين بصيغتين مختلفتين: حارس الإنشاء يقيس على
    ``permit_id`` وقائمة "تستحق ولم يُفتح لها ملف" تقيس على ``employee_id``.
    فموظف له إقامتان يظهر تنبيهه مخفًيا بينما الإنشاء يسمح — وهو نفس النمط
    الذي نتجنّبه: قاعدة واحدة في مكانين تنحرف.
    """
    return db.scalar(select(models.ResidencyRenewal).where(
        models.ResidencyRenewal.permit_id == permit_id,
        models.ResidencyRenewal.status.notin_([R.REJECTED, R.COMPLETED])))


def _get_renewal(db, user, rid) -> models.ResidencyRenewal:
    rn = db.get(models.ResidencyRenewal, rid)
    if not rn:
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة")
    assert_same_company(user, rn.company_id, db=db)
    return rn


async def _save_doc(db, user, request, entity_type, entity_id, company_id,
                    code, title, upload: UploadFile, expiry_date: date | None = None,
                    source_document_id: int | None = None):
    """يحفظ ملفًا كمستند بنُسخ (الأحدث is_current) — يُبقي القديم."""
    import hashlib

    # AWS-01 — عبر طبقة التخزين لا على القرص مباشرة
    payload = await read_limited(upload)
    fpath = save_bytes(payload, "renewals", upload.filename,
                       prefix=f"{entity_type}_{entity_id}_{code}_")
    # RNW-23 — بصمة الملف كما رُفع. النظام لا يولّد مستنًدا حكومًيا بشعار
    # حكومي؛ يحفظ الملف الحقيقي الصادر عن الجهة. والبصمة هي ما يثبت لاحًقا
    # أن الملف المعروض هو نفسه المرفوع ولم يُستبدل — بلا هذا فحفظه إيداع
    # بلا إثبات.
    checksum = hashlib.sha256(payload).hexdigest()
    prev = db.scalars(select(models.Document).where(
        models.Document.entity_type == entity_type, models.Document.entity_id == entity_id,
        models.Document.document_type_code == code, models.Document.is_current == True)).all()  # noqa: E712
    ver = max((d.version for d in prev), default=0) + 1
    for d in prev:
        d.is_current = False
    doc = models.Document(company_id=company_id, entity_type=entity_type, entity_id=entity_id,
                          document_type_code=code, title=title, file_path=fpath,
                          mime=upload.content_type, expiry_date=expiry_date,
                          version=ver, is_current=True, uploaded_by=user.id,
                          source_document_id=source_document_id,
                          checksum_sha256=checksum)
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
    days_left = (permit.expiry_date - kuwait_today()).days
    rtype = R.classify(days_left)
    if rtype is None:
        raise HTTPException(status_code=400,
                            detail="لا يمكن التجديد قبل 90 يومًا من الانتهاء")
    if rtype == "early" and not (reason and reason.strip()):
        raise HTTPException(status_code=400, detail="سبب التجديد المبكر إلزامي")

    # منع تكرار معاملة مفتوحة لنفس الإقامة
    open_exists = _open_case_for_permit(db, permit.id)
    if open_exists:
        # الضغط مرتين على "بدء المعاملة" لا ينشئ اثنتين — نعيد القائمة برقمها
        # بدل رسالة خطأ عمياء، فالواجهة تفتحها بدل أن تُظهر فشًلا للمستخدم.
        raise HTTPException(
            status_code=409,
            detail=f"توجد معاملة تجديد مفتوحة لهذه الإقامة (رقم {open_exists.id})")

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
    if not _is_pro(user, perms) and not any(has_permission(user.role, perms, x) for x in permissions.APPROVAL_PERMS) \
            and user.role not in ("super_admin", "company_owner"):
        q = q.where(models.ResidencyRenewal.employee_id == (user.employee_id or -1))
    return [_serialize(db, rn) for rn in db.scalars(q).all()]


@router.get("/{rid}")
def get_renewal(rid: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    rn = _get_renewal(db, user, rid)
    perms = get_user_perms(user, db)
    if not _is_pro(user, perms) and not any(has_permission(user.role, perms, x) for x in permissions.APPROVAL_PERMS) \
            and user.employee_id != rn.employee_id and user.role not in ("super_admin", "company_owner"):
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة")
    return _serialize(db, rn)


@router.get("/{rid}/document/{doc_type}")
def download_renewal_document(rid: int, doc_type: str,
                              user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """تنزيل مستند تجديد (عقد/موقّع) أو مستند الموظف المرتبط (إذن عمل/بطاقة مدنية)."""
    rn = _get_renewal(db, user, rid)
    perms = get_user_perms(user, db)
    if not _is_pro(user, perms) and not any(has_permission(user.role, perms, x) for x in permissions.APPROVAL_PERMS) \
            and user.employee_id != rn.employee_id and user.role not in ("super_admin", "company_owner"):
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة")

    if doc_type in R.ALL_CONTRACT_DOCS:
        entity_type, entity_id = "renewal", rn.id
    elif doc_type in (R.DOC_WORK_PERMIT, R.DOC_CIVIL_CARD):
        entity_type, entity_id = "employee", rn.employee_id
    else:
        raise HTTPException(status_code=400, detail="نوع مستند غير معروف")

    doc = db.scalar(select(models.Document).where(
        models.Document.entity_type == entity_type, models.Document.entity_id == entity_id,
        models.Document.document_type_code == doc_type, models.Document.is_current == True))  # noqa: E712
    if not doc or not doc.file_path or not key_exists(doc.file_path):
        raise HTTPException(status_code=404, detail="لا توجد نسخة محفوظة")
    return file_response(doc.file_path, filename=os.path.basename(doc.file_path),
                        media_type=doc.mime or "application/octet-stream")


# ----------------------------- موافقات (مبكر) -----------------------------

@router.post("/{rid}/decide")
def decide_renewal(rid: int, decision: str = Form(...), reject_reason: str | None = Form(None),
                   request: Request = None,
                   user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """موافقة/رفض مرحلة (المدير ثم الشؤون) للتجديد المبكر."""
    rn = _get_renewal(db, user, rid)
    perms = get_user_perms(user, db)
    if not any(has_permission(user.role, perms, x) for x in permissions.APPROVAL_PERMS):
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
        # RNW-08 — الربط بالنسخة المولّدة السارية وقت التوقيع، لا بالمعاملة وحدها
        src = _generated_contract_doc(db, rn)
        await _save_doc(db, user, request, "renewal", rn.id, rn.company_id, doc_kind,
                        "موقّع حكومي" if doc_kind == R.DOC_SIGNED_GOV else "موقّع داخلي", file,
                        source_document_id=(src.id if src else None))
        if all(_has(db, "renewal", rn.id, c) for c in R.REQUIRED_SIGNED_DOCS):
            rn.status = R.CONTRACTS_SIGNED
            _notify_stage(db, rn)

    # RNW-09 — النسخة الثالثة: العقد بتوقيع الطرفين. يرفعها المندوب بعد توقيع
    # صاحب الشركة خارج النظام، أثناء الإجراءات الحكومية. لا تُغيّر الحالة —
    # نسخة الموظف ليست نهائية، وهذه لا تمسح ما قبلها.
    elif doc_kind == R.DOC_CONTRACT_FINAL:
        if not is_pro:
            raise HTTPException(status_code=403, detail="النسخة النهائية يرفعها المندوب")
        if rn.status not in (R.CONTRACTS_SIGNED, R.RENEWING):
            raise HTTPException(
                status_code=409,
                detail="النسخة النهائية تُرفع بعد رفع الموظف نسخته الموقّعة")
        # النهائية تشير إلى نسخة الموظف: سلسلة إثبات كاملة من المولّدة إلى
        # ما قُدّم للجهة الحكومية، كل حلقة تعرف سابقتها.
        signed = db.scalar(select(models.Document).where(
            models.Document.entity_type == "renewal", models.Document.entity_id == rn.id,
            models.Document.document_type_code == R.DOC_SIGNED_GOV,
            models.Document.is_current == True))  # noqa: E712
        await _save_doc(db, user, request, "renewal", rn.id, rn.company_id, doc_kind,
                        "العقد النهائي — بتوقيع الطرفين", file,
                        source_document_id=(signed.id if signed else None))

    # المندوب يرفع إذن العمل الجديد (جاري التجديد → بانتظار البطاقة)
    elif doc_kind == R.DOC_WORK_PERMIT:
        if not is_pro:
            raise HTTPException(status_code=403, detail="خاص بالمندوب")
        if rn.status != R.RENEWING:
            raise HTTPException(status_code=409, detail="عيّن الحالة (جاري التجديد) أولًا")
        await _save_doc(db, user, request, "employee", emp.id, rn.company_id,
                        R.DOC_WORK_PERMIT, "إذن العمل الجديد", file)
        _ocr_proposal(db, "employee", emp.id, doc_kind)  # RNW-12 — اقتراح لا تطبيق
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
        _ocr_proposal(db, "employee", emp.id, doc_kind)  # RNW-12 — اقتراح لا تطبيق
        rn.status = R.PENDING_HR_VERIFY
        _notify_stage(db, rn)
    else:
        raise HTTPException(status_code=400, detail="نوع مستند غير معروف")

    db.commit()
    return _serialize(db, rn)


# ==============================================================================
# RNW-12/13 — مراجعة ما قرأه النظام قبل اعتماده
# ==============================================================================
#: عتبة الثقة التي دونها يلزم تأكيد صريح. ليست رقًما تعسفًيا: قارئ البطاقة
#: يبدأ من 0.5 ويزيد 0.08 لكل حقل يُستخرج، فما دون 0.7 يعني أن أقلّ من ثلاثة
#: حقول قُرئت — أي أن الصورة رديئة ولا يُبنى على قراءتها.
LOW_CONFIDENCE = 0.7

#: ما يهمّ التجديد من كل مستند
OCR_FIELDS_OF_INTEREST = {
    R.DOC_WORK_PERMIT: ("expiry_date", "doc_number"),
    R.DOC_CIVIL_CARD: ("civil_id", "expiry_date"),
}


def _closure_blockers(db, rn) -> list[str]:
    """RNW-17/18 — ما ينقص لإغلاق المعاملة، مسمًّى بالضبط.

    «بيانات ناقصة» ليست رسالة: المندوب يقف أمامها ولا يعرف أين يذهب. القائمة
    هنا تسمّي المستند أو الحقل باسمه، فالإغلاق يُرفض ويُشرح في آنٍ واحد.
    """
    missing = []
    for key, label in ESSENTIAL_FIELDS.items():
        if not getattr(rn, key, None):
            missing.append(label)
    if not rn.gov_reference_no:
        missing.append("الرقم المرجعي للمعاملة الحكومية")

    required_docs = {
        R.DOC_CONTRACT_GOV: "العقد الحكومي",
        R.DOC_SIGNED_GOV: "العقد موقًَّعا من الموظف",
        R.DOC_WORK_PERMIT: "إذن العمل الجديد",
    }
    for kind, label in required_docs.items():
        entity = "employee" if kind == R.DOC_WORK_PERMIT else "renewal"
        entity_id = rn.employee_id if kind == R.DOC_WORK_PERMIT else rn.id
        if not _has(db, entity, entity_id, kind):
            missing.append(label)
    return missing


#: ما يُودَع في ملف الموظف عند الاكتمال، وتحت أي نوع.
#: إذن العمل والبطاقة يُحفظان في ملف الموظف عند رفعهما أصًلا؛ الناقص كان
#: العقد النهائي — يبقى محبوًسا داخل المعاملة، فمن يفتح ملف الموظف بعد سنة
#: لا يجد العقد الذي قُدّم للجهة الحكومية.
FILED_TO_EMPLOYEE = {R.DOC_CONTRACT_FINAL: "gov_contract"}


def _file_documents_to_employee(db, rn, user) -> list[str]:
    """RNW-14 — يودع مستندات المعاملة النهائية في ملف الموظف تحت أنواعها.

    لا يُنسخ الملف: الصفّ الجديد يشير إلى نفس المسار ونفس البصمة، ويحمل
    ``source_document_id`` إلى نسخة المعاملة. فالمستند واحد، مفهرس في مكانين،
    ولا تنشأ نسختان تتباعدان.
    """
    filed = []
    for kind, employee_code in FILED_TO_EMPLOYEE.items():
        src = db.scalar(select(models.Document).where(
            models.Document.entity_type == "renewal",
            models.Document.entity_id == rn.id,
            models.Document.document_type_code == kind,
            models.Document.is_current == True))  # noqa: E712
        if not src:
            continue
        already = db.scalar(select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == rn.employee_id,
            models.Document.source_document_id == src.id))
        if already:
            continue
        prev = db.scalars(select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == rn.employee_id,
            models.Document.document_type_code == employee_code,
            models.Document.is_current == True)).all()  # noqa: E712
        for d in prev:
            d.is_current = False  # RNW-15 — تصير History ولا تُحذف
        db.add(models.Document(
            company_id=rn.company_id, entity_type="employee", entity_id=rn.employee_id,
            document_type_code=employee_code,
            title=f"العقد الحكومي النهائي — تجديد #{rn.id}",
            file_path=src.file_path, mime=src.mime,
            version=max((d.version for d in prev), default=0) + 1,
            is_current=True, uploaded_by=user.id,
            source_document_id=src.id, checksum_sha256=src.checksum_sha256,
        ))
        filed.append(employee_code)
    return filed


def _close_renewal_tasks(db, rn) -> int:
    """RNW-19 — يغلق مهام المعاملة المفتوحة عند اكتمالها.

    كانت تبقى مفتوحة في صندوق المهام بعد انتهاء التجديد، فيرى المندوب والموظف
    مطلوًبا منهما إجراء لا وجود له — وصندوق مهام يمتلئ بما انتهى يفقد معناه.
    """
    open_tasks = db.scalars(select(models.Task).where(
        models.Task.related_entity_type == "renewal",
        models.Task.related_entity_id == rn.id,
        models.Task.status.in_(("open", "in_progress")),
    )).all()
    for task in open_tasks:
        task.status = "dismissed"
        task.completed_at = datetime.utcnow()
    return len(open_tasks)


#: الحدث في سجل التدقيق ← اسمه في القصة. الترجمة هنا لا في الواجهة:
#: القصة تُقرأ من الـAPI أيًضا (تصدير، تقرير، تدقيق خارجي)، فلو عاشت
#: الأسماء في الواجهة وحدها لخرجت الأحداث بأكوادها التقنية لكل قارئ آخر.
TIMELINE_LABELS = {
    "create_renewal": "بدأت معاملة التجديد",
    "generate_gov_contract": "وُلّد العقد الحكومي",
    "renewal_upload": "رُفع مستند",
    "renewal_approved": "اعتُمدت المرحلة",
    "renewal_rejected": "رُفضت المعاملة",
    "renewal_renewing": "بدأت الإجراءات الحكومية",
    "finalize_renewal": "سُجّلت بيانات المعاملة الحكومية",
    "hr_verify_renewal": "التحقق النهائي واكتمال المعاملة",
}


@router.get("/{rid}/timeline")
def renewal_timeline(rid: int, user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """RNW-21 — قصة المعاملة كاملة من التنبيه إلى المستند النهائي.

    ROOT CAUSE: كل حدث كان يُسجَّل في سجل التدقيق منذ البداية — الفاعل ووقته
    والكيان — لكن **لم يكن ثمّة ما يعرضه كقصة**. فمن يفتح معاملة مكتملة يرى
    حالتها الأخيرة ولا يعرف كيف وصلت إليها: من بدأها، ومن اعتمد، ومتى رُفع
    كل مستند. والسؤال يُطرح بعد شهور حين تُراجَع معاملة أو يُعترض عليها.

    تُبنى من ``AuditLog`` لا من جدول جديد: البيانات موجودة، وجدول ثانٍ يعني
    مصدرين لقصة واحدة — وأحدهما سينحرف.
    """
    rn = _get_renewal(db, user, rid)
    perms = get_user_perms(user, db)
    if not _is_pro(user, perms) and user.employee_id != rn.employee_id             and user.role not in ("super_admin", "company_owner", "hr"):
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة")

    rows = db.scalars(select(models.AuditLog).where(
        models.AuditLog.entity_type.in_(("renewal", "residency_renewal")),
        models.AuditLog.entity_id == rn.id,
    ).order_by(models.AuditLog.created_at)).all()

    users = {}
    events = []

    # الحدث الأول ليس في السجل: التنبيه سبق المعاملة ولا فاعل له.
    permit = db.get(models.Permit, rn.permit_id) if rn.permit_id else None
    events.append({
        "action": "expiry_detected",
        "label": "اكتُشف قرب انتهاء الإقامة",
        "actor": None, "actor_role": "النظام",
        "at": rn.created_at, "renewal_id": rn.id,
        "reference": (permit.number if permit else None),
    })

    for row in rows:
        actor = users.get(row.user_id)
        if actor is None and row.user_id:
            actor = users[row.user_id] = db.get(models.User, row.user_id)
        events.append({
            "action": row.action,
            "label": TIMELINE_LABELS.get(row.action, row.action),
            "actor": (actor.full_name if actor else None),
            "actor_role": (ROLE_LABEL_AR.get(actor.role, actor.role) if actor else "النظام"),
            "at": row.created_at,
            "renewal_id": rn.id,
            "reference": row.detail,
        })

    return {
        "renewal_id": rn.id,
        "employee_id": rn.employee_id,
        "company_id": rn.company_id,
        "status": rn.status,
        "events": events,
    }


@router.get("/{rid}/closure-check")
def closure_check(rid: int, user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """RNW-17 — هل تكتمل شروط الإغلاق؟ وما الناقص إن لم تكتمل."""
    rn = _get_renewal(db, user, rid)
    perms = get_user_perms(user, db)
    if not _is_pro(user, perms) and user.role not in ("super_admin", "company_owner", "hr"):
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة")
    missing = _closure_blockers(db, rn)
    return {"renewal_id": rn.id, "can_close": not missing, "missing": missing}


@router.get("/{rid}/extracted")
def extracted_values(rid: int, user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """RNW-12 — القيم التي قرأها النظام، معروضة للمراجعة قبل الاعتماد.

    لا تُطبَّق شيًئا. تُخرِج لكل حقل: قيمته المقترحة ودرجة ثقته والمستند الذي
    قُرئ منه وحالته. والحقل الذي فشل استخراجه **يظهر فارًغا مع سبب** ولا يُخفى
    — إخفاؤه هو ما جعل عطًلا سابًقا يمرّ صامًتا.
    """
    rn = _get_renewal(db, user, rid)
    perms = get_user_perms(user, db)
    if not _is_pro(user, perms) and user.role not in ("super_admin", "company_owner", "hr"):
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة")

    rows = []
    for doc_kind, fields in OCR_FIELDS_OF_INTEREST.items():
        doc = db.scalar(select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == rn.employee_id,
            models.Document.document_type_code == doc_kind,
            models.Document.is_current == True,  # noqa: E712
        ))
        if not doc:
            continue
        data = doc.extracted_data_json or {}
        conf = float(data.get("_confidence") or 0.0)
        for field in fields:
            value = data.get(field)
            if not value:
                status, needs = "failed", True
            elif conf < LOW_CONFIDENCE:
                status, needs = "low_confidence", True
            else:
                status, needs = "high_confidence", False
            rows.append({
                "document_kind": doc_kind, "document_id": doc.id,
                "field": field, "value": value,
                "confidence": conf, "status": status,
                "needs_confirmation": needs,
                "note": data.get("_note"),
                "provider": data.get("_provider"),
            })

    confirmed = rn.confirmed_data_json or {}
    missing = [label for key, label in ESSENTIAL_FIELDS.items()
               if not (getattr(rn, key, None) or confirmed.get(key, {}).get("value"))]
    return {
        "renewal_id": rn.id,
        "fields": rows,
        "confirmed": confirmed,
        "missing_essential": missing,
        "can_close": not missing,
    }


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
    if new_expiry_date <= kuwait_today():
        raise HTTPException(status_code=400,
                          detail="تاريخ انتهاء الإقامة الجديد يجب أن يكون في المستقبل")

    rn.gov_reference_no = gov_reference_no.strip()
    rn.fees_amount = fees_amount
    rn.fees_receipt_no = fees_receipt_no.strip()
    rn.new_permit_number = new_permit_number.strip()
    rn.new_expiry_date = new_expiry_date
    rn.finalized_at = datetime.utcnow()
    rn.finalized_by = user.id

    # RNW-12 — سجلّ المصدر: القيمة المعتمَدة تُقارَن بما قرأه النظام، فيُعرف
    # أهي قراءة آلية قُبِلت كما هي، أم تصحيح بشري لها، أم إدخال يدوي محض.
    # التمييز مهمّ: "صُحِّحت" تعني أن القارئ أخطأ وتستحقّ متابعة، و"يدوي"
    # تعني أنه لم يقرأ شيًئا أصلًا.
    proposals = {}
    for doc_kind in OCR_FIELDS_OF_INTEREST:
        d = db.scalar(select(models.Document).where(
            models.Document.entity_type == "employee",
            models.Document.entity_id == rn.employee_id,
            models.Document.document_type_code == doc_kind,
            models.Document.is_current == True))  # noqa: E712
        if d and d.extracted_data_json:
            proposals[doc_kind] = d.extracted_data_json

    def _provenance(field: str, value):
        for kind, data in proposals.items():
            proposed = data.get("expiry_date" if field == "new_expiry_date" else field)
            if proposed:
                same = str(proposed)[:10] == str(value)[:10]
                return {"value": str(value), "source": "ocr" if same else "corrected",
                        "confidence": data.get("_confidence"),
                        "document_kind": kind, "ocr_value": str(proposed)}
        return {"value": str(value), "source": "manual", "confidence": None}

    record = {k: _provenance(k, getattr(rn, k)) for k in ESSENTIAL_FIELDS}
    for entry in record.values():
        entry["confirmed_by"] = user.id
        entry["confirmed_at"] = datetime.utcnow().isoformat()
    rn.confirmed_data_json = record
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
    # RNW-17/18 — الإغلاق مشروط بفحص اكتمال يسمّي الناقص، لا بضغطة «تم»
    blockers = _closure_blockers(db, rn)
    if blockers:
        raise HTTPException(
            status_code=400,
            detail="لا يمكن إغلاق المعاملة — الناقص: " + "، ".join(blockers))
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
        start_date=kuwait_today(), expiry_date=rn.new_expiry_date,
        status="active",
    )
    db.add(new_permit)

    _file_documents_to_employee(db, rn, user)  # RNW-14 — لا يبقى محبوًسا في المعاملة
    closed = _close_renewal_tasks(db, rn)  # RNW-19
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
    ctx.update(_gov_contract_context(db, emp, company, rn))
    # RNW-06 — لا توليد بحقل ناقص. _fill_html يستبدل المفقود بـ"................"
    # فينتج عقد حكومي بمربّعات فارغة يوقّعه الموظف ويُقدَّم لجهة رسمية. نرفض
    # ونسمّي الناقص بالعربية ليعرف المندوب أين يذهب ليصلحه.
    missing = [label for key, label in R.GOV_CONTRACT_REQUIRED_FIELDS.items()
               if not str(ctx.get(key) or "").strip()]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=("تعذّر توليد العقد الحكومي — بيانات ناقصة في ملف الموظف أو الشركة: "
                    + "، ".join(missing) + ". أكملها ثم أعد التوليد."))

    reference_no = _generate_reference_no(db, "GOV-REN", rn.company_id, tpl.version or 1)
    ctx["ref_no"] = reference_no

    # GC-01/GC-02 — العقد يُولَّد من نموذج الهيئة الرسمي نفسه، لا من قالب
    # HTML يقلّده. القالب في القاعدة يبقى مرجًعا للنسخة ورقم الإصدار،
    # والمحتوى يأتي من ملف الوورد ببصمته الأصلية.
    content_bytes, ext, mime, docx_missing = gov_contract_docx.generate(ctx)
    if docx_missing:
        raise HTTPException(
            status_code=400,
            detail=("تعذّر توليد العقد الحكومي — بيانات ناقصة: "
                    + "، ".join(docx_missing) + ". أكملها ثم أعد التوليد."))
    checksum = hashlib.sha256(content_bytes).hexdigest()

    # احفظ كـissued document على الموظف مربوط بالتجديد
    # AWS-01 — عبر طبقة التخزين. المفتاح محدَّد لأن الرقم المرجعي جزء
    # من هويّة العقد الحكومي ويُطبع عليه.
    safe_ref = reference_no.replace("/", "_")
    fpath = save_at_key(content_bytes, f"gov_contracts/{safe_ref}.{ext}")

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

    # GC-01 — لم يعد هناك «html» يُعاد للواجهة: العقد ملف بتخطيط الهيئة
    # (PDF، أو docx إن غاب LibreOffice عن البيئة) يُنزَّل لا يُعرض في صفحة.
    # وإعادة HTML مقلّد كانت هي المشكلة الأصلية.
    if (format or "").lower() in ("pdf", "file", "download"):
        return file_response(fpath, filename=f"{safe_ref}.{ext}", media_type=mime)
    return {
        "ok": True,
        "format": ext,
        "download_url": f"/api/renewals/{rn.id}/gov-contract?format=file",
        "document_id": doc.id, "reference_no": reference_no,
        "checksum_sha256": checksum,
        "note": "اطبع العقد → الموظف يوقّعه → ارفع النسخة الموقّعة عبر upload بـdoc_type=renewal_signed_gov",
    }


@router.get("/due/permits")
def permits_due_without_case(user: models.User = Depends(get_current_user),
                             db: Session = Depends(get_db)):
    """QA-05 — إقامات تستحق التجديد ولم يُفتح لها ملف بعد.

    ROOT CAUSE: صفحة التجديدات تعرض ملفات ResidencyRenewal — أي إجراءات
    بُدئت فعًلا — بينما مركز العمليات يعرض الإقامات المقتربة من الانتهاء.
    فرأى المستخدم "حالة حرجة" هناك وصفحة فارغة هنا، وقرأ الفراغ كعطل. الرقمان
    صحيحان لكنهما عن شيئين مختلفين، ولم يكن في الواجهة ما يقول ذلك.

    هذه النقطة تصل بينهما: ما يستحق فتح ملف ولم يُفتح له.
    """
    from datetime import timedelta

    today = kuwait_today()
    soon = today + timedelta(days=90)
    q = select(models.Permit).where(
        models.Permit.kind == "residency",
        models.Permit.status == "active",
        models.Permit.expiry_date.isnot(None),
        models.Permit.expiry_date <= soon,
    )
    if user.role not in ("super_admin", "company_owner"):
        q = q.where(models.Permit.company_id == user.company_id)

    out = []
    for p in db.scalars(q.order_by(models.Permit.expiry_date)).all():
        if _open_case_for_permit(db, p.id):
            continue
        emp = db.get(models.Employee, p.employee_id)
        # RNW-01 — المواصفة تطلب اسم الموظف والشركة والفرع. الفرع كان ناقًصا،
        # والمندوب يحتاجه ليعرف أين يذهب قبل أن يبدأ.
        branch = db.get(models.Branch, emp.branch_id) if emp and emp.branch_id else None
        company = db.get(models.Company, p.company_id)
        out.append({
            "permit_id": p.id, "employee_id": p.employee_id,
            "employee_name": emp.name if emp else None,
            "employee_no": emp.employee_no if emp else None,
            "job_title": emp.job_title if emp else None,
            "company_id": p.company_id,
            "company_name": company.name if company else None,
            "branch_id": emp.branch_id if emp else None,
            "branch_name": branch.name if branch else None,
            "number": p.number, "expiry_date": p.expiry_date,
            "days_left": (p.expiry_date - today).days,
        })
    return out
