# -*- coding: utf-8 -*-
"""محرّك الطلبات والموافقات: تقديم، اعتماد/رفض، إلغاء المدير، مواعيد، رفع مستندات."""
import os
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, workflow
from ..config import settings
from ..database import get_db
from ..deps import (assert_same_company, audit, get_current_user, require_any_perm,
                    require_perm, scope_company_id)
from ..safe_files import read_limited, unique_path

router = APIRouter(prefix="/requests", tags=["requests"])

# حقول إلزامية لكل نوع طلب له نموذج مخصّص في الواجهة (Requests.tsx) — تمنع حفظ طلب فارغ
# `{}` يدخل مسار الاعتماد الفعلي (QA-P0-WF-01). الأنواع غير المدرجة هنا (نموذج عام، أو
# طلبات تُنشأ برمجيًا مثل REQEOS/REQCLR بحمولة خاصة بها) تُفحص فقط بألا تكون فارغة تمامًا.
REQUIRED_PAYLOAD_FIELDS: dict[str, list[str]] = {
    "leave": ["start_date", "end_date"],
    "salary_certificate": ["addressed_to", "purpose"],
    "exit_permission": ["date", "reason"],
    "advance": ["amount"],
    "loan": ["amount", "months"],
    "REQADV": ["subtype", "amount"],
    "REQBANK": ["bank_name", "iban"],
    "REQEXP": ["amount", "description"],
    "REQWARN": ["warning_ref", "response"],
}


def _missing_required_fields(code: str, payload: dict) -> list[str]:
    def _blank(v):
        return v is None or (isinstance(v, str) and not v.strip())

    required = REQUIRED_PAYLOAD_FIELDS.get(code)
    if required is not None:
        return [k for k in required if _blank(payload.get(k))]
    # لا نموذج مخصّص لهذا النوع: يكفي ألا تكون الحمولة فارغة تمامًا
    if not payload or all(_blank(v) for v in payload.values()):
        return ["details"]
    return []


# ----------------------------- أنواع الطلبات -----------------------------

@router.get("/status-map")
def status_map(user: models.User = Depends(get_current_user)):
    """ربط الحالات الداخلية بحالات V1.3/V1.4/V1.5 الرسمية (FIX-009 + V1.5)."""
    return workflow.STATUS_MAP


@router.get("/status-model")
def status_model(user: models.User = Depends(get_current_user)):
    """V1.5 Phase 2 — الـ canonical status taxonomy الكامل:
    - request_lifecycle: DRAFT/SUBMITTED/IN_REVIEW/NEEDS_INFO/APPROVED/IN_EXECUTION/COMPLETED
    - document_lifecycle: NOT_REQUIRED/QUEUED/GENERATING/GENERATED/SIGNED/DELIVERED/ARCHIVED
    - step_types: DECISION/VALIDATION/EXECUTION/ACKNOWLEDGEMENT/NOTIFICATION/AUTOMATION
    - internal_to_v15: خريطة الحالات الداخلية القديمة → V1.5 canonical
    """
    from .. import v15_status
    return v15_status.as_dict()


@router.get("/registry")
def registry(user: models.User = Depends(get_current_user)):
    """V1.5 Migration Registry: canonical workflows/documents + legacy aliases.
    يمكن للفرونت-إند استخدامه ليعرض الاسم الجديد الرسمي (WF-XXX) بجانب الكود القديم في
    الطلبات المحفوظة قبل الترحيل."""
    from .. import v15_registry
    return {
        "canonical_workflows": v15_registry.CANONICAL_WORKFLOWS,
        "layouts": v15_registry.LAYOUTS,
        "reports": v15_registry.REPORTS,
        "system_records": v15_registry.SYSTEM_RECORDS,
        "legacy_request_aliases": v15_registry.LEGACY_REQUEST_ALIASES,
        "legacy_template_aliases": v15_registry.LEGACY_PRN_ALIASES,
        "summary": v15_registry.summary(),
    }


