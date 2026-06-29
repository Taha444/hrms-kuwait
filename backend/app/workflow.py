# -*- coding: utf-8 -*-
"""محرّك الطلبات والموافقات (configurable Requests & Approvals).

كل نوع طلب يُعرَّف بسلسلة مراحل مرتّبة (approval_chain_json). كل مرحلة:
  { "order": 0, "label": "...", "role": "branch_supervisor", "kind": "approval",
    "produces_document": false }

أنواع المراحل (kind):
- approval     : يحتاج قرار اعتماد/رفض من صاحب الدور.
- hr_review    : يعتمد HR ثم يولّد المستند ويحدد موعد توقيع (awaiting_signature)،
                 وبعد رفع الموقّع يتقدّم الطلب.
- delegate_exit: مهمة للمندوب لإجراءات إذن المغادرة (awaiting_delegate)،
                 وبعد رفع إذن المغادرة يكتمل الطلب.
- pickup       : إشعار HR والعامل بأن المستند جاهز للاستلام (ready_for_pickup).

المدير العام / صاحب الشركة / الإدارة العليا يحق لهم الرفض/الإلغاء في أي مرحلة.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .notifications import create_task, notify_employee_self, users_by_role

# إلغاء الطلب إجراء تشغيلي → المالك (اطلاع فقط) مستبعَد
CANCEL_ROLES = {"super_admin", "company_manager"}


# ----------------------- أنواع الطلبات الافتراضية (للـ seed) -----------------------

DEFAULT_REQUEST_TYPES = [
    {
        "code": "leave",
        "name": "طلب إجازة",
        "requires_physical_signature": True,
        "produces_document": True,
        "approval_chain_json": [
            {"order": 0, "label": "اعتماد مسؤول الفرع", "role": "branch_supervisor", "kind": "approval"},
            {"order": 1, "label": "اعتماد المدير العام", "role": "company_manager", "kind": "approval"},
            {"order": 2, "label": "مراجعة شؤون الموظفين وتحديد موعد التوقيع", "role": "hr",
             "kind": "hr_review", "produces_document": True},
            {"order": 3, "label": "إجراءات إذن مغادرة البلاد (المندوب)", "role": "delegate",
             "kind": "delegate_exit"},
        ],
        "template_html": None,
    },
    {
        "code": "salary_certificate",
        "name": "طلب شهادة راتب",
        "requires_physical_signature": False,
        "produces_document": True,
        "approval_chain_json": [
            {"order": 0, "label": "اعتماد وتوقيع المدير العام", "role": "company_manager",
             "kind": "approval", "produces_document": True},
            {"order": 1, "label": "جاهزة للاستلام من شؤون الموظفين", "role": "hr", "kind": "pickup"},
        ],
        "template_html": None,
    },
]


def get_request_type(db: Session, company_id: int, code: str) -> models.RequestType | None:
    """يبحث عن نوع الطلب الخاص بالشركة أولًا ثم العام (company_id=None)."""
    rt = db.scalar(
        select(models.RequestType).where(
            models.RequestType.code == code,
            models.RequestType.company_id == company_id,
            models.RequestType.is_active == True,  # noqa: E712
        )
    )
    if rt:
        return rt
    return db.scalar(
        select(models.RequestType).where(
            models.RequestType.code == code,
            models.RequestType.company_id.is_(None),
            models.RequestType.is_active == True,  # noqa: E712
        )
    )


def _chain(rt: models.RequestType) -> list[dict]:
    return sorted(rt.approval_chain_json or [], key=lambda s: s.get("order", 0))


def resolve_stage_approvers(db: Session, req: models.Request, stage: dict) -> list[models.User]:
    """يحدد المستخدمين المعنيين بمرحلة معيّنة حسب الدور (وفرع العامل)."""
    role = stage.get("role")
    if role == "branch_supervisor":
        emp = db.get(models.Employee, req.employee_id)
        if emp and emp.branch_id:
            sup_ids = [
                bs.user_id for bs in db.scalars(
                    select(models.BranchSupervisor).where(
                        models.BranchSupervisor.branch_id == emp.branch_id
                    )
                ).all()
            ]
            users = [db.get(models.User, uid) for uid in sup_ids]
            users = [u for u in users if u and u.is_active]
            if users:
                return users
        # لا يوجد مسؤول فرع → يتجاوز للمدير العام
        return users_by_role(db, req.company_id, ["company_manager"])
    return users_by_role(db, req.company_id, [role]) if role else []


def can_decide(db: Session, req: models.Request, user: models.User, stage: dict) -> bool:
    if user.role == "super_admin":
        return True
    if user.company_id != req.company_id:
        return False
    # المدير العام يستطيع التدخّل في أي مرحلة
    if user.role in ("company_manager", "company_owner"):
        return True
    approvers = resolve_stage_approvers(db, req, stage)
    return any(u.id == user.id for u in approvers)


def _employee_name(db: Session, req: models.Request) -> str:
    emp = db.get(models.Employee, req.employee_id)
    return emp.name if emp else f"#{req.employee_id}"


def create_request(db: Session, employee: models.Employee, requester: models.User,
                   rt: models.RequestType, payload: dict) -> models.Request:
    req = models.Request(
        company_id=employee.company_id, employee_id=employee.id,
        requester_user_id=requester.id, request_type_code=rt.code,
        payload_json=payload, status="pending", current_stage=0,
    )
    db.add(req)
    db.flush()
    enter_stage(db, req, rt)
    db.commit()
    db.refresh(req)
    return req


def enter_stage(db: Session, req: models.Request, rt: models.RequestType) -> None:
    """يهيّئ المرحلة الحالية: ضبط الحالة وإنشاء المهام للمستلِمين."""
    chain = _chain(rt)
    if req.current_stage >= len(chain):
        return _finalize(db, req)
    stage = chain[req.current_stage]
    kind = stage.get("kind", "approval")
    name = _employee_name(db, req)
    label = stage.get("label", "")

    if kind in ("approval", "hr_review"):
        req.status = "pending"
        for u in resolve_stage_approvers(db, req, stage):
            create_task(
                db, company_id=req.company_id, assignee_user_id=u.id, type="request_stage",
                title=f"بانتظار موافقتك: {rt.name} — {name}",
                detail=f"المرحلة: {label}. اطّلع على الطلب لاعتماده أو رفضه.",
                related_entity_type="request", related_entity_id=req.id,
                severity="info", dedup_key=f"req_stage:{req.id}:{req.current_stage}:u{u.id}",
            )
    elif kind == "delegate_exit":
        req.status = "awaiting_delegate"
        p = req.payload_json or {}
        for u in users_by_role(db, req.company_id, ["delegate"]):
            create_task(
                db, company_id=req.company_id, assignee_user_id=u.id, type="exit_permit",
                title=f"إجراءات إذن مغادرة البلاد: {name}",
                detail=(f"تم منح {name} إجازة من {p.get('start_date','')} إلى {p.get('end_date','')}، "
                        "برجاء البدء في إجراءات إذن مغادرة البلاد ورفعه على النظام."),
                related_entity_type="request", related_entity_id=req.id,
                severity="warning", dedup_key=f"req_exit:{req.id}",
            )
    elif kind == "pickup":
        req.status = "ready_for_pickup"
        for u in users_by_role(db, req.company_id, ["hr"]):
            create_task(
                db, company_id=req.company_id, assignee_user_id=u.id, type="pickup_ready",
                title=f"مستند جاهز للحفظ/التسليم: {rt.name} — {name}",
                detail="تم اعتماد الطلب. احفظ المستند وسلّمه للعامل عند حضوره.",
                related_entity_type="request", related_entity_id=req.id,
                dedup_key=f"req_pickup_hr:{req.id}",
            )
        notify_employee_self(
            db, req.employee_id, type="pickup_ready",
            title=f"{rt.name} جاهزة للاستلام",
            detail="يرجى استلام المستند من مكتب شؤون الموظفين.",
            related_entity_type="request", related_entity_id=req.id,
            dedup_key=f"req_pickup_emp:{req.id}",
        )

    # إشعار العامل بالتقدّم
    notify_employee_self(
        db, req.employee_id, type="request_update",
        title=f"تحديث على طلبك: {rt.name}",
        detail=f"وصل طلبك إلى مرحلة: {label}.",
        related_entity_type="request", related_entity_id=req.id,
        dedup_key=f"req_progress:{req.id}:{req.current_stage}",
    )


def decide(db: Session, req: models.Request, user: models.User, decision: str,
           note: str | None, rt: models.RequestType) -> models.Request:
    chain = _chain(rt)
    stage = chain[req.current_stage]
    approval = models.RequestApproval(
        request_id=req.id, stage_order=req.current_stage,
        stage_label=stage.get("label", ""), approver_role=user.role,
        approver_user_id=user.id, decision=decision, note=note,
    )
    db.add(approval)

    if decision == "rejected":
        req.status = "rejected"
        req.closed_at = datetime.now(timezone.utc)
        _notify_terminated(db, req, rt, "rejected", user, note)
        db.commit()
        db.refresh(req)
        return req

    # اعتماد
    kind = stage.get("kind", "approval")
    if kind == "hr_review":
        # يولّد المستند وينتقل لحالة انتظار التوقيع (لا يتقدّم حتى رفع الموقّع)
        generate_document(db, req, rt, kind="generated_pdf", actor=user)
        req.status = "awaiting_signature"
        notify_employee_self(
            db, req.employee_id, type="appointment",
            title="مطلوب حضورك للتوقيع",
            detail="برجاء مراجعة مسؤول شؤون الموظفين في مقر الشركة لإتمام طلبك بالتوقيع.",
            related_entity_type="request", related_entity_id=req.id,
            dedup_key=f"req_sign:{req.id}",
        )
        db.commit()
        db.refresh(req)
        return req

    if stage.get("produces_document"):
        generate_document(db, req, rt, kind="generated_pdf", actor=user)

    _advance(db, req, rt)
    db.commit()
    db.refresh(req)
    return req


def upload_signed_scan_done(db: Session, req: models.Request, rt: models.RequestType) -> None:
    """يُستدعى بعد رفع نسخة موقّعة في مرحلة hr_review → يتقدّم الطلب."""
    _advance(db, req, rt)
    db.commit()


def upload_exit_permit_done(db: Session, req: models.Request, rt: models.RequestType) -> None:
    """يُستدعى بعد رفع إذن المغادرة في مرحلة delegate_exit → يكتمل الطلب."""
    name = _employee_name(db, req)
    notify_employee_self(
        db, req.employee_id, type="exit_permit",
        title="إذن مغادرة البلاد جاهز",
        detail=f"تم إنهاء إجراءات إذن المغادرة الخاص بـ {name}. يمكنك طباعته والسفر.",
        related_entity_type="request", related_entity_id=req.id,
        dedup_key=f"req_exit_ready:{req.id}",
    )
    _advance(db, req, rt)
    db.commit()


def mark_pickup_received(db: Session, req: models.Request, rt: models.RequestType) -> None:
    _advance(db, req, rt)
    db.commit()


def _advance(db: Session, req: models.Request, rt: models.RequestType) -> None:
    req.current_stage += 1
    if req.current_stage >= len(_chain(rt)):
        _finalize(db, req)
    else:
        enter_stage(db, req, rt)


def _finalize(db: Session, req: models.Request) -> None:
    req.status = "completed"
    req.closed_at = datetime.now(timezone.utc)
    notify_employee_self(
        db, req.employee_id, type="request_update",
        title="اكتمل طلبك",
        detail="تم إنهاء جميع مراحل طلبك بنجاح.",
        related_entity_type="request", related_entity_id=req.id,
        dedup_key=f"req_done:{req.id}",
    )


def cancel(db: Session, req: models.Request, user: models.User, note: str | None,
           rt: models.RequestType) -> models.Request:
    """إلغاء/رفض من المدير العام في أي مرحلة → إشعار كل الأطراف."""
    if user.role not in CANCEL_ROLES:
        raise PermissionError("الإلغاء من صلاحية المدير العام / الإدارة العليا فقط")
    req.status = "cancelled"
    req.closed_at = datetime.now(timezone.utc)
    db.add(models.RequestApproval(
        request_id=req.id, stage_order=req.current_stage, stage_label="إلغاء المدير العام",
        approver_role=user.role, approver_user_id=user.id, decision="rejected", note=note,
    ))
    _notify_terminated(db, req, rt, "cancelled", user, note)
    db.commit()
    db.refresh(req)
    return req


def _notify_terminated(db: Session, req: models.Request, rt: models.RequestType,
                       kind: str, actor: models.User, note: str | None) -> None:
    """يُشعر العامل وكل من اعتمد أو كان سيعتمد بالرفض/الإلغاء."""
    word = "رفض" if kind == "rejected" else "إلغاء"
    reason = f" السبب: {note}" if note else ""
    # العامل
    notify_employee_self(
        db, req.employee_id, type="request_update",
        title=f"تم {word} طلبك: {rt.name}",
        detail=f"تم {word} الطلب من قبل {actor.full_name or actor.role}.{reason}",
        related_entity_type="request", related_entity_id=req.id,
        dedup_key=f"req_term_emp:{req.id}",
    )
    # كل من اعتمد سابقًا
    approved_uids = {
        a.approver_user_id for a in db.scalars(
            select(models.RequestApproval).where(models.RequestApproval.request_id == req.id)
        ).all() if a.approver_user_id
    }
    # ومن كان سيعتمد في المراحل المتبقية
    chain = _chain(rt)
    future_users: set[int] = set()
    for stage in chain[req.current_stage:]:
        for u in resolve_stage_approvers(db, req, stage):
            future_users.add(u.id)
    for uid in (approved_uids | future_users):
        if uid == actor.id:
            continue
        create_task(
            db, company_id=req.company_id, assignee_user_id=uid, type="request_update",
            title=f"تم {word} طلب: {rt.name} — {_employee_name(db, req)}",
            detail=f"قام {actor.full_name or actor.role} بـ{word} الطلب.{reason}",
            related_entity_type="request", related_entity_id=req.id,
            dedup_key=f"req_term:{req.id}:u{uid}",
        )


def generate_document(db: Session, req: models.Request, rt: models.RequestType,
                      kind: str, actor: models.User) -> models.RequestDocument:
    """يولّد مستند الطلب (HTML قابل للطباعة) مع عبارة 'اعتمد من قبل'."""
    emp = db.get(models.Employee, req.employee_id)
    company = db.get(models.Company, req.company_id)
    approvals = db.scalars(
        select(models.RequestApproval).where(
            models.RequestApproval.request_id == req.id,
            models.RequestApproval.decision == "approved",
        )
    ).all()
    html = render_document_html(rt, req, emp, company, approvals)

    os.makedirs(settings.upload_dir, exist_ok=True)
    fname = f"request_{req.id}_{kind}_{int(datetime.now().timestamp())}.html"
    fpath = os.path.join(settings.upload_dir, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(html)

    existing = db.scalars(
        select(models.RequestDocument).where(
            models.RequestDocument.request_id == req.id,
            models.RequestDocument.kind == kind,
        )
    ).all()
    doc = models.RequestDocument(
        request_id=req.id, kind=kind, file_path=fpath,
        version=len(existing) + 1, uploaded_by=actor.id,
    )
    db.add(doc)
    return doc


def render_document_html(rt, req, emp, company, approvals) -> str:
    from html import escape as e  # تهريب القيم لمنع حقن HTML/XSS

    p = req.payload_json or {}
    rows = "".join(
        f"<li>اعتمد من قبل: <b>{e(a.stage_label or '')}</b> ({e(a.approver_role or '')}) بتاريخ "
        f"{a.decided_at.strftime('%Y-%m-%d %H:%M')}</li>"
        for a in approvals
    )
    body_extra = ""
    if rt.code == "leave":
        body_extra = (
            f"<p>نوع الإجازة: {e(str(p.get('leave_type','اعتيادية')))}</p>"
            f"<p>من تاريخ: {e(str(p.get('start_date','')))} إلى تاريخ: {e(str(p.get('end_date','')))} "
            f"(عدد الأيام: {e(str(p.get('days','')))})</p>"
            f"<p>السبب: {e(str(p.get('reason','')))}</p>"
        )
    elif rt.code == "salary_certificate":
        body_extra = (
            f"<p>الجهة المستفيدة: {e(str(p.get('addressed_to','')))}</p>"
            f"<p>الغرض: {e(str(p.get('purpose','')))}</p>"
            f"<p>الراتب الأساسي: {getattr(emp,'basic_salary',0)} د.ك</p>"
        )
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>{e(rt.name)}</title>
<style>
body{{font-family:'Segoe UI',Tahoma,Arial;margin:40px;color:#111}}
.header{{text-align:center;border-bottom:2px solid #333;padding-bottom:12px;margin-bottom:24px}}
.muted{{color:#666;font-size:13px}} .sign{{margin-top:60px}}
ul{{line-height:1.9}} @media print{{.noprint{{display:none}}}}
</style></head><body>
<div class="header">
  <h2>{e(company.name) if company else ''}</h2>
  <h3>{e(rt.name)}</h3>
  <div class="muted">رقم الطلب: {req.id} — تاريخ: {datetime.now().strftime('%Y-%m-%d')}</div>
</div>
<p>الموظف: <b>{e(emp.name) if emp else ''}</b> — الرقم المدني: {e(getattr(emp,'civil_id','') or '')}</p>
<p>الوظيفة: {e(getattr(emp,'job_title','') or '')}</p>
{body_extra}
<hr><h4>سلسلة الاعتماد</h4><ul>{rows or '<li>—</li>'}</ul>
<div class="sign">
  <p>توقيع الموظف: ............................</p>
  <p>توقيع/ختم الشركة: ............................</p>
</div>
<button class="noprint" onclick="window.print()">طباعة</button>
</body></html>"""
