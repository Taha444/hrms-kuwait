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

from .. import gov_contract_data, gov_contract_form, models, permissions, renewal as R
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


def _ocr_proposal(db, entity_type: str, entity_id: int, doc_kind: str,
                  renewal_id: int | None = None) -> None:
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

    # P4-22 — قراءة المستند حدث في القصة، لا خطوة صامتة.
    #
    # كانت النتيجة تُحفَظ في المستند ولا تُسجَّل. فمن يقرأ خطّ الزمن بعد
    # شهور يرى «رُفعت البطاقة المدنية» ثم «سُجّلت بيانات المعاملة»، ولا
    # يعرف هل قرأها النظام أم أُدخلت يدًوا، ولا بأي ثقة.
    #
    # وهو ما تحرسه القاعدة 14: لا تحديث صامت عند ضعف الثقة. والصمت في
    # السجلّ نصف التحديث الصامت.
    conf = float(data.get("_confidence") or 0.0)
    outcome = ("فشلت القراءة" if data.get("_provider") == "error"
               else "ثقة منخفضة — تحتاج تأكيًدا" if conf < LOW_CONFIDENCE
               else "ثقة عالية")
    audit(db, None, "renewal_ocr_read", entity_type, entity_id,
          detail=f"{doc_kind}: {outcome} ({conf:.2f})",
          company_id=getattr(doc, "company_id", None))
    # **والحدث في قصّته**: التايملاين يقرأ ما سُجِّل باسم المعاملة،
    # وهذا كان يُسجَّل باسم الموظف وحده. فقراءة النظام للمستند — وهي
    # نصف قصّة التجديد: ماذا قرأ وبأي ثقة — لا تظهر في خطّ المعاملة.
    #
    # ولا يُنزَع من ملف الموظف: مستنده وقراءته تخصّانه أيًضا. سطران
    # لحدث واحد أصدق من سطر في المكان الخطأ.
    if renewal_id is not None and entity_type != "renewal":
        audit(db, None, "renewal_ocr_read", "renewal", renewal_id,
              detail=f"{doc_kind}: {outcome} ({conf:.2f})",
              company_id=getattr(doc, "company_id", None))




#: قواعدُ حقول العقد الحكومي في ``gov_contract_data`` — مصدرٌ واحد يقرؤه
#: مسارُ التجديد ومسارُ التعيين معًا (كانت هنا وحدها، والورقة واحدة).
APPROVED_PAYROLL_STATUSES = gov_contract_data.APPROVED_PAYROLL_STATUSES
_approved_wage = gov_contract_data.approved_wage


def _gov_contract_context(db: Session, emp: models.Employee,
                          company: models.Company | None,
                          rn: models.ResidencyRenewal,
                          representative_id: int | None = None) -> dict:
    start = rn.new_expiry_date if getattr(rn, "new_expiry_date", None) else None
    return gov_contract_data.contract_context(db, emp, company, start_date=start,
                                              representative_id=representative_id)


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


def _renewal_branch_allowed(db, user, employee_id: int) -> bool:
    """نطاقُ الفرع على المعاملة كما هو على ملف الموظف (``_get_emp``).

    كان التحقّق شركًة واحدة لا فرًعا، والقراءُة مفتوحٌة لكل من يملك صلاحيَة
    اعتماد — ومسؤوُل الفرع منهم. فكان يسرد معاملاِت فرٍع آخر ويُنزّل البطاقَة
    المدنيَة لموظّفيه، والملفُّ الذي يحملها مغلٌق أمامه بنطاق فرعه.
    """
    from ..deps import resolve_scope
    sc = resolve_scope(user, db)
    if sc.self_employee_id is not None and employee_id != sc.self_employee_id:
        return False
    if sc.branch_ids is not None:
        emp = db.get(models.Employee, employee_id)
        if emp is None or emp.branch_id not in sc.branch_ids:
            return False
    return True


