# -*- coding: utf-8 -*-
"""إرسال الإشعار الفوري إلى **أجهزة** مستخدم — لا إلى مستخدم.

يجمع ثلاثة أشياء بُنيت منفصلة: قرار ``push_policy`` (هل يُدفَع وبأي
نصّ)، وأجهزة ``DeviceToken``، ونقل ``fcm``.

**ولماذا الفصل بقي**: القرار يُختبَر بلا شبكة، والنقل يُختبَر بلا منطق
عمل، وهذه الوحدة تُختبَر بمزوّد مُستبدَل. خلطُها في موضع واحد يجعل كل
اختبار يحتاج Firebase.

**والفشل لا يُفقد إشعاًرا**: الإشعار الداخلي مكتوب في القاعدة قبل أن
تُستدعى هذه الوحدة. فسقوط Firebase يعني أن الموظف يراه حين يفتح
النظام — لا أنه ضاع.

**والجهاز الميت يُوسَم لا يُعاد إليه**: رمز رفضته Firebase يبقى يفشل
مع كل إشعار إلى الأبد، فيبطئ كل إرسال ويملأ السجلّ. يُوسَم مرّة
ويُستبعَد.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from . import models, push_policy
from .fcm import DEAD_TOKEN_ERRORS, is_configured
from .fcm import send as fcm_send

logger = logging.getLogger("hrms.push")


def active_tokens(db, user_id: int) -> list[models.DeviceToken]:
    """أجهزة المستخدم الحيّة — الموسومة ميتة لا يُعاد إليها."""
    return list(db.scalars(select(models.DeviceToken).where(
        models.DeviceToken.user_id == user_id,
        models.DeviceToken.revoked_at.is_(None))).all())


def revoke(db, row: models.DeviceToken, reason: str) -> None:
    """يَسِم جهاًزا ميًتا — ولا يحذفه.

    الحذف يمحو أثر أن الجهاز كان مسجًَّلا، والسجلّ يُسأل عنه: «هل كان
    الإشعار يصل هذا الشخص أصًلا؟».
    """
    row.revoked_at = datetime.now(timezone.utc)
    row.revoked_reason = (reason or "")[:60]


def push_to_user(db, user_id: int, *, kind: str | None,
                 title: str | None, body: str | None,
                 entity_type: str | None = None,
                 entity_id: int | None = None) -> dict:
    """يدفع إشعاًرا إلى كل أجهزة المستخدم الحيّة.

    يعيد حصيلة مقروءة (``sent`` / ``failed`` / ``revoked`` / ``skipped``)
    — لا ``None`` صامًتا: من ينادي يحتاج أن يعرف هل وصل شيء.
    """
    payload = push_policy.build(kind, title, body, entity_type, entity_id)
    if payload is None:
        return {"skipped": "policy", "sent": 0}
    if not is_configured():
        return {"skipped": "not_configured", "sent": 0}

    rows = active_tokens(db, user_id)
    if not rows:
        return {"skipped": "no_devices", "sent": 0}

    sent = failed = revoked = 0
    for row in rows:
        ok, reason = fcm_send(row.token, payload)
        if ok:
            row.last_seen_at = datetime.now(timezone.utc)
            sent += 1
            continue
        failed += 1
        if reason in DEAD_TOKEN_ERRORS:
            revoke(db, row, reason or "dead")
            revoked += 1
    return {"sent": sent, "failed": failed, "revoked": revoked}


def register(db, user_id: int, token: str, *, platform: str = "web",
             label: str | None = None) -> models.DeviceToken:
    """يسجّل جهاًزا، أو **ينقل ملكيّته** إن كان مسجًَّلا لغيره.

    Firebase قد تُعيد الرمز نفسه لجهاز انتقل بين حسابين على المتصفّح
    ذاته. فإنشاء صفّ ثانٍ يعني وصول إشعار زيد إلى جهاز يستعمله عمرو —
    والقيد الفريد على الرمز يمنع ذلك، وهذا الفرع يجعل النقل صريًحا لا
    خطأ قاعدة.
    """
    now = datetime.now(timezone.utc)
    row = db.scalar(select(models.DeviceToken).where(
        models.DeviceToken.token == token))
    if row is None:
        row = models.DeviceToken(user_id=user_id, token=token,
                                 platform=platform, label=label,
                                 last_seen_at=now)
        db.add(row)
        db.flush()
        return row

    if row.user_id != user_id:
        logger.info("نُقل رمز جهاز من المستخدم %s إلى %s", row.user_id, user_id)
    row.user_id = user_id
    row.platform = platform or row.platform
    row.label = label or row.label
    row.last_seen_at = now
    # تسجيل جديد يُحيي جهاًزا وُسِم ميًتا: المستخدم أذِن من جديد.
    row.revoked_at = None
    row.revoked_reason = None
    db.flush()
    return row
