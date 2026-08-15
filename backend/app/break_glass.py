# -*- coding: utf-8 -*-
"""V2.2 §13.5 (AC-05) — تجاوز Super Admin: حدث موثّق لا صلاحية دائمة.

ROOT CAUSE: ``has_permission`` تعيد True لـsuper_admin مطلًقا، فيملك
``override_approval`` في كل لحظة ويعتمد أي مرحلة عمل بلا أن يطلبها أحد ولا أن
ينتبه إليها أحد — الحساب التقني معتمِد تجاري بحكم الأمر الواقع.

المنع الكامل ليس حًلا: حين يتعطّل الإسناد (موظف بلا فرع، معتمِد غادر الشركة)
يقف العمل ولا مخرج. الحل أن يصير التجاوز حدًثا له سبب ومدة وسجل.
"""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models

# نافذة قصيرة عمًدا: التجاوز الطارئ يُستهلك في دقائق. الساعة تكفي للحالة
# الحقيقية وتضيق عن أن تصير وضًعا دائًما بالإهمال.
DEFAULT_MINUTES = 60
MAX_MINUTES = 240


def active_session(db: Session, user_id: int,
                   now: datetime | None = None) -> models.BreakGlassSession | None:
    """النافذة السارية لهذا المستخدم — أو لا شيء."""
    now = now or datetime.now()
    return db.scalar(select(models.BreakGlassSession).where(
        models.BreakGlassSession.user_id == user_id,
        models.BreakGlassSession.closed_at.is_(None),
        models.BreakGlassSession.expires_at > now,
    ).order_by(models.BreakGlassSession.id.desc()))


def open_session(db: Session, user: models.User, reason: str,
                 minutes: int = DEFAULT_MINUTES,
                 company_id: int | None = None) -> models.BreakGlassSession:
    """يفتح نافذة تجاوز بسبب إلزامي ومدة محدودة."""
    reason = (reason or "").strip()
    if len(reason) < 10:
        raise ValueError("سبب التجاوز إلزامي ومفصّل — لا يُقبل سطر مبهم")
    minutes = max(1, min(int(minutes or DEFAULT_MINUTES), MAX_MINUTES))
    now = datetime.now()
    existing = active_session(db, user.id, now)
    if existing:
        return existing
    row = models.BreakGlassSession(
        user_id=user.id, company_id=company_id or user.company_id,
        reason=reason, started_at=now,
        expires_at=now + timedelta(minutes=minutes),
    )
    db.add(row)
    db.flush()
    return row


def record_use(db: Session, session: models.BreakGlassSession) -> None:
    """يزيد عدّاد الاستخدام — نافذة استُخدمت عشرين مرة ليست حالة طارئة."""
    session.uses = (session.uses or 0) + 1