def _get_renewal(db, user, rid) -> models.ResidencyRenewal:
    rn = db.get(models.ResidencyRenewal, rid)
    if not rn:
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة")
    assert_same_company(user, rn.company_id, db=db)
    # والموظفُ صاحبُ المعاملة يراها دائمًا — هي معاملته.
    if user.employee_id != rn.employee_id and not _renewal_branch_allowed(
            db, user, rn.employee_id):
        audit(db, user, "FORBIDDEN_SCOPE_ACCESS", "renewal", rn.id,
              detail="branch_out_of_scope")
        db.commit()
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة")
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
    from .documents import _close_expiry_tasks_for
    for d in prev:
        d.is_current = False
        # إذنُ العمل والبطاقةُ المدنية لهما تنبيهُ انتهاءٍ مربوطٌ بمعرّف **النسخة**: تُستبدَل بالجديدة
        # فيبقى التنبيهُ مفتوحًا على نسخةٍ لم تعد تُراقَب (كما يُغلَق في رفع المستندات والأرشيف).
        _close_expiry_tasks_for(db, d.id)
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
    # M15 — ``permit_id`` المُرسَل كان يُحمَّل بلا نسبٍ لصاحبه: مندوبُ شركةٍ ربط معاملته
    # بإقامة موظفٍ في **شركةٍ أخرى** (قيس 201)، فتُحسب مدتُها ونوعُ تجديدها منها، وينتهي
    # الإنهاء بالكتابة على إقامة غيره. فالإقامة تخصّ **هذا الموظف**، وفعّالة، وإقامة.
    if (permit.employee_id != eid or permit.company_id != emp.company_id
            or permit.kind != "residency" or permit.status != "active"):
        raise HTTPException(status_code=404, detail="لا توجد إقامة سارية بهذا الرقم لهذا الموظف")

    # **ولا تُجدَّد إقامةُ من انتهت خدمته** — بابٌ ثالثٌ للقاعدة الموحَّدة
    # ``INACTIVE_EMPLOYMENT``: ``create_request`` يمنعه والبصمُ يمنعه، وملفُّ
    # التجديد كان يُفتح له. والتجديدُ معاملةٌ حكوميةٌ برسومها والتزامها،
    # وإقامةُ من غادر تُحسم بالإلغاء أو التحويل لا بالتجديد.
    from ..deps import INACTIVE_EMPLOYMENT
    _emp = db.get(models.Employee, permit.employee_id)
    if _emp and (_emp.status or "").strip().lower() in INACTIVE_EMPLOYMENT:
        raise HTTPException(
            status_code=409,
            detail=(f"لا يُفتح تجديدُ إقامةٍ لموظفٍ حالته «{_emp.status}» — "
                    "إقامةُ من انتهت خدمته تُحسم بالإلغاء أو التحويل."))
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


#: TSK-01 — بادئة مفتاح المهمة لكل مرحلة. تُقرأ هنا لا تُستنتج من النصّ:
#: بها يُعرف ما ينتمي للمرحلة الحالية وما بقي من مرحلة مضت.
#: (والمراحل الغائبة عن الخريطة لا تُنشئ مهمة أصًلا.)
STAGE_TASK_PREFIX = {
    R.PENDING_MANAGER: "renewal_mgr:",
    R.PENDING_HR: "renewal_hr:",
    R.AWAITING_CONTRACTS: "renewal_pro:",
    R.AWAITING_SIGNATURE: "renewal_sign:",
    R.CONTRACTS_SIGNED: "renewal_signed:",
    R.AWAITING_CIVIL_CARD: "renewal_card:",
    # **وبصمٌة ناقصٌة تُغلق ما أُرسل للتوّ.** ``_close_superseded_stage_tasks``
    # تُبقي بصمَة المرحلة الحالية وتُغلق ما عداها، فمرحلٌة بلا بصمٍة هنا
    # تُغلَق مهمُّتها في النداء نفسه الذي أنشأها.
    R.PENDING_HR_VERIFY: "renewal_verify:",
    R.COMPLETED: "renewal_done:",
}