@router.get("/types")
def list_request_types(category: str | None = None,
                       user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    cid = user.company_id
    q = select(models.RequestType).where(models.RequestType.is_active == True)  # noqa: E712
    rows = db.scalars(q).all()

    # V1.5 Phase 5 dual-read: كل نوع طلب يحمل الكود القديم والـ canonical معًا. الفلاجز
    # يقرر أيّهما "الأساسي" (primary):
    # - v15_canonical_display=on: الكود canonical أساسي، والقديم legacy_code
    # - افتراضيًا (default): الكود القديم أساسي، والـ canonical معلومة إضافية
    # - v15_legacy_catalog_hidden=on: يخفي الأنواع التي canonical لها = None (غير مصنّفة)
    from .. import feature_flags as ff
    from .. import v15_registry
    canonical_display = ff.is_enabled(db, cid, ff.V15_CANONICAL_DISPLAY)
    hide_legacy = ff.is_enabled(db, cid, ff.V15_LEGACY_CATALOG_HIDDEN)

    seen, out = set(), []
    for rt in sorted(rows, key=lambda r: (r.code, r.company_id is None)):
        if rt.company_id not in (None, cid):
            continue
        if rt.code in seen:
            continue
        # الموظف (خدمة ذاتية) يرى فقط الأنواع الموسومة له — لا نماذج ADM* الداخلية ولا ما
        # يبدأ من HR/الإدارة بشأنه (P0-06: تنظيم كتالوج الطلبات حسب الدور)
        if user.role == "employee" and not rt.visible_to_employee:
            continue
        seen.add(rt.code)
        canonical_info = v15_registry.resolve_request(rt.code)
        canonical_code = canonical_info.get("canonical")
        if hide_legacy and not canonical_code:
            continue
        entry: dict = {
            "code": rt.code, "name": rt.name, "category": rt.category,
            "chain": rt.approval_chain_json,
            "produces_document": rt.produces_document,
            "canonical_code": canonical_code,
            "canonical_subtype": canonical_info.get("subtype"),
        }
        if canonical_display and canonical_code:
            entry["primary_code"] = canonical_code
            entry["legacy_code"] = rt.code
        else:
            entry["primary_code"] = rt.code
            entry["legacy_code"] = None
        out.append(entry)
    if category:
        out = [x for x in out if x["category"] == category]
    return out


@router.post("/types", status_code=201)
def create_request_type(data: schemas.RequestTypeIn,
                        user: models.User = Depends(require_perm("manage_request_types")),
                        db: Session = Depends(get_db)):
    cid = None if user.role == "super_admin" else user.company_id
    rt = models.RequestType(company_id=cid, **data.model_dump())
    db.add(rt)
    db.commit()
    db.refresh(rt)
    return {"ok": True, "id": rt.id}


# ----------------------------- تقديم وعرض -----------------------------

@router.post("", status_code=201)
def submit_request(data: schemas.RequestIn, request: Request,
                   user: models.User = Depends(require_perm("submit_request")),
                   db: Session = Depends(get_db)):
    # تحديد الموظف: العامل يقدّم لنفسه، وذو الصلاحية قد يقدّم لموظف
    emp_id = data.employee_id or user.employee_id
    if not emp_id:
        raise HTTPException(status_code=400, detail="يجب تحديد الموظف")
    emp = db.get(models.Employee, emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    assert_same_company(user, emp.company_id, db=db)

    rt = workflow.get_request_type(db, emp.company_id, data.request_type_code)
    if not rt:
        raise HTTPException(status_code=404, detail="نوع الطلب غير معرّف")

    # منع تقديم طلب فارغ يدخل مسار الاعتماد الفعلي (QA-P0-WF-01)
    missing = _missing_required_fields(data.request_type_code, data.payload_json or {})
    if missing:
        labels = [workflow.PAYLOAD_KEY_LABELS_AR.get(k, workflow._humanize_key(k)) for k in missing]
        raise HTTPException(status_code=400, detail=f"الحقول التالية مطلوبة: {'، '.join(labels)}")

    # تحقّق منطق التواريخ لطلبات الإجازة
    if data.request_type_code == "leave":
        p = data.payload_json or {}
        sd, ed = p.get("start_date"), p.get("end_date")
        if sd and ed and str(ed) < str(sd):
            raise HTTPException(status_code=400, detail="تاريخ نهاية الإجازة قبل بدايتها")

    req = workflow.create_request(db, emp, user, rt, data.payload_json)
    audit(db, user, "submit_request", "request", req.id, detail=rt.code, request=request, company_id=emp.company_id)
    db.commit()
    st = workflow.status_info(req.status)
    return {"ok": True, "id": req.id, "status": req.status, "status_label": st["label"],
            "current_stage": req.current_stage}


@router.get("/mine")
def my_requests(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """طلباتي (للعامل) — الطلبات التي قدّمها أو الخاصة بملفه."""
    q = select(models.Request).where(
        (models.Request.requester_user_id == user.id)
        | (models.Request.employee_id == (user.employee_id or -1))
    )
    return [_serialize(db, r) for r in db.scalars(q.order_by(models.Request.created_at.desc())).all()]


@router.get("/inbox")
def approval_inbox(company_id: int | None = None,
                   user: models.User = Depends(
                       require_any_perm("approve_request", "process_delegate_tasks")),
                   db: Session = Depends(get_db)):
    """بانتظار موافقتي — طلبات مرحلتها الحالية موجّهة لهذا المستخدم."""
    cid = scope_company_id(user, company_id)
    q = select(models.Request).where(models.Request.status.in_(
        ["pending", "awaiting_signature", "awaiting_delegate", "ready_for_pickup"]))
    if cid is not None:
        q = q.where(models.Request.company_id == cid)
    out = []
    for req in db.scalars(q.order_by(models.Request.created_at.desc())).all():
        rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
        if not rt:
            continue
        chain = workflow._chain(rt)
        if req.current_stage >= len(chain):
            continue
        stage = chain[req.current_stage]
        if workflow.can_decide(db, req, user, stage, rt=rt):
            out.append(_serialize(db, req))
    return out


@router.get("/{req_id}")
def get_request(req_id: int, user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    req = _get_req(db, user, req_id)
    return _serialize(db, req, full=True)


# ----------------------------- قرارات -----------------------------

@router.post("/{req_id}/decide")
def decide(req_id: int, data: schemas.ApprovalDecisionIn, request: Request,
           user: models.User = Depends(
               require_any_perm("approve_request", "process_delegate_tasks")),
           db: Session = Depends(get_db)):
    req = _get_req(db, user, req_id)
    if req.status not in ("pending",):
        raise HTTPException(status_code=409, detail="لا يمكن اتخاذ قرار في هذه الحالة")
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    chain = workflow._chain(rt)
    stage = chain[req.current_stage]
    if not workflow.can_decide(db, req, user, stage, rt=rt):
        raise HTTPException(status_code=403, detail="لست المعتمِد لهذه المرحلة")
    if data.decision not in ("approved", "rejected", "returned"):
        raise HTTPException(status_code=400, detail="قرار غير صالح")
    if data.decision == "returned":
        # إرجاع للتصحيح متاح فقط بالمرحلتين الأولى والثانية، ويلزم توضيح السبب (QA-P2-WF-03)
        if req.current_stage >= 2:
            raise HTTPException(status_code=400, detail="الإرجاع للتصحيح متاح فقط في المرحلتين الأولى والثانية")
        if not (data.note and data.note.strip()):
            raise HTTPException(status_code=400, detail="يجب توضيح سبب الإرجاع في الملاحظة")
    if stage.get("kind") == "delegate_exit" and data.decision == "approved":
        raise HTTPException(
            status_code=400,
            detail="هذه المرحلة تكتمل برفع إذن المغادرة (documents) لا بالاعتماد المباشر",
        )
    req = workflow.decide(db, req, user, data.decision, data.note, rt)
    audit(db, user, f"request_{data.decision}", "request", req.id, request=request, company_id=req.company_id)
    st = workflow.status_info(req.status)
    return {"ok": True, "status": req.status, "status_label": st["label"], "current_stage": req.current_stage}


@router.post("/{req_id}/cancel")
def cancel(req_id: int, request: Request, note: str | None = None,
           user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = _get_req(db, user, req_id)
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    try:
        req = workflow.cancel(db, req, user, note, rt)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    audit(db, user, "request_cancel", "request", req.id, request=request, company_id=req.company_id)
    return {"ok": True, "status": req.status}


@router.post("/{req_id}/resubmit")
def resubmit_request(req_id: int, request: Request, data: dict | None = None,
                     user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """إعادة تقديم طلب بعد إرجاعه للتصحيح (V1.4 NEEDS_INFO): يقبل حمولة معدّلة اختيارية،
    ويعيد الطلب لمرحلة الاعتماد الأولى دون إنشاء طلب جديد."""
    req = _get_req(db, user, req_id)
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    try:
        req = workflow.resubmit(db, req, user, (data or {}).get("payload_json"), rt)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit(db, user, "request_resubmit", "request", req.id, request=request, company_id=req.company_id)
    return {"ok": True, "status": req.status, "current_stage": req.current_stage}


# ----------------------------- مواعيد ومستندات -----------------------------

@router.post("/{req_id}/appointment")
def set_appointment(req_id: int, data: schemas.AppointmentIn, request: Request,
                    user: models.User = Depends(require_perm("approve_request")),
                    db: Session = Depends(get_db)):
    """يحدد HR موعد مراجعة العامل للتوقيع (الحالة awaiting_signature)."""
    req = _get_req(db, user, req_id)
    appt = models.Appointment(company_id=req.company_id, request_id=req.id,
                              employee_id=req.employee_id, scheduled_at=data.scheduled_at,
                              location=data.location, created_by=user.id)
    db.add(appt)
    from ..notifications import notify_employee_self
    notify_employee_self(
        db, req.employee_id, type="appointment",
        title="موعد مراجعة للتوقيع",
        detail=(f"برجاء مراجعة شؤون الموظفين يوم {data.scheduled_at:%Y-%m-%d} الساعة "
                f"{data.scheduled_at:%H:%M} في {data.location or 'مقر الشركة'} لإتمام طلبك."),
        related_entity_type="request", related_entity_id=req.id,
        dedup_key=f"appt:{appt.request_id}:{int(data.scheduled_at.timestamp())}",
    )
    audit(db, user, "set_appointment", "request", req.id, request=request, company_id=req.company_id)
    db.commit()
    return {"ok": True}


@router.post("/{req_id}/documents")
async def upload_request_document(req_id: int, request: Request, kind: str = Form(...),
                                  file: UploadFile = File(...),
                                  user: models.User = Depends(get_current_user),
                                  db: Session = Depends(get_db)):
    """رفع مستند الطلب (signed_scan من HR / exit_permit من المندوب) ويقدّم سير العمل."""
    req = _get_req(db, user, req_id)
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)

    if kind not in ("signed_scan", "exit_permit", "generated_pdf", "attachment"):
        raise HTTPException(status_code=400, detail="نوع مستند غير صالح")
    folder = os.path.join(settings.upload_dir, "requests")
    fpath = unique_path(folder, file.filename, prefix=f"req{req.id}_{kind}_")
    with open(fpath, "wb") as f:
        f.write(await read_limited(file))
    existing = db.scalars(select(models.RequestDocument).where(
        models.RequestDocument.request_id == req.id, models.RequestDocument.kind == kind)).all()
    db.add(models.RequestDocument(request_id=req.id, kind=kind, file_path=fpath,
                                  version=len(existing) + 1, uploaded_by=user.id))
    db.flush()

    # تقديم سير العمل حسب نوع المستند
    if kind == "signed_scan" and req.status == "awaiting_signature":
        workflow.upload_signed_scan_done(db, req, rt)
    elif kind == "exit_permit" and req.status == "awaiting_delegate":
        if not (user.role == "delegate" or user.role in workflow.CANCEL_ROLES):
            raise HTTPException(status_code=403, detail="رفع إذن المغادرة من صلاحية المندوب")
        workflow.upload_exit_permit_done(db, req, rt)
    else:
        db.commit()

    audit(db, user, "upload_request_doc", "request", req.id, detail=kind, request=request, company_id=req.company_id)
    db.commit()
    return {"ok": True, "status": req.status}


@router.post("/{req_id}/received")
def mark_received(req_id: int, user: models.User = Depends(require_perm("approve_request")),
                  db: Session = Depends(get_db)):
    """تسجيل استلام العامل للمستند (يُغلق طلب شهادة الراتب)."""
    req = _get_req(db, user, req_id)
    if req.status != "ready_for_pickup":
        raise HTTPException(status_code=409, detail="الطلب ليس جاهزًا للاستلام")
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    workflow.mark_pickup_received(db, req, rt)
    return {"ok": True, "status": req.status}


@router.get("/{req_id}/document/{kind}")
def download_request_document(req_id: int, kind: str,
                              user: models.User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    req = _get_req(db, user, req_id)
    doc = db.scalar(select(models.RequestDocument).where(
        models.RequestDocument.request_id == req.id, models.RequestDocument.kind == kind
    ).order_by(models.RequestDocument.version.desc()))
    if not doc or not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    if doc.file_path.endswith(".pdf"):
        media = "application/pdf"
    elif doc.file_path.endswith(".html"):
        media = "text/html"
    else:
        media = "application/octet-stream"
    return FileResponse(doc.file_path, media_type=media,
                        filename=os.path.basename(doc.file_path))


# ----------------------- دورة حياة الطباعة/الأرشفة (FIX-008) -----------------------

def _latest_doc(db: Session, req_id: int, kind: str) -> models.RequestDocument:
    doc = db.scalar(select(models.RequestDocument).where(
        models.RequestDocument.request_id == req_id, models.RequestDocument.kind == kind
    ).order_by(models.RequestDocument.version.desc()))
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    return doc


@router.post("/{req_id}/document/{kind}/mark-printed")
def mark_document_printed(req_id: int, kind: str, request: Request,
                          user: models.User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """READY_TO_PRINT → PRINTED: تسجّل من طبع المستند الفعلي ومتى."""
    req = _get_req(db, user, req_id)
    doc = _latest_doc(db, req.id, kind)
    if doc.print_status not in ("ready_to_print", "printed"):
        raise HTTPException(status_code=409, detail="لا يمكن تسجيل الطباعة في هذه الحالة")
    doc.print_status = "printed"
    doc.printed_at = datetime.now()
    doc.printed_by = user.id
    audit(db, user, "print_document", "request", req.id, detail=kind, request=request, company_id=req.company_id)
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    if rt:
        from ..notifications import notify_from_template
        notify_from_template(
            db, code="NTF-044", assignee_user_id=user.id, company_id=req.company_id,
            context={"document_name": rt.name, "actor_name": user.full_name or user.role},
            related_entity_type="request", related_entity_id=req.id,
            dedup_key=f"print_done:{doc.id}",
        )
    db.commit()
    return {"ok": True, "print_status": doc.print_status}


@router.post("/{req_id}/document/{kind}/mark-filed")
def mark_document_filed(req_id: int, kind: str, request: Request,
                        user: models.User = Depends(require_perm("upload_documents")),
                        db: Session = Depends(get_db)):
    """PRINTED → FILED: أرشفة النسخة المعتمدة في ملف الموظف (ورقي/إلكتروني)."""
    req = _get_req(db, user, req_id)
    doc = _latest_doc(db, req.id, kind)
    if doc.print_status != "printed":
        raise HTTPException(status_code=409, detail="يجب تسجيل الطباعة أولًا قبل الأرشفة")
    doc.print_status = "filed"
    doc.filed_at = datetime.now()
    doc.filed_by = user.id
    audit(db, user, "file_document", "request", req.id, detail=kind, request=request, company_id=req.company_id)
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    if rt:
        # أرشفة فعلية في ملف الموظف العام (جدول Document) — لا يبقى الأثر داخل الطلب فقط
        type_code = f"request_{req.request_type_code}"
        prev = db.scalars(select(models.Document).where(
            models.Document.entity_type == "employee", models.Document.entity_id == req.employee_id,
            models.Document.document_type_code == type_code, models.Document.is_current == True,  # noqa: E712
        )).all()
        for d in prev:
            d.is_current = False
        db.add(models.Document(
            company_id=req.company_id, entity_type="employee", entity_id=req.employee_id,
            document_type_code=type_code, title=rt.name, file_path=doc.file_path,
            mime="application/pdf", version=len(prev) + 1, is_current=True, uploaded_by=user.id,
        ))
        from ..notifications import notify_from_template
        notify_from_template(
            db, code="NTF-045", assignee_user_id=user.id, company_id=req.company_id,
            context={"document_name": rt.name},
            related_entity_type="request", related_entity_id=req.id,
            dedup_key=f"file_done:{doc.id}",
        )
    db.commit()
    return {"ok": True, "print_status": doc.print_status}


# ----------------------------- مساعدات -----------------------------

def _get_req(db: Session, user: models.User, req_id: int) -> models.Request:
    req = db.get(models.Request, req_id)
    if not req:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    assert_same_company(user, req.company_id, db=db)
    is_self = req.employee_id == user.employee_id
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)

    # الطلبات السرّية (شكاوى/تظلمات، FIX-014): الاطلاع يقتصر على الإدارة العليا،
    # معتمدي المرحلة الفعليين عبر السلسلة كاملة (مثل الشؤون القانونية)، وصاحب الطلب نفسه —
    # لا تجاوز إداري عام حتى لا يطّلع المسؤول المشتكى به على الشكوى ضده.
    if rt and rt.is_confidential:
        if user.role == "super_admin" or is_self:
            return req
        for stage in workflow._chain(rt):
            if any(u.id == user.id for u in workflow.resolve_stage_approvers(db, req, stage)):
                return req
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    # خدمة ذاتية: من لا يعتمد/يعالج الطلبات يرى طلباته هو فقط (لا طلبات الزملاء)
    from ..permissions import has_permission
    from ..deps import get_user_perms
    perms = get_user_perms(user, db)
    is_handler = (user.role == "super_admin"
                  or has_permission(user.role, perms, "approve_request")
                  or has_permission(user.role, perms, "process_delegate_tasks"))
    if not is_handler and not is_self:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    return req


ROLE_AR = {
    "super_admin": "الإدارة العليا", "company_owner": "صاحب الشركات",
    "company_manager": "المدير العام", "branch_supervisor": "مسؤول الفرع",
    "hr": "شؤون الموظفين", "delegate": "المندوب", "employee": "الموظف",
}


def _serialize(db: Session, req: models.Request, full: bool = False) -> dict:
    emp = db.get(models.Employee, req.employee_id)
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    chain = workflow._chain(rt) if rt else []
    st = workflow.status_info(req.status)
    # V1.5 canonical resolver: يعرض الكود الجديد للطلب بجانب الكود القديم في seed
    from .. import v15_registry
    canonical_info = v15_registry.resolve_request(req.request_type_code)
    data = {
        "id": req.id, "type": req.request_type_code,
        "type_name": rt.name if rt else req.request_type_code,
        "canonical_workflow": canonical_info.get("canonical"),  # V1.5 WF-XXX (قد يكون None)
        "canonical_subtype": canonical_info.get("subtype"),
        "employee_id": req.employee_id, "employee_name": emp.name if emp else None,
        "status": req.status, "status_code": st["code"], "status_label": st["label"],
        "status_v15": st.get("v15"),  # V1.5 canonical (IN_REVIEW/NEEDS_INFO/...)
        "current_stage": req.current_stage,
        "total_stages": len(chain),
        "payload": req.payload_json, "created_at": req.created_at,
    }
    if full:
        approvals = db.scalars(select(models.RequestApproval).where(
            models.RequestApproval.request_id == req.id)
            .order_by(models.RequestApproval.decided_at)).all()
        # كل قرار حسب مرحلته (للعرض: من قرّر، متى، وبأي ملاحظة) بصرف النظر عن نوع القرار
        by_stage = {a.stage_order: a for a in approvals}
        # القرار السلبي لكل مرحلة (رفض أو إرجاع للتصحيح، QA-P2-WF-03) — يحدد لون/نص المرحلة بدقة
        negative = {a.stage_order: a.decision for a in approvals if a.decision in ("rejected", "returned")}
        docs = db.scalars(select(models.RequestDocument).where(
            models.RequestDocument.request_id == req.id)).all()

        def _name(uid):
            u = db.get(models.User, uid) if uid else None
            return (u.full_name or ROLE_AR.get(u.role, u.role)) if u else None

        # حالة كل مرحلة لرسم المسار الهرمي بوضوح
        stages = []
        for i, st in enumerate(chain):
            ap = by_stage.get(i)
            if req.status == "completed":
                state = "done"
            elif req.status == "cancelled":
                state = "done" if i < req.current_stage else ("cancelled" if i == req.current_stage else "skipped")
            elif i in negative:
                state = negative[i]
            elif i < req.current_stage:
                state = "done"
            elif i == req.current_stage:
                state = "current"
            else:
                state = "pending"
            stages.append({
                "order": i, "label": st.get("label"), "role": st.get("role"),
                "role_label": ROLE_AR.get(st.get("role"), st.get("role")),
                "kind": st.get("kind", "approval"), "state": state,
                "approver_name": _name(ap.approver_user_id) if ap else None,
                "decided_at": ap.decided_at if ap else None,
                "note": ap.note if ap else None,
            })

        data["stages"] = stages
        data["chain"] = chain
        data["timeline"] = [
            {"stage": a.stage_order, "label": a.stage_label, "role": a.approver_role,
             "role_label": ROLE_AR.get(a.approver_role, a.approver_role),
             "approver_name": _name(a.approver_user_id),
             "decision": a.decision, "note": a.note, "at": a.decided_at} for a in approvals
        ]
        data["documents"] = [
            {"kind": d.kind, "version": d.version, "created_at": d.created_at,
             "print_status": d.print_status, "printed_at": d.printed_at, "filed_at": d.filed_at,
             # V1.5 Phase 4: canonical OD code + lifecycle status (منفصل عن print_status)
             "od_code": d.od_code,
             "lifecycle_status": d.lifecycle_status}
            for d in docs
        ]
    return data
