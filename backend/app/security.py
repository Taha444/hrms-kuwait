# -*- coding: utf-8 -*-
"""الأمان: تجزئة كلمات المرور (PBKDF2-SHA256) وإصدار/تحقق رموز JWT.

نستخدم hashlib.pbkdf2_hmac من المكتبة القياسية لتفادي مشاكل بناء
الحزم الأصلية (bcrypt) على إصدارات بايثون الحديثة، مع أمان كافٍ
(عدد دورات مرتفع + ملح عشوائي لكل كلمة مرور).
"""
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from .config import settings

_PBKDF2_ROUNDS = 240_000
_ALGO = "sha256"


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
                        impersonator_id: int | None = None) -> str:
    claims = {"sub": str(subject), "role": role, "company_id": company_id}
    if impersonator_id is not None:
        # يتيح تسجيل impersonate_end لاحًقا (P1-04) بمعرفة من بدأ الانتحال فعًلا
        claims["impersonator_id"] = impersonator_id
    return _create_token(
        claims,
        timedelta(minutes=settings.access_token_expire_minutes),
        "access",
    )


def create_refresh_token(subject: int) -> str:
    return _create_token({"sub": str(subject)}, timedelta(days=settings.refresh_token_expire_days), "refresh")


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
