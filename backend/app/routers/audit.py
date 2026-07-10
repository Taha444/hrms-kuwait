# -*- coding: utf-8 -*-
"""عرض سجل التدقيق (Audit Trail) — مفلتر حسب الشركة، للإدارة والمالك والمدير."""
from datetime import date, datetime, time

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import require_perm, scope_company_id

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(company_id: int | None = None, limit: int = 100, offset: int = 0,
               action: str | None = None, entity_type: str | None = None,
               entity_id: int | None = None, user_id: int | None = None,
               from_date: date | None = None, to_date: date | None = None,
               user: models.User = Depends(require_perm("view_audit")),
               db: Session = Depends(get_db)):
    """فلاتر التدقيق (P1-04): إضافة entity_type/entity_id/user_id ومدى تاريخي، فوق
    company_id/action الموجودَين أصًلا — تُسهّل تتبّع كل ما جرى على كيان أو مستخدم بعينه."""
    cid = scope_company_id(user, company_id)
    q = select(models.AuditLog)
    if cid is not None:
        q = q.where(models.AuditLog.company_id == cid)
    if action:
        q = q.where(models.AuditLog.action == action)
    if entity_type:
        q = q.where(models.AuditLog.entity_type == entity_type)
    if entity_id is not None:
        q = q.where(models.AuditLog.entity_id == entity_id)
    if user_id is not None:
        q = q.where(models.AuditLog.user_id == user_id)
    if from_date:
        q = q.where(models.AuditLog.created_at >= datetime.combine(from_date, time.min))
    if to_date:
        q = q.where(models.AuditLog.created_at <= datetime.combine(to_date, time.max))
    limit = max(1, min(limit, 500))
    rows = db.scalars(q.order_by(models.AuditLog.created_at.desc())
                      .limit(limit).offset(max(offset, 0))).all()
    # خرائط أسماء للعرض
    user_names = {u.id: u.full_name for u in db.scalars(select(models.User)).all()}
    return [{"id": r.id, "action": r.action, "entity_type": r.entity_type,
             "entity_id": r.entity_id, "detail": r.detail, "ip": r.ip,
             "by": user_names.get(r.user_id, r.user_id), "at": r.created_at}
            for r in rows]
