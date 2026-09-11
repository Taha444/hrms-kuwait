# -*- coding: utf-8 -*-
"""رموز QR المتغيّرة وتذاكر التسجيل — JWT موقّع بمفتاح الخادم (self-verifying).

- رمز الفرع (qr): JWT قصير الصلاحية (~90 ثانية) يحتوي branch_id + jti، يُعرَض على
  شاشة الفرع ويتجدّد دوريًا. الخادم هو مصدر الحقيقة الوحيد.
- تذكرة التسجيل (checkin_ticket): تُصدَر بعد التحقق من الرمز، صالحة ~3 دقائق ومربوطة
  بالموظف والفرع — حتى لا يفشل التسجيل لو دار الـ QR أثناء التقاط السيلفي.

منع إعادة الاستخدام (anti-replay) عبر تخزين jti المُستهلَك في جدول consumed_tokens.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import hashlib

import jwt
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import models
from .config import settings

QR_TTL_SECONDS = 90
TICKET_TTL_SECONDS = 180
CLOCK_SKEW_LEEWAY = 15  # تحمّل فروق الساعة (± نافذة)


def _encode(payload: dict, ttl: int, token_type: str) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=ttl)
    body = {**payload, "type": token_type, "jti": uuid.uuid4().hex,
            "iat": now, "exp": exp}
    token = jwt.encode(body, settings.secret_key, algorithm=settings.algorithm)
    return token, exp


# **وباٌب ثاٍن لسكّ الرمز يُغلَق.**
#
# كانت هنا ``make_qr_token`` تسكّ رمز فرٍع بمهلة وبلا صلة بمفتاح الشاشة،
# **ولا يستدعيها شيٌء في التطبيق** — تبقيها الاختبارات وحدها. وبقاؤها بعد
# ربط الرمز بالمفتاح سلاٌح مُعبَّأ: من يستعملها غًدا يسكّ رمًزا لا يُبطله
# تدوير، فتعود الثغرة من باٍب لا يمرّ به أحد اليوم.
#
# والاختبارات التي كانت تستعملها كانت تختبر مساًرا لا يسلكه المنتج.


def kiosk_key_fingerprint(kiosk_key: str | None) -> str:
    """بصمٌة قصيرة لمفتاح الشاشة — تُحمَل في الرمز فيُبطله تدويُر المفتاح.

    ولا يُحمَل المفتاح نفسه: الرمز يُعرَض على شاشٍة ويُصوَّر، فحمُله فيه
    تسريٌب له. والبصمة تكفي للمقارنة ولا تكشف الأصل.
    """
    if not kiosk_key:
        return ""
    return hashlib.sha256(kiosk_key.encode("utf-8")).hexdigest()[:16]


def make_static_qr_token(branch_id: int, kiosk_key: str | None) -> str:
    """رمز الفرع — ثابٌت ما دام مفتاح الشاشة ثابًتا، **ويُبطله تدويُره**.

    **العطل المقيس**: كان الرمز ``deterministic`` بلا انتهاء ولا مُعرِّف
    ولا صلة بمفتاح الشاشة — «لا يتغيّر إطلاقًا» بنصّ شرحه. فمن صوّره مرًّة
    يملكه إلى الأبد، **وتدويُر المفتاح لا يُبطله**: يمنع جلَب رمٍز جديد
    من الرابط، ولا يمسّ ما خرج.

    وكان شرحُه يحيل الحماية إلى الـgeofence. والقياس: ``_check_geofence``
    يقيس المسافة **إن أرسل العميل إحداثيات**، وموظُف نمط ``qr`` غير
    مُلزَم بإرسالها. فالدفاع الذي يُبرِّر دواَم الرمز **اختيارٌي بيد
    المتّصل**.

    فصار الرمز يحمل بصمة المفتاح: تدويُر المفتاح يُبطل كل ما صدر قبله —
    وهذا هو معنى «الإبطال» الذي كان الزرّ يَعِد به ولا يفعله.
    """
    # والمفتاح **مُلزِم لا اختياري**: قيمٌة افتراضية تعني رمًزا يُسكّ
    # صحيَح الشكل وميَّت المعنى — يُقبَل عند الإنشاء ويُردّ عند الاستعمال.
    body = {"branch_id": branch_id, "type": "qr", "static": True,
            "kv": kiosk_key_fingerprint(kiosk_key)}
    return jwt.encode(body, settings.secret_key, algorithm=settings.algorithm)


def make_checkin_ticket(employee_id: int, branch_id: int) -> tuple[str, datetime]:
    return _encode({"employee_id": employee_id, "branch_id": branch_id},
                   TICKET_TTL_SECONDS, "checkin_ticket")


def decode(token: str, expected_type: str) -> dict:
    """يفكّ ويتحقّق من التوقيع وانتهاء الصلاحية والنوع. يرفع استثناءً عند الفشل."""
    payload = jwt.decode(
        token, settings.secret_key, algorithms=[settings.algorithm],
        leeway=CLOCK_SKEW_LEEWAY,
    )
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("نوع الرمز غير مطابق")
    return payload


def consume_jti(db: Session, jti: str, kind: str, expires_at: datetime) -> bool:
    """يستهلك jti لمرة واحدة. يُرجع False إن سبق استخدامه (إعادة استخدام)."""
    # تنظيف الرموز المنتهية بشكل انتهازي
    db.execute(delete(models.ConsumedToken).where(
        models.ConsumedToken.expires_at < datetime.now(timezone.utc)))
    if isinstance(expires_at, (int, float)):
        expires_at = datetime.fromtimestamp(expires_at, tz=timezone.utc)
    exists = db.scalar(select(models.ConsumedToken).where(models.ConsumedToken.jti == jti))
    if exists:
        return False
    db.add(models.ConsumedToken(jti=jti, kind=kind, expires_at=expires_at))
    db.flush()
    return True
