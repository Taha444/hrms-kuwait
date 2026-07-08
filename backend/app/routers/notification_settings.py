# -*- coding: utf-8 -*-
"""كتالوج قوالب الإشعارات + تفضيلات التسليم لكل مستخدم (FIX-004)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])

CHANNELS = ("in_app", "whatsapp", "sms", "email")


@router.get("/templates")
def list_notification_templates(category: str | None = None,
                                user: models.User = Depends(get_current_user),
                                db: Session = Depends(get_db)):
    q = select(models.NotificationTemplate).where(models.NotificationTemplate.is_active == True)  # noqa: E712
    if category:
        q = q.where(models.NotificationTemplate.category == category)
    rows = db.scalars(q.order_by(models.NotificationTemplate.code)).all()
    return [{"code": t.code, "name": t.name, "category": t.category, "event_type": t.event_type,
            "channel_default": t.channel_default, "sla_hours": t.sla_hours} for t in rows]


@router.get("/templates/categories")
def notification_categories(db: Session = Depends(get_db),
                            user: models.User = Depends(get_current_user)):
    rows = db.scalars(select(models.NotificationTemplate.category).distinct()).all()
    return sorted(rows)


class PreferenceIn(BaseModel):
    category: str
    channel: str
    enabled: bool


@router.get("/preferences")
def my_preferences(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """تفضيلات المستخدم الحالي لكل (فئة × قناة) — القيمة الافتراضية مفعّلة."""
    categories = sorted(db.scalars(select(models.NotificationTemplate.category).distinct()).all())
    saved = {
        (p.category, p.channel): p.enabled
        for p in db.scalars(select(models.NotificationPreference).where(
            models.NotificationPreference.user_id == user.id)).all()
    }
    return [
        {"category": cat, "channel": ch, "enabled": saved.get((cat, ch), True)}
        for cat in categories for ch in CHANNELS
    ]


@router.put("/preferences")
def update_preferences(data: list[PreferenceIn],
                       user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    for item in data:
        row = db.scalar(select(models.NotificationPreference).where(
            models.NotificationPreference.user_id == user.id,
            models.NotificationPreference.category == item.category,
            models.NotificationPreference.channel == item.channel,
        ))
        if row:
            row.enabled = item.enabled
        else:
            db.add(models.NotificationPreference(
                user_id=user.id, category=item.category, channel=item.channel,
                enabled=item.enabled,
            ))
    db.commit()
    return {"ok": True}