def _close_superseded_stage_tasks(db, rn) -> int:
    """يغلق مهام المراحل التي مضت.

    **العطل**: كل مرحلة تُنشئ مهمتها بمفتاح مستقلّ ولا تغلق ما قبلها،
    فتتراكم على المعاملة الواحدة مهام لمراحل انتهت. صندوق يمتلئ بما لم
    يعد مطلوًبا يُقرأ كأنه عمل متأخّر، فيُهمَل كلّه.

    والإغلاق **بالبادئة لا بالكنس الشامل**: كنس كل مهام المعاملة ثم
    إعادة إنشاء مهمة المرحلة الحالية يبدو مكافًئا وهو ليس كذلك — المهمة
    القائمة تُغلق ويُنشأ صفّ جديد مكانها عند كل نداء، فيتحوّل منع
    التكرار إلى مصدر له، ويفقد المستخدم ما كان قد بدأه (in_progress).
    """
    keep = STAGE_TASK_PREFIX.get(rn.status)
    rows = db.scalars(select(models.Task).where(
        models.Task.related_entity_type == "renewal",
        models.Task.related_entity_id == rn.id,
        models.Task.status.in_(("open", "in_progress")),
    )).all()
    closed = 0
    for task in rows:
        key = task.dedup_key or ""
        if keep and key.startswith(keep):
            continue                       # مهمة المرحلة الحالية: تبقى
        task.status = "dismissed"
        task.completed_at = datetime.utcnow()
        closed += 1
    return closed


#: RNW-D4 — من يملك الفعل في كل مرحلة. تُقرأ في رسالة الرفض فيعرف
#: القارئ إلى أين يذهب بدل أن يقف أمام «الحالة لا تسمح».
STAGE_ACTOR = {
    R.NEW: "الموظف أو المندوب",
    R.PENDING_MANAGER: "مدير الشركة",
    R.PENDING_HR: "شؤون الموظفين",
    R.WITH_DELEGATE: "المندوب",
    R.AWAITING_CONTRACTS: "المندوب",
    R.AWAITING_SIGNATURE: "الموظف صاحب الطلب",
    R.CONTRACTS_SIGNED: "المندوب",
    R.RENEWING: "المندوب",
    R.AWAITING_CIVIL_CARD: "الموظف صاحب الطلب",
    R.PENDING_HR_VERIFY: "شؤون الموظفين",
    R.COMPLETED: "—",
    R.REJECTED: "—",
}


def _stage_conflict(rn, action: str, needed_status=None) -> HTTPException:
    """رفض 409 يقول أربعة أشياء بدل واحد.

    **العطل**: «الحالة لا تسمح بذلك» تخبر المستخدم أنه أخطأ ولا تخبره
    بماذا. فيعيد المحاولة، أو يظنّ النظام معطًلا، أو يتصل بمن لا يملك
    الفعل. ونصف قيمة الرفض في أن يقول إلى أين يذهب.

    فالرسالة تحمل: المرحلة الحالية · لماذا رُفض · المرحلة المطلوبة ·
    ومَن يملكها.
    """
    def label(code):
        return R.STATUS_LABELS.get(code, {}).get("ar", code)

    parts = [f"المرحلة الحالية: «{label(rn.status)}»",
             f"ولا تسمح بـ{action}"]
    if needed_status:
        parts.append(f"المطلوب أن تكون «{label(needed_status)}»")
        who = STAGE_ACTOR.get(needed_status)
        if who and who != "—":
            parts.append(f"ويقوم بها: {who}")
    return HTTPException(status_code=409, detail=" — ".join(parts))


