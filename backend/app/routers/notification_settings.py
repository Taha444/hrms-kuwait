# -*- coding: utf-8 -*-
"""كتالوج قوالب الإشعارات + تفضيلات التسليم لكل مستخدم (FIX-004)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import channels, models
from ..database import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])

#: P10-33 — القائمة من ``channels.CHANNEL_CATALOG`` لا نسخة ثالثة منها.
#: كانت مكتوبة هنا وفي تعليق النموذج وفي مصفوفة داخل شاشة التفضيلات.
CHANNELS = tuple(channels.CHANNEL_CATALOG)


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


@router.get("/channels")
def list_channels(user: models.User = Depends(get_current_user)):
    """P10-33 — القنوات وحالة تكاملها: تقرؤها الشاشة بدل أن تفترضها."""
    return [{"channel": name, **info}
            for name, info in channels.channel_availability().items()]


@router.get("/preferences")
def my_preferences(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """تفضيلات المستخدم لكل (فئة × قناة)، **مع حالة تكامل كل قناة**.

    P10-33 — كان الافتراضي ``True`` للقنوات الأربع بلا شرط: فيرى
    المستخدم واتساب والبريد مُفعَّلين ولا يصله شيء أبًدا. والبريد لا
    صنف قناة له إطلاًقا، فمفتاحه لا يعمل في أي ضبط.

    فما لا يُسلِّم لا يُعرَض مُفعًَّلا افتراًضا، ويصحبه سببه — وخانة
    مُعطَّلة يُقرأ سببها أصدق من وعد لا يقع.
    """
    categories = sorted(db.scalars(select(models.NotificationTemplate.category).distinct()).all())
    saved = {
        (p.category, p.channel): p.enabled
        for p in db.scalars(select(models.NotificationPreference).where(
            models.NotificationPreference.user_id == user.id)).all()
    }
    avail = channels.channel_availability()
    return [
        {"category": cat, "channel": ch,
         # الافتراضي يتبع التكامل؛ واختيار المستخدم الصريح يبقى محفوًظا
         # فلا يُمحى تفضيله يوم يُضبط المزوّد.
         "enabled": saved.get((cat, ch), avail[ch]["available"]),
         "available": avail[ch]["available"],
         "unavailable_reason": avail[ch]["reason"]}
        for cat in categories for ch in CHANNELS
    ]


@router.put("/preferences")
def update_preferences(data: list[PreferenceIn],
                       user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    # P10-33 — والخادم يفرضها لا الواجهة: تعطيل خانة لا يمنع طلًبا مباشًرا،
    # وتفعيل قناة لا تُسلِّم يكتب في القاعدة وعًدا لا يقع.
    #
    # والتعطيل مقبول دائًما: من أراد كتم قناة يُكتم له، سلّمت أو لم تُسلّم.
    avail = channels.channel_availability()
    for item in data:
        if item.channel not in avail:
            raise HTTPException(status_code=400,
                                detail=f"قناة غير معروفة: {item.channel}")
        if item.enabled and not avail[item.channel]["available"]:
            raise HTTPException(
                status_code=409,
                detail=(f"قناة «{avail[item.channel]['label']}» لا تُسلِّم الآن — "
                        f"{avail[item.channel]['reason']}"))

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
