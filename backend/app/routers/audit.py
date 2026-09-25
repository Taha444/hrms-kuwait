# -*- coding: utf-8 -*-
"""عرض سجل التدقيق (Audit Trail) — مفلتر حسب الشركة، للإدارة والمالك والمدير."""
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..clock import KUWAIT_TZ
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
    # اليومُ في الفلتر هو **يوم الكويت** (كما تعرضه الشاشة)، والمخزَّن UTC: يبدأ يومُ الكويت 21:00 UTC
    # من اليوم السابق — فحدثٌ عند 01:00 صباحًا بتوقيت الكويت كان يسقط من يومه ويظهر في اليوم الذي قبله.
    def _kuwait_day_utc(d: date) -> datetime:
        return datetime.combine(d, time.min, KUWAIT_TZ).astimezone(timezone.utc).replace(tzinfo=None)

    if from_date:
        q = q.where(models.AuditLog.created_at >= _kuwait_day_utc(from_date))
    if to_date:
        q = q.where(models.AuditLog.created_at < _kuwait_day_utc(to_date + timedelta(days=1)))
    limit = max(1, min(limit, 500))
    rows = db.scalars(q.order_by(models.AuditLog.created_at.desc())
                      .limit(limit).offset(max(offset, 0))).all()
    # خرائط أسماء للعرض
    user_names = {u.id: u.full_name for u in db.scalars(select(models.User)).all()}
    # QA-26 — لا سجل بلا منفذ: ما لا فاعل بشري له هو فعل النظام صراحًة
    # (مجدوِل/صيانة)، لا حقل فارغ يُقرأ كعطل.
    # P11-36 — من فعل حًقا، لا الاسم المعروض وحده.
    #
    # ``original_user_id`` كان يُكتب في كل صفّ يقع تحت انتحال — ولا
    # يقرؤه أحد. فقُرئ اعتماد نفّذه مدير النظام بانتحال شخصية موظف
    # الشؤون القانونية على أنه فعل الأخير، وهو الاسم الذي يبقى في
    # السجلّ إلى الأبد أمام من يراجع.
    #
    # ولا يُستبدَل الاسم بل يُضاف إليه: من يقرأ يحتاج الاثنين — تحت أي
    # صلاحية وقع الفعل، ومن يجلس أمام الشاشة.
    return [{"id": r.id, "action": r.action, "entity_type": r.entity_type,
             "entity_id": r.entity_id, "detail": r.detail, "ip": r.ip,
             "by": user_names.get(r.user_id) if r.user_id else None,
             "by_system": r.user_id is None,
             "on_behalf": bool(r.original_user_id),
             "acted_by": (user_names.get(r.original_user_id)
                          if r.original_user_id else None),
             # **الحقول المخزَّنة كلُّها تُعرض** (M22، 2026-09-24): القاعدة تحفظ الصفة وقت
             # الفعل والنتيجة والسبب وقبل/بعد والمعرّف المشترك ومتصفّح الفاعل، والواجهة كانت
             # تعرض أحد عشر حقلًا فقط — فلا يُرى إن كان الفعل نجح أم فشل، ولا بأي صفة وقع.
             "company_id": r.company_id, "branch_id": r.branch_id,
             "actor_role": r.actor_role, "result": r.result, "reason": r.reason,
             "before": r.before_json, "after": r.after_json,
             "correlation_id": r.correlation_id, "user_agent": r.user_agent,
             "at": r.created_at}
            for r in rows]