def _notify_stage(db, rn):
    """إشعار المسؤول عن المرحلة الحالية.

    ويغلق ما بقي من المراحل السابقة قبل ذلك — التنبيه على مرحلة جديدة
    بلا إغلاق ما سبقها يترك المعاملة الواحدة بأربع مهام مفتوحة.
    """
    _close_superseded_stage_tasks(db, rn)
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
    elif rn.status == R.PENDING_HR_VERIFY:
        # **بوّابٌة تنتظر فاعًلا لا يعلم أنها تنتظره.**
        #
        # هذه آخُر بوّابة قبل الإغلاق: الشؤون تطابق رقم الإقامة الجديد
        # وتاريخه والرسوم. وكلا الانتقالين إليها **ينادي**
        # ``_notify_stage`` — ولم يكن لها فرٌع هنا، فيقع النداء ولا يُرسَل
        # شيء. والنظاُم يعرف الفاعل: ``STAGE_ACTOR`` يقول «شؤون
        # الموظفين». فتبقى المعاملة ساكنًة حتى يمرّ عليها أحٌد بالمصادفة.
        for u in users_by_role(db, rn.company_id, ["hr"]):
            notify_from_template(
                db, code="NTF-033", assignee_user_id=u.id, company_id=rn.company_id,
                context={"request_type": "تحقّق بيانات تجديد الإقامة",
                         "employee_name": name},
                related_entity_type="renewal", related_entity_id=rn.id,
                dedup_key=f"renewal_verify:{rn.id}:u{u.id}")
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
    rows = db.scalars(q).all()
    # ونطاقُ الفرع في القائمة كما في فتح المعاملة الواحدة.
    rows = [rn for rn in rows if rn.employee_id == user.employee_id
            or _renewal_branch_allowed(db, user, rn.employee_id)]
    return [_serialize(db, rn) for rn in rows]


