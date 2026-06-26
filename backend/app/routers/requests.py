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
from ..deps import assert_same_company, audit, get_current_user, require_perm, scope_company_id
from ..safe_files import read_limited, unique_path

router = APIRouter(prefix="/requests", tags=["requests"])


# ----------------------------- أنواع الطلبات -----------------------------

@router.get("/types")
def list_request_types(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    cid = user.company_id
    q = select(models.RequestType).where(models.RequestType.is_active == True)  # noqa: E712
    rows = db.scalars(q).all()
    seen, out = set(), []
    for rt in sorted(rows, key=lambda r: (r.code, r.company_id is None)):
        if rt.company_id not in (None, cid):
            continue
        if rt.code in seen:
            continue
        seen.add(rt.code)
        out.append({"code": rt.code, "name": rt.name,
                    "chain": rt.approval_chain_json,
                    "produces_document": rt.produces_document})
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
    assert_same_company(user, emp.company_id)

    rt = workflow.get_request_type(db, emp.company_id, data.request_type_code)
    if not rt:
        raise HTTPException(status_code=404, detail="نوع الطلب غير معرّف")

    # تحقّق منطق التواريخ لطلبات الإجازة
    if data.request_type_code == "leave":
        p = data.payload_json or {}
        sd, ed = p.get("start_date"), p.get("end_date")
        if sd and ed and str(ed) < str(sd):
            raise HTTPException(status_code=400, detail="تاريخ نهاية الإجازة قبل بدايتها")

    req = workflow.create_request(db, emp, user, rt, data.payload_json)
    audit(db, user, "submit_request", "request", req.id, detail=rt.code, request=request)
    db.commit()
    return {"ok": True, "id": req.id, "status": req.status, "current_stage": req.current_stage}


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
                   user: models.User = Depends(require_perm("approve_request")),
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
        if workflow.can_decide(db, req, user, stage):
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
           user: models.User = Depends(require_perm("approve_request")),
           db: Session = Depends(get_db)):
    req = _get_req(db, user, req_id)
    if req.status not in ("pending",):
        raise HTTPException(status_code=409, detail="لا يمكن اتخاذ قرار في هذه الحالة")
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    chain = workflow._chain(rt)
    stage = chain[req.current_stage]
    if not workflow.can_decide(db, req, user, stage):
        raise HTTPException(status_code=403, detail="لست المعتمِد لهذه المرحلة")
    if data.decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="قرار غير صالح")
    req = workflow.decide(db, req, user, data.decision, data.note, rt)
    audit(db, user, f"request_{data.decision}", "request", req.id, request=request)
    return {"ok": True, "status": req.status, "current_stage": req.current_stage}


@router.post("/{req_id}/cancel")
def cancel(req_id: int, request: Request, note: str | None = None,
           user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = _get_req(db, user, req_id)
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    try:
        req = workflow.cancel(db, req, user, note, rt)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    audit(db, user, "request_cancel", "request", req.id, request=request)
    return {"ok": True, "status": req.status}


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
    audit(db, user, "set_appointment", "request", req.id, request=request)
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

    audit(db, user, "upload_request_doc", "request", req.id, detail=kind, request=request)
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
    media = "text/html" if doc.file_path.endswith(".html") else "application/octet-stream"
    return FileResponse(doc.file_path, media_type=media,
                        filename=os.path.basename(doc.file_path))


# ----------------------------- مساعدات -----------------------------

def _get_req(db: Session, user: models.User, req_id: int) -> models.Request:
    req = db.get(models.Request, req_id)
    if not req:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    assert_same_company(user, req.company_id)
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
    data = {
        "id": req.id, "type": req.request_type_code,
        "type_name": rt.name if rt else req.request_type_code,
        "employee_id": req.employee_id, "employee_name": emp.name if emp else None,
        "status": req.status, "current_stage": req.current_stage,
        "total_stages": len(chain),
        "payload": req.payload_json, "created_at": req.created_at,
    }
    if full:
        approvals = db.scalars(select(models.RequestApproval).where(
            models.RequestApproval.request_id == req.id)
            .order_by(models.RequestApproval.decided_at)).all()
        by_stage = {a.stage_order: a for a in approvals if a.decision != "rejected"}
        rejected = {a.stage_order for a in approvals if a.decision == "rejected"}
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
            elif i in rejected:
                state = "rejected"
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
            {"kind": d.kind, "version": d.version, "created_at": d.created_at} for d in docs
        ]
    return data
