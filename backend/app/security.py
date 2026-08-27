# -*- coding: utf-8 -*-
"""الأمان: تجزئة كلمات المرور (PBKDF2-SHA256) وإصدار/تحقق رموز JWT.

نستخدم hashlib.pbkdf2_hmac من المكتبة القياسية لتفادي مشاكل بناء
الحزم الأصلية (bcrypt) على إصدارات بايثون الحديثة، مع أمان كافٍ
(عدد دورات مرتفع + ملح عشوائي لكل كلمة مرور).
"""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from .config import settings

_PBKDF2_ROUNDS = 240_000
_ALGO = "sha256"

# حروف وأرقام بلا الملتبس منها: 0/O و1/l/I. الكلمة المؤقّتة تُقرأ من شاشة
# وتُكتب بيد، وحرف ملتبس واحد يعني محاولة فاشلة تُقرّب الحساب من القفل.
_PW_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
_PW_SYMBOLS = "!@#$%&*"


def generate_temp_password(length: int = 12) -> str:
    """كلمة مرور مؤقّتة عشوائية — مختلفة لكل شخص وكل مرة.

    البديل الذي كان قائًما كلمة واحدة ثابتة في الإعدادات لكل مستخدم يُنشأ أو
    تُعاد كلمته: من يعرفها يدخل بأي حساب لم يغيّرها صاحبه بعد، وهي مكتوبة في
    المستودع فيعرفها كل من رأى الكود. العشوائية هنا ليست تحسيًنا بل شرط
    أن تعني "كلمة مرور مؤقّتة" شيًئا.

    ``secrets`` لا ``random``: الثاني مولّد قابل للتنبّؤ بمعرفة حالته.
    """
    pool = _PW_ALPHABET + _PW_SYMBOLS
    while True:
        pw = "".join(secrets.choice(pool) for _ in range(length))
        # نضمن التنوّع صراحة بدل الاتّكال على الاحتمال — سياسات التعقيد
        # ترفض كلمة خلت مصادفًة من رقم أو رمز.
        if (any(c.isdigit() for c in pw) and any(c.islower() for c in pw)
                and any(c.isupper() for c in pw) and any(c in _PW_SYMBOLS for c in pw)):
            return pw


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac(_ALGO, password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_{_ALGO}${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, rounds, salt_hex, hash_hex = stored.split("$")
        if not scheme.startswith("pbkdf2_"):
            return False
        algo = scheme.split("_", 1)[1]
        dk = hashlib.pbkdf2_hmac(algo, password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except (ValueError, AttributeError):
        return False


def _create_token(data: dict, expires_delta: timedelta, token_type: str) -> str:
    payload = data.copy()
    now = datetime.now(timezone.utc)
    payload.update({"exp": now + expires_delta, "iat": now, "type": token_type})
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(subject: int, role: str, company_id: int | None,
                        impersonator_id: int | None = None,
                        active_company_id: int | None = None) -> str:
    """R9 §16 — active_company_id يُستخدم لمستخدمي is_cross_company:
    التوكن يحمل company_id=NULL لكن active_company_id=X، والسيرفر يستنتج منه
    الشركة الحالية + employee_id عبر UserCompanyLink."""
    claims = {"sub": str(subject), "role": role, "company_id": company_id}
    if impersonator_id is not None:
        # يتيح تسجيل impersonate_end لاحًقا (P1-04) بمعرفة من بدأ الانتحال فعًلا
        claims["impersonator_id"] = impersonator_id
    if active_company_id is not None:
        claims["active_company_id"] = int(active_company_id)
    return _create_token(
        claims,
        timedelta(minutes=settings.access_token_expire_minutes),
        "access",
    )


def create_refresh_token(subject: int, impersonator_id: int | None = None) -> str:
    """رمز التجديد يحمل وسم الانتحال إن وُجد.

    بدونه تُولَد من رمز تجديد جلسةِ انتحالٍ رموزُ دخول نظيفة، فتُقيَّد الأفعال
    على المُنتحَل وحده ويضيع من فعلها حًقا — وهو السؤال الوحيد الذي وُجد
    الانتحال ليجيبه. الوسم يسري مع الجلسة كلها لا مع أول رمز فيها.
    """
    claims: dict = {"sub": str(subject)}
    if impersonator_id is not None:
        claims["impersonator_id"] = impersonator_id
    return _create_token(claims, timedelta(days=settings.refresh_token_expire_days), "refresh")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