@router.get("/{rid}")
def get_renewal(rid: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    rn = _get_renewal(db, user, rid)
    perms = get_user_perms(user, db)
    if not _is_pro(user, perms) and not any(has_permission(user.role, perms, x) for x in permissions.APPROVAL_PERMS) \
            and user.employee_id != rn.employee_id and user.role not in ("super_admin", "company_owner"):
        raise HTTPException(status_code=404, detail="المعاملة غير موجودة")
    return _serialize(db, rn)


@router.get("/{rid}/document/{doc_type}")
def download_renewal_document(rid: int, doc_type: str, request: Request,
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
    # M18 — **كلُّ تنزيلٍ يُدقَّق**: العقد الحكومي والبطاقة المدنية وإذن العمل أوراقٌ حسّاسة، وكان
    # تنزيلُها بلا أثر بينما تنزيل مستند الموظف والأرشيف يُسجَّل — فمن نزّلها لا يُعرَف.
    audit(db, user, "download_renewal_document", "renewal", rn.id,
          detail=f"{doc_type} v{doc.version} (doc#{doc.id})", request=request,
          company_id=rn.company_id, correlation_id=f"renewal:{rn.id}")
    db.commit()
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
        raise _stage_conflict(rn, "اتخاذ قرار اعتماد")
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
        raise _stage_conflict(rn, "بدء إجراءات التجديد", R.CONTRACTS_SIGNED)
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
            raise _stage_conflict(rn, "رفع العقود", R.AWAITING_CONTRACTS)
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
            raise _stage_conflict(rn, "رفع العقد الموقّع", R.AWAITING_SIGNATURE)
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
            raise _stage_conflict(rn, "رفع إذن العمل", R.RENEWING)
        await _save_doc(db, user, request, "employee", emp.id, rn.company_id,
                        R.DOC_WORK_PERMIT, "إذن العمل الجديد", file)
        _ocr_proposal(db, "employee", emp.id, doc_kind, renewal_id=rn.id)
        rn.status = R.AWAITING_CIVIL_CARD
        _notify_stage(db, rn)

    # الموظف يرفع البطاقة المدنية — ينتقل لتحقق HR (R4 §7)
    elif doc_kind == R.DOC_CIVIL_CARD:
        if not (is_owner_emp or is_pro):
            raise HTTPException(status_code=403, detail="خاص بالموظف صاحب الطلب")
        if rn.status != R.AWAITING_CIVIL_CARD:
            raise _stage_conflict(rn, "رفع البطاقة المدنية", R.AWAITING_CIVIL_CARD)
        await _save_doc(db, user, request, "employee", emp.id, rn.company_id,
                        R.DOC_CIVIL_CARD, "البطاقة المدنية الجديدة", file)
        # R4-A — بدل التنقّل المباشر لـCOMPLETED، نمرّ عبر PENDING_HR_VERIFY
        _ocr_proposal(db, "employee", emp.id, doc_kind, renewal_id=rn.id)
        # RNW-D1 — الانتقال مشروط ببيانات الحكومة. المستند يُحفَظ في الحالتين:
        # الموظف رفع ما عليه، ولا يُعاقَب بضياع رفعه لأن المندوب لم يُدخل
        # بياناته بعد. تبقى المعاملة في مرحلتها حتى يُكملها المندوب.
        if _ready_for_hr_verify(db, rn):
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


#: RNW-D1 — بيانات المعاملة الحكومية التي بدونها لا معنى لتحقّق HR.
#: يُدخلها المندوب عبر ``finalize``، وهي شرط دخول ``pending_hr_verify``.
GOV_DATA_FIELDS = {
    "new_expiry_date": "تاريخ الانتهاء الجديد",
    "new_permit_number": "رقم الإقامة الجديد",
    "gov_reference_no": "الرقم المرجعي للمعاملة الحكومية",
}


def _gov_data_missing(rn) -> list[str]:
    """ما ينقص من بيانات الحكومة، مسمًّى.

    **العطل الذي أنتج هذه الدالة**: كان رفع البطاقة المدنية ينقل المعاملة
    إلى ``pending_hr_verify`` بلا فحص. فإن لم يكن المندوب أدخل بيانات
    الحكومة بعد، وقعت المعاملة في حالة لا مخرج منها: ``finalize`` يردّ
    409 لأن المرحلة لا تسمح بالإدخال، وتحقّق HR يرفض الإغلاق لأن
    البيانات ناقصة. مقفولة من الناحيتين.
    """
    return [label for key, label in GOV_DATA_FIELDS.items()
            if not getattr(rn, key, None)]


def _civil_card_uploaded(db, rn) -> bool:
    return _has(db, "employee", rn.employee_id, R.DOC_CIVIL_CARD)


def _ready_for_hr_verify(db, rn) -> bool:
    """شرطا الدخول إلى تحقّق HR: البطاقة مرفوعة **و**البيانات مكتملة.

    ويُقيَّمان عند كلٍّ من المدخلين — رفع البطاقة وإدخال البيانات — فأيّهما
    اكتمل أخيًرا هو الذي ينقل المعاملة. لو فُحص عند مدخل واحد لانتقلت
    القفلة موضعها ولم تُغلق: من يرفع البطاقة أوًلا يُمنع، ثم يُدخل المندوب
    البيانات ولا شيء ينقل المعاملة بعدها.
    """
    return _civil_card_uploaded(db, rn) and not _gov_data_missing(rn)


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


def _extend_work_permit(db, rn) -> None:
    """قرار المالك (2026-09-25): إذن العمل يتبع تاريخ الإقامة الجديد.

    المندوب يرفع «إذن العمل الجديد» ضمن التجديد نفسه، لكنه يُحفظ مستندًا بلا تاريخ،
    فيبقى تصريحُ ``work_permit`` القديم بتاريخه الأول وتستمرّ تنبيهاته. فيُمدَّد إلى تاريخ
    الإقامة المعتمَد، وتُغلق بلاغاتُ انتهائه. ولا يُنشأ تصريحٌ لمن لا تصريح له.
    """
    wp = db.scalar(select(models.Permit).where(
        models.Permit.employee_id == rn.employee_id, models.Permit.company_id == rn.company_id,
        models.Permit.kind == "work_permit", models.Permit.status == "active",
    ).order_by(models.Permit.expiry_date.desc()))
    if not wp or (wp.expiry_date and wp.expiry_date >= rn.new_expiry_date):
        return
    wp.expiry_date = rn.new_expiry_date
    for task in db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "permit",
            models.Task.related_entity_id == wp.id,
            models.Task.status.in_(("open", "in_progress")))).all():
        task.status = "done"
        task.completed_at = datetime.utcnow()


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
    # وبلاغاتُ انتهاء **الإقامة القديمة** نفسها: تبقى مفتوحةً بعد التجديد، إذ يقيس التنظيف
    # اليوميُّ على تاريخ انتهاء التصريح القديم (وهو قريبٌ لم يتغيّر) فلا يعدّها منتهية الصلاحية.
    # كما يفعل إلغاءُ الإقامة تمامًا: الحاجةُ التي وُلد لها البلاغ قُضيت.
    superseded = db.scalars(select(models.Task).where(
        models.Task.related_entity_type == "permit",
        models.Task.related_entity_id == rn.permit_id,
        models.Task.status.in_(("open", "in_progress")),
    )).all() if rn.permit_id else []
    for task in superseded:
        task.status = "done"
        task.completed_at = datetime.utcnow()
    return len(open_tasks) + len(superseded)


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
    "renewal_ocr_read": "قرأ النظام المستند",
    # M18 — تنزيل مستند المعاملة يُدقَّق، ويظهر في قصتها: من نزّل العقد أو البطاقة ومتى.
    "download_renewal_document": "نُزِّل مستند من المعاملة",
}

