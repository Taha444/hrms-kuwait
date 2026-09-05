# -*- coding: utf-8 -*-
"""V1.5 Phase 3 — CRUD للتفويض المؤقت لصلاحية الاعتماد."""
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import audit, get_current_user

router = APIRouter(prefix="/delegations", tags=["delegations"])


class DelegationIn(BaseModel):
    delegate_user_id: int
    reason: str | None = None
    starts_at: datetime
    ends_at: datetime
    scope: str = Field(default="all")


def _may_manage(user: models.User, delegator: models.User) -> bool:
    """يحدد من يستطيع منح/إلغاء تفويض باسم delegator:
    - المستخدم نفسه (يفوّض نائبه)
    - HR أو super_admin
    """
    return user.id == delegator.id or user.role in ("hr", "super_admin")


@router.get("")
def list_delegations(only_active: bool = True,
                     user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """يعرض التفويضات ضمن الشركة. الموظف العادي يرى فقط اللي يخصه (delegator أو delegate)."""
    q = select(models.ApprovalDelegation)
    if user.role not in ("hr", "super_admin"):
        q = q.where(
            (models.ApprovalDelegation.delegator_user_id == user.id)
            | (models.ApprovalDelegation.delegate_user_id == user.id)
        )
    if user.company_id:
        q = q.where(models.ApprovalDelegation.company_id == user.company_id)
    if only_active:
        now = datetime.utcnow()
        q = q.where(
            models.ApprovalDelegation.is_active == True,  # noqa: E712
            models.ApprovalDelegation.starts_at <= now,
            models.ApprovalDelegation.ends_at >= now,
        )
    rows = db.scalars(q.order_by(models.ApprovalDelegation.starts_at.desc())).all()
    # الأسماء لا الأرقام: صفٌّ يقول «12 ← 7» لا يُقرأ. وكانت القائمة
    # تُعيد المعرّفات وحدها لأن لا شاشة تقرؤها.
    names: dict[int, str | None] = {}
    for r in rows:
        for uid in (r.delegator_user_id, r.delegate_user_id):
            if uid not in names:
                u = db.get(models.User, uid)
                names[uid] = (u.full_name or u.civil_id) if u else None
    now = datetime.utcnow()
    return [
        {"id": r.id, "delegator_user_id": r.delegator_user_id,
         "delegator_name": names.get(r.delegator_user_id),
         "delegate_user_id": r.delegate_user_id,
         "delegate_name": names.get(r.delegate_user_id),
         "reason": r.reason,
         "starts_at": r.starts_at, "ends_at": r.ends_at, "scope": r.scope,
         "is_active": r.is_active, "revoked_at": r.revoked_at,
         # **سارٍ الآن** لا «فعّال»: صفٌّ لم تبدأ مدّته أو انقضت يبقى
         # ``is_active`` صحيًحا بينما المحرّك لا يعتدّ به — والفرق يظهر
         # للمستخدم تفويًضا لا يعمل بلا سبب ظاهر.
         "in_effect": bool(r.is_active and r.starts_at <= now <= r.ends_at)}
        for r in rows
    ]


@router.get("/candidates")
def delegation_candidates(user: models.User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """من يمكن تفويضه: زملاء الشركة النشطون، بلا المستخدم نفسه.

    **ولماذا نقطة خاصة**: ``/users`` محجوزة لـ``manage_users``، فمسؤول
    الفرع الذي يسافر لا يجد زميًلا يفوّضه رغم أن الخادم يسمح له بالتفويض
    عن نفسه. وهي أضيق ما يكفي: معرّف واسم ودور — لا بريد ولا هاتف ولا
    رقم مدني.
    """
    if not user.company_id:
        return []
    rows = db.scalars(select(models.User).where(
        models.User.company_id == user.company_id,
        models.User.id != user.id,
        models.User.is_active.is_(True),
    ).order_by(models.User.full_name)).all()
    return [{"id": u.id, "full_name": u.full_name or u.civil_id, "role": u.role}
            for u in rows]


@router.post("", status_code=201)
def create_delegation(data: DelegationIn, request: Request,
                      delegator_user_id: int | None = None,
                      user: models.User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """ينشئ تفويضًا. delegator_user_id اختياري: HR يستطيع منح تفويض باسم أي مستخدم؛
    المستخدم العادي يفوّض عن نفسه فقط."""
    delegator_id = delegator_user_id or user.id
    delegator = db.get(models.User, delegator_id)
    if not delegator:
        raise HTTPException(status_code=404, detail="المفوِّض غير موجود")
    if not _may_manage(user, delegator):
        raise HTTPException(status_code=403, detail="لا يمكنك التفويض باسم مستخدم آخر")
    delegate = db.get(models.User, data.delegate_user_id)
    if not delegate or delegate.company_id != delegator.company_id:
        raise HTTPException(status_code=400, detail="المفوَّض إليه يجب أن يكون في نفس الشركة")
    if delegate.id == delegator.id:
        raise HTTPException(status_code=400, detail="لا يمكن تفويض المستخدم نفسه")
    if data.ends_at <= data.starts_at:
        raise HTTPException(status_code=400, detail="تاريخ انتهاء التفويض قبل بدايته")
    row = models.ApprovalDelegation(
        company_id=delegator.company_id,
        delegator_user_id=delegator.id,
        delegate_user_id=delegate.id,
        reason=data.reason, starts_at=data.starts_at, ends_at=data.ends_at,
        scope=data.scope, is_active=True,
    )
    db.add(row)
    db.flush()
    audit(db, user, "delegation_create", "delegation", row.id,
          detail=f"{delegator.full_name or delegator.role} → {delegate.full_name or delegate.role}",
          request=request)
    db.commit()
    return {"ok": True, "id": row.id}


@router.post("/{delegation_id}/revoke")
def revoke_delegation(delegation_id: int, request: Request,
                      user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(models.ApprovalDelegation, delegation_id)
    if not row:
        raise HTTPException(status_code=404, detail="التفويض غير موجود")
    delegator = db.get(models.User, row.delegator_user_id)
    if not delegator or not _may_manage(user, delegator):
        raise HTTPException(status_code=403, detail="لا يمكنك إلغاء تفويض لا يخصك")
    row.is_active = False
    row.revoked_at = datetime.utcnow()
    row.revoked_by_user_id = user.id
    audit(db, user, "delegation_revoke", "delegation", row.id, request=request)
    db.commit()
    return {"ok": True}
