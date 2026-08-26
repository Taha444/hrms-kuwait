# -*- coding: utf-8 -*-
"""QA-19 — مصدر واحد لحساب امتثال التراخيص.

ROOT CAUSE: اللوحة كانت تعدّ "المنتهية" بشرط ``expiry_date < today`` وحده —
بلا ``status == "active"`` — فتدخل التراخيص المؤرشفة والمستبدَلة في الحساب،
ويصير المقام كل التراخيص في التاريخ لا القائم منها. فظهرت نسبة 24% منتهية
بينما مركز العمليات (الذي يفلتر النشطة) لا يعرض ولا ترخيًصا منتهًيا.

الترخيص المؤرشف ليس مشكلة امتثال: أُنهي أو استُبدل عن قصد. التعريف المعتمد
هو تعريف مركز العمليات لأنه الصفحة التي يذهب إليها المستخدم للتصرّف.
"""
from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import models
from .clock import today as kuwait_today


def license_compliance(db: Session, company_id: int | None, today: date | None = None) -> dict:
    """(الإجمالي، السارية، المنتهية) — للتراخيص النشطة وحدها."""
    today = today or kuwait_today()

    def _count(*conds) -> int:
        q = select(func.count()).select_from(models.License).where(
            models.License.status == "active", *conds)
        if company_id is not None:
            q = q.where(models.License.company_id == company_id)
        return db.scalar(q) or 0

    total = _count()
    valid = _count(or_(models.License.expiry_date.is_(None),
                       models.License.expiry_date >= today))
    expired = _count(models.License.expiry_date.isnot(None),
                     models.License.expiry_date < today)
    return {"total": total, "valid": valid, "expired": expired}