#: P4-22 — «رُفع مستند» تخفي أهمّ ما في القصة.
#:
#: الرفع حدث واحد في التدقيق (``renewal_upload``) وستّة مستندات مختلفة
#: تمرّ به: العقد المولَّد، ونسخة الموظف الموقّعة، والنسخة النهائية،
#: وإذن العمل، والبطاقة المدنية. ومن يقرأ الخطّ بعد شهور يرى ست مرّات
#: «رُفع مستند» ولا يعرف أيّها كان.
#:
#: والكود مسجَّل في ``detail`` منذ البداية — الناقص أن يُقرأ.
UPLOAD_LABELS = {
    R.DOC_CONTRACT_GOV: "رُفع العقد الحكومي المولَّد",
    R.DOC_CONTRACT_INTERNAL: "رُفع عقد الشركة (اختياري)",
    R.DOC_SIGNED_GOV: "رفع الموظف العقد موقًَّعا",
    R.DOC_SIGNED_INTERNAL: "رُفع عقد الشركة موقًَّعا",
    R.DOC_CONTRACT_FINAL: "رُفع العقد بتوقيع الطرفين",
    R.DOC_WORK_PERMIT: "رُفع إذن العمل الجديد",
    R.DOC_CIVIL_CARD: "رُفعت البطاقة المدنية الجديدة",
}


