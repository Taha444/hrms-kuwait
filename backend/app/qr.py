# -*- coding: utf-8 -*-
"""توليد/تحقق رمز QR متغيّر بالوقت لكل فرع (TOTP-like).

الرمز يتجدد كل 60 ثانية ويُشتق من سرّ الفرع (qr_secret) — لمنع تصوير
رمز ثابت والتسجيل من بعيد. التحقق يسمح بنافذة ±1 لتفادي فروق الساعة.
"""
import hashlib
import hmac
import math
import time

QR_PERIOD_SECONDS = 60


def _code_for_counter(secret: str, counter: int) -> str:
    msg = str(counter).encode()
    digest = hmac.new(secret.encode(), msg, hashlib.sha256).digest()
    # اشتقاق 6 أرقام
    offset = digest[-1] & 0x0F
    binary = ((digest[offset] & 0x7F) << 24
              | (digest[offset + 1] & 0xFF) << 16
              | (digest[offset + 2] & 0xFF) << 8
              | (digest[offset + 3] & 0xFF))
    return f"{binary % 1_000_000:06d}"


def current_code(secret: str, at: float | None = None) -> str:
    counter = int((at or time.time()) // QR_PERIOD_SECONDS)
    return _code_for_counter(secret, counter)


def verify_code(secret: str, code: str, at: float | None = None, window: int = 1) -> bool:
    counter = int((at or time.time()) // QR_PERIOD_SECONDS)
    for delta in range(-window, window + 1):
        if hmac.compare_digest(_code_for_counter(secret, counter + delta), str(code).strip()):
            return True
    return False


def seconds_remaining(at: float | None = None) -> int:
    now = at or time.time()
    return QR_PERIOD_SECONDS - int(now % QR_PERIOD_SECONDS)


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """المسافة بالأمتار بين نقطتين (لتحقّق الـ Geofence)."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
