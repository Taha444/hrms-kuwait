# -*- coding: utf-8 -*-
"""V1.5 Phase 3 — Approval Delegation (V2.2 §3.1 Approver: تفويض مؤقت).

مسؤولية الوحدة: البحث عن المستخدمين المفوَّض إليهم صلاحية اعتماد مؤقتة بحيث يضافون
إلى قائمة الـ approvers للمرحلة الحالية دون تعديل approval_chain_json.

قاعدة أمان: التفويض لا يمنح صلاحية أعلى من صلاحية المفوِّض؛ فقط يوسّع دائرة من يمكنه
تنفيذ نفس القرار.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


def active_delegates_for(db: Session, delegator_user_id: int,
                         company_id: int | None = None) -> list[models.User]:
    """يعيد قائمة المستخدمين المفوَّض إليهم صلاحية اعتماد الحالية باسم المفوِّض المحدد."""
    now = datetime.now(timezone.utc)
    q = select(models.ApprovalDelegation).where(
        models.ApprovalDelegation.delegator_user_id == delegator_user_id,
        models.ApprovalDelegation.is_active == True,  # noqa: E712
        models.ApprovalDelegation.starts_at <= now,
        models.ApprovalDelegation.ends_at >= now,
    )
    if company_id is not None:
        q = q.where(models.ApprovalDelegation.company_id == company_id)
    rows = db.scalars(q).all()
    out: list[models.User] = []
    for row in rows:
        u = db.get(models.User, row.delegate_user_id)
        if u and u.is_active:
            out.append(u)
    return out


def is_valid_delegator_for(db: Session, delegate_user_id: int,
                           delegator_user_id: int, company_id: int | None = None) -> bool:
    """يتحقق إذا كان delegate_user_id مفوَّض حاليًا من delegator_user_id."""
    now = datetime.now(timezone.utc)
    q = select(models.ApprovalDelegation).where(
        models.ApprovalDelegation.delegator_user_id == delegator_user_id,
        models.ApprovalDelegation.delegate_user_id == delegate_user_id,
        models.ApprovalDelegation.is_active == True,  # noqa: E712
        models.ApprovalDelegation.starts_at <= now,
        models.ApprovalDelegation.ends_at >= now,
    )
    if company_id is not None:
        q = q.where(models.ApprovalDelegation.company_id == company_id)
    return db.scalar(q) is not None


def expand_approvers_with_delegates(db: Session, approvers: list[models.User],
                                    company_id: int | None) -> list[models.User]:
    """يضيف كل المفوَّض إليهم من أي approver أصلي في القائمة، بدون تكرار."""
    seen = {u.id for u in approvers}
    out = list(approvers)
    for u in approvers:
        for d in active_delegates_for(db, u.id, company_id):
            if d.id not in seen:
                seen.add(d.id)
                out.append(d)
    return out
