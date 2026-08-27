# -*- coding: utf-8 -*-
"""إبطال رمز بعينه قبل انتهاء صلاحيته.

المشكلة أن JWT لا يُسترجع: من حمله ظلّ صالًحا حتى انقضاء مدّته مهما فعل
صاحبه. فكان «تسجيل الخروج» يمسح الرمز من المتصفح ولا يمسّ الرمز نفسه —
يبقى صالًحا نصف ساعة، ورمز التجديد أربعة عشر يوًما. وكذلك «إنهاء الانتحال»:
يكتب سطر تدقيق ولا يُنهي شيًئا. زرّان يقولان إن الجلسة انتهت وهي لم تنتهِ.

والبديل الأسهل — رفع ``tokens_valid_after`` للمستخدم — مرفوض عمًدا: يُخرجه
من كل أجهزته، وفي حالة الانتحال يعاقب المُنتحَل على فعل غيره. الإبطال هنا
**لرمز بعينه** (jti) لا لمستخدم.

كل الإبطال يمرّ من هنا: الخروج، وإنهاء الانتحال، وأي مسار مقبل. قاعدة
واحدة في مكان واحد بدل نسختين تفترقان.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from . import models
from .security import decode_token

#: تنظيف الصفوف المنتهية لا يستحقّ استعلاًما في كل نداء
_CLEAN_EVERY = 200
_calls = 0


def _naive(dt: datetime) -> datetime:
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def revoke_token(db: Session, token: str, reason: str,
                 user_id: int | None = None) -> bool:
    """يُبطل رمًزا واحًدا. يعيد False إن كان الرمز غير مقروء أو بلا jti.

    لا يرفع استثناء على رمز تالف: الخروج يجب أن ينجح دائًما من جهة
    المستخدم — أسوأ ما يحدث أن يكون الرمز الذي أراد إبطاله غير صالح أصًلا.
    """
    try:
        payload = decode_token(token)
    except Exception:
        return False
    jti = payload.get("jti")
    exp = payload.get("exp")
    if not jti or not exp:
        # رمز صدر قبل إضافة jti — سيموت بمدّته وحدها. لا نُسقط بقيّة الخروج
        # بسببه، لكن لا ندّعي أنه أُبطل.
        return False
    if db.get(models.RevokedToken, jti):
        return True                      # مُبطل مسبًقا — الإبطال عملية عاقرة
    db.add(models.RevokedToken(
        jti=jti,
        user_id=user_id if user_id is not None else _sub(payload),
        expires_at=_naive(datetime.fromtimestamp(int(exp), tz=timezone.utc)),
        reason=reason[:40],
    ))
    return True


def _sub(payload: dict) -> int | None:
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None


def is_revoked(db: Session, payload: dict) -> bool:
    """هل أُبطل هذا الرمز؟ يُنادى في مسار كل طلب، فالبحث بالمفتاح وحده."""
    global _calls
    jti = payload.get("jti")
    if not jti:
        return False                     # رمز قديم بلا jti — تحكمه مدّته
    _calls += 1
    if _calls % _CLEAN_EVERY == 0:
        purge_expired(db)
    return db.get(models.RevokedToken, jti) is not None


def purge_expired(db: Session) -> int:
    """يحذف ما انتهت صلاحيته: بعدها يرفض الرمزَ انتهاؤه نفسه.

    بلا هذا ينمو الجدول بلا حدّ على خدمة تعمل شهوًرا — نفس العيب الذي
    أُصلح في عدّاد محاولات الدخول، ولا سبب لتكراره هنا.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    res = db.execute(delete(models.RevokedToken).where(
        models.RevokedToken.expires_at < now))
    db.commit()
    return res.rowcount or 0