def _timeline_label(action: str, detail: str | None) -> str:
    """تسمية الحدث — وتفصيلها حين يحمله السجلّ."""
    if action == "renewal_upload" and detail:
        return UPLOAD_LABELS.get(detail.strip(), TIMELINE_LABELS[action])
    return TIMELINE_LABELS.get(action, action)


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
            "label": _timeline_label(row.action, row.detail),
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
    # RNW-D2 — الإنقاذ: pending_hr_verify ضمن المسموح.
    #
    # المنع (RNW-D1) يحمي ما هو آتٍ ولا يحرّر ما هو عالق: معاملات وصلت
    # المرحلة قبل الإصلاح بلا بيانات حكومة، فلا finalize يقبلها ولا HR
    # يغلقها. والقرار المتَّخذ: تُستكمل في مكانها بدل إرجاعها — HR يرى
    # الناقص، والمندوب يُدخله، والمعاملة تُغلق بلا رحلة ذهاب وعودة تظهر
    # للموظف كأنها تراجعت.
    #
    # والتعديل هنا آمن لأن المرحلة اسمها «بانتظار تحقّق HR»: لم يُصادَق
    # على شيء بعد، وكل إدخال يُسجَّل في التدقيق بقيمته قبل وبعد.
    if rn.status not in (R.RENEWING, R.CONTRACTS_SIGNED, R.WITH_DELEGATE,
                         R.AWAITING_CIVIL_CARD, R.PENDING_HR_VERIFY):
        raise HTTPException(
            status_code=409,
            detail=(f"الحالة الحالية ({R.STATUS_LABELS.get(rn.status, {}).get('ar', rn.status)}) "
                    "لا تسمح بإدخال بيانات المعاملة الحكومية — "
                    "تُدخَل أثناء التجديد أو بانتظار البطاقة أو بانتظار تحقّق HR"))
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
    # RNW-D1 — الطرف الثاني للبوّابة: لو كانت البطاقة مرفوعة من قبل فهذه
    # الخطوة هي التي تُكمل الشرطين، فتنقل هي المعاملة. وبدون هذا الفرع
    # ينتقل العطل ولا يزول: البطاقة تُرفض النقل لنقص البيانات، ثم تُدخَل
    # البيانات ولا يبقى حدث ينقل المعاملة — ساكنة بلا مخرج مرة أخرى.
    if _ready_for_hr_verify(db, rn):
        rn.status = R.PENDING_HR_VERIFY
    elif rn.status != R.AWAITING_CIVIL_CARD:
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
        raise _stage_conflict(rn, "تحقّق شؤون الموظفين", R.PENDING_HR_VERIFY)
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
    _extend_work_permit(db, rn)

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
# عقد الشركة يُوقَّع مرة واحدة عند التعيين. المصدر ملف الهيئة الرسمي نفسه
# (``gov_contract_form``) — صفّ DocumentTemplate بكود "GOV-CONTRACT-RENEWAL"
# ليس شرًطا (GC-01)، يبقى مرجًعا اختياريًا لرقم الإصدار فقط إن وُجد.
# البيانات تُملأ تلقائيًا من الموظف/الشركة، وحقلٌ ناقص يُطبع فارًغا
# (2026-09-22) بدل أن يوقف التوليد.

