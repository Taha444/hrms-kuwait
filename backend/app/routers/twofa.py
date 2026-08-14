# -*- coding: utf-8 -*-
"""V2.2 §9 — TOTP-based 2FA للأدوار الحساسة (super_admin/company_owner/hr/accountant).

نقاط النهاية:
- POST /api/2fa/enroll   — يبدأ التسجيل: يُنشئ secret + otpauth URI + QR PNG
- POST /api/2fa/confirm  — يؤكد الـ TOTP بأول رمز صحيح (يفعّل 2FA)
- POST /api/2fa/verify   — يتحقق من الرمز (يُستدعى بعد login للأدوار التي تستوجب 2FA)
- POST /api/2fa/disable  — يعطل 2FA (يحتاج كلمة السر الحالية)

القاعدة:
- الأدوار الحساسة (SENSITIVE_ROLES) يجب أن تسجّل قبل تنفيذ عمليات كتابة
- عدم إجبار الأدوار العادية على 2FA (خيار)
- الرمز 6 خانات، صالح 30 ثانية، يُقبل ±1 كنافذة زمنية (drift)
"""
import base64
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..deps import audit, get_current_user
from ..security import verify_password

router = APIRouter(prefix="/2fa", tags=["2fa"])

SENSITIVE_ROLES = {"super_admin", "company_owner", "company_manager", "hr", "accountant"}
ISSUER = "HRMS-Kuwait"


class VerifyIn(BaseModel):
    code: str


class DisableIn(BaseModel):
    password: str


def _new_secret() -> str:
    """يُنشئ secret عشوائي 20 بايت base32."""
    import os
    return base64.b32encode(os.urandom(20)).decode("ascii").rstrip("=")


def _verify_code(secret: str, code: str, valid_window: int | None = None) -> bool:
    """يتحقق من رمز TOTP مع نافذة ±valid_window * 30s.

    QA-22 — النافذة صارت قابلة للضبط من البيئة (TOTP_VALID_WINDOW).
    السبب: ساعة الخادم وُجدت متأخرة ~111 ثانية، فرُفضت رموز صحيحة تماًما —
    TOTP يقارن بالوقت لا بالسر، فانحراف الساعة يُبطل النظام كله بلا أي خطأ
    ظاهر في الكود، وهو ما جعل التشخيص عسًيرا.

    الحل الصحيح ضبط ساعة الخادم (NTP)؛ وهذا المتغيّر مخرج طوارئ حين لا تملك
    التحكم فيها. توسيعه يوسّع نافذة إعادة استخدام الرمز، فلا تزده فوق اللازم:
    4 ≈ ±2 دقيقة.
    """
    import os

    import pyotp
    if valid_window is None:
        try:
            valid_window = int(os.environ.get("TOTP_VALID_WINDOW", "1"))
        except ValueError:
            valid_window = 1
    if not (code and code.strip().isdigit() and len(code.strip()) == 6):
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(code.strip(), valid_window=valid_window)


def clock_skew_seconds() -> float | None:
    """انحراف ساعة الخادم عن مصدر خارجي — تشخيص لا تصحيح.

    يُعرَض في /2fa/status ليظهر السبب مباشرة بدل اكتشافه بالتجربة والخطأ.
    """
    import email.utils
    import time
    import urllib.request
    try:
        with urllib.request.urlopen("https://www.google.com", timeout=3) as r:
            served = r.headers.get("Date")
        if not served:
            return None
        return round(time.time() - email.utils.parsedate_to_datetime(served).timestamp(), 1)
    except Exception:  # noqa: BLE001 — التشخيص لا يجب أن يُسقط شيًئا
        return None


@router.post("/enroll")
def enroll(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """يبدأ التسجيل: ينشئ secret + otpauth URI + QR PNG (base64)."""
    if user.totp_confirmed:
        raise HTTPException(status_code=409, detail="2FA مفعّل بالفعل — عطّله أولاً لإعادة التسجيل")
    import pyotp
    import qrcode
    if not user.totp_secret:
        user.totp_secret = _new_secret()
        db.commit()
    label = f"{user.civil_id}@{ISSUER}"
    uri = pyotp.TOTP(user.totp_secret).provisioning_uri(name=label, issuer_name=ISSUER)
    buf = io.BytesIO()
    qrcode.make(uri).save(buf, format="PNG")
    png_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return {
        "secret": user.totp_secret,  # للإدخال اليدوي في التطبيق
        "uri": uri,
        "qr_png_base64": png_b64,
        "issuer": ISSUER,
    }


@router.post("/confirm")
def confirm(data: VerifyIn, request: Request,
            user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """يؤكد الـ TOTP بأول رمز صحيح — يفعّل 2FA للحساب."""
    if not user.totp_secret:
        raise HTTPException(status_code=400, detail="ابدأ التسجيل عبر /2fa/enroll أولاً")
    if user.totp_confirmed:
        return {"ok": True, "already_confirmed": True}
    if not _verify_code(user.totp_secret, data.code):
        raise HTTPException(status_code=400, detail="الرمز غير صالح أو انتهت صلاحيته")
    user.totp_confirmed = True
    user.totp_last_used_at = datetime.now(timezone.utc)
    audit(db, user, "totp_enable", "user", user.id, request=request)
    db.commit()
    return {"ok": True, "confirmed": True}


@router.post("/verify")
def verify(data: VerifyIn, request: Request,
           user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """يتحقق من رمز TOTP — يُستخدم بعد login للأدوار الحساسة."""
    if not (user.totp_secret and user.totp_confirmed):
        raise HTTPException(status_code=400, detail="2FA غير مفعّل لحسابك")
    if not _verify_code(user.totp_secret, data.code):
        audit(db, user, "totp_fail", "user", user.id, request=request)
        db.commit()
        raise HTTPException(status_code=400, detail="الرمز غير صالح")
    user.totp_last_used_at = datetime.now(timezone.utc)
    audit(db, user, "totp_verify", "user", user.id, request=request)
    db.commit()
    return {"ok": True}


@router.post("/disable")
def disable(data: DisableIn, request: Request,
            user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """يعطل 2FA (يحتاج كلمة السر الحالية للتأكيد)."""
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=400, detail="كلمة المرور غير صحيحة")
    if not user.totp_confirmed:
        return {"ok": True, "already_disabled": True}
    user.totp_secret = None
    user.totp_confirmed = False
    audit(db, user, "totp_disable", "user", user.id, request=request)
    db.commit()
    return {"ok": True, "disabled": True}


@router.get("/status")
def status(user: models.User = Depends(get_current_user)):
    """حالة 2FA الحالية للمستخدم — للواجهة تعرف تعرض أزرار الإعداد."""
    from ..permissions import ROLE_LABEL_AR
    return {
        "enabled": bool(user.totp_confirmed),
        "sensitive_role": user.role in SENSITIVE_ROLES,
        "last_used_at": user.totp_last_used_at.isoformat() if user.totp_last_used_at else None,
        # R6-D §4 — تسمية دور المستخدم عشان الواجهة تعرض نصًا مخصّصًا بدل عام
        "role": user.role,
        "role_label_ar": ROLE_LABEL_AR.get(user.role, user.role),
    }