@router.post("/{rid}/gov-contract/generate")
def generate_gov_contract(rid: int, request: Request,
                          format: str = "html",
                          representative_id: int | None = None,
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

    # V-B — لا إعادة توليد بعد أن يوقّع الموظف.
    #
    # إعادة التوليد **قبل** التوقيع عمل مشروع: تُصحَّح بيانات الموظف
    # ويُعاد العقد. ومنعها يدفع المندوب إلى فتح معاملة ثانية.
    #
    # وبعد التوقيع تصير ضرًرا: للعقد ثلاث نسخ لكلٍّ معنى قانوني —
    # المولَّدة، والموقّعة من الموظف، والموقّعة من الطرفين. وتوليد نسخة
    # جديدة يجعل «السارية» غير ما وقّعه الموظف بيده، فيُقدَّم إلى الجهة
    # عقد لم يوقّعه أحد، أو يُحتجّ بتوقيع على نصّ غيره.
    #
    # (سجّلت المراجعة خمس توليدات لعقد واحد. والعدد ليس العطل — الحدّ هو.)
    if _has(db, "renewal", rn.id, R.DOC_SIGNED_GOV):
        raise HTTPException(
            status_code=409,
            detail=("وقّع الموظف نسخته من هذا العقد، فلا يُعاد توليده. "
                    "لتغيير بياناته أرجِع المعاملة إلى مرحلة رفع العقود."))

    emp = db.get(models.Employee, rn.employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")

    # ابحث عن قالب العقد الحكومي (يُنشأ يدويًا من إدارة القوالب مرة واحدة)
    tpl = db.scalar(select(models.DocumentTemplate).where(
        models.DocumentTemplate.code == "GOV-CONTRACT-RENEWAL",
        models.DocumentTemplate.is_active == True,  # noqa: E712
    ))
    # GC-01 — القالب لم يعد شرًطا للتوليد: مصدر العقد ملف الهيئة الرسمي
    # وبصمته، لا صفّ HTML في القاعدة. وكان اشتراطه يوقف التوليد برسالة
    # تطلب لصق «نص وزارة الداخلية» في قالب — وهي تعليمات بطلت، وتدعو من
    # يقرأها إلى بناء عقد رسمي بيده.
    #
    # ويبقى الصفّ إن وُجد مرجًعا لرقم الإصدار وحده، فيُحفظ ترقيم المستندات
    # الصادرة كما هو.

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
    ctx.update(_gov_contract_context(db, emp, company, rn, representative_id=representative_id))
    # RNW-06 (عُدّلت 2026-09-22، بطلب صريح): لا رفض بعد اليوم لحقل ناقص —
    # العقد يُطبع بالخانة فارغة ويملؤها الموظف يدويًا، واستكمال البيانات
    # في النظام صار مهمة لاحقة (ترقية) لا شرط توليد. ``missing`` يبقى
    # معلوماتيًا فقط: يُسجَّل في التدقيق ليُعرف لاحقًا ما تبقّى.
    missing = [label for key, label in R.GOV_CONTRACT_REQUIRED_FIELDS.items()
               if not str(ctx.get(key) or "").strip()]

    reference_no = _generate_reference_no(db, "GOV-REN", rn.company_id,
                                          (tpl.version if tpl else 1) or 1)
    ctx["ref_no"] = reference_no

    # GC-01/GC-02 — العقد يُولَّد من نموذج الهيئة الرسمي نفسه، لا من قالب
    # HTML يقلّده. القالب في القاعدة يبقى مرجًعا للنسخة ورقم الإصدار،
    # والمحتوى يأتي من ملف الوورد ببصمته الأصلية.
    content_bytes, ext, mime, docx_missing, snap = gov_contract_form.generate(ctx)
    missing = missing or docx_missing
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
        template_version=(tpl.version if tpl else 1) or 1, checksum_sha256=checksum,
        generated_at=datetime.utcnow(), generated_by=user.id,
        # GC-10 — لقطة القيم وقت الإصدار. الملف ثابت ببصمته، واللقطة تجعل
        # «بأي راتب صدر هذا العقد؟» سؤاًلا يُجاب من السجلّ لا من فتح الملف،
        # وتكشف الفارق إن عُدِّل ملف الموظف بعد الإصدار.
        extracted_data_json=snap,
    )
    db.add(doc)
    db.flush()
    missing_note = f" — حقول فارغة: {'، '.join(missing)}" if missing else ""
    audit(db, user, "generate_gov_contract", "residency_renewal", rn.id,
          detail=f"gov contract → {reference_no} ({ext}){missing_note}",
          request=request, company_id=rn.company_id)
    db.commit()

    # GC-01 — لم يعد هناك «html» يُعاد للواجهة: العقد ملف بتخطيط الهيئة
    # (PDF، أو docx إن غاب LibreOffice عن البيئة) يُنزَّل لا يُعرض في صفحة.
    # وإعادة HTML مقلّد كانت هي المشكلة الأصلية.
    if (format or "").lower() in ("pdf", "file", "download"):
        return file_response(fpath, filename=f"{safe_ref}.{ext}", media_type=mime)
    note = "اطبع العقد → الموظف يوقّعه → ارفع النسخة الموقّعة عبر upload بـdoc_type=renewal_signed_gov"
    if missing:
        note += f" — تنبيه: العقد طُبع بخانات فارغة ({'، '.join(missing)}) لنقص في ملف الموظف/الشركة، أكملها لاحقًا."
    return {
        "ok": True,
        "format": ext,
        "download_url": f"/api/renewals/{rn.id}/gov-contract?format=file",
        "document_id": doc.id, "reference_no": reference_no,
        "checksum_sha256": checksum,
        "missing_fields": missing,
        "note": note,
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
    from ..expiry_windows import WINDOW
    soon = today + WINDOW
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
        # ونطاقُ الفرع هنا كما في المعاملات نفسها: رقُم الإقامة وتاريُخها لا
        # يُعرضان لمسؤول فرٍع آخر.
        if p.employee_id != user.employee_id and not _renewal_branch_allowed(
                db, user, p.employee_id):
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
