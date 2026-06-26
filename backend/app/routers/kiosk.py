# -*- coding: utf-8 -*-
"""شاشة عرض QR للفروع (Kiosk) — نقطة عامة بلا تسجيل دخول، مُصرّحة بمفتاح الفرع فقط.

لا تكشف هذه النقطة أي بيانات أخرى — فقط رمز الـ QR الحالي للفرع.
"""
import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from ..qr_token import QR_TTL_SECONDS, make_qr_token

router = APIRouter(prefix="/kiosk", tags=["kiosk"])


@router.get("/{branch_id}/qr")
def kiosk_qr(branch_id: int, key: str = Query(...), db: Session = Depends(get_db)):
    branch = db.get(models.Branch, branch_id)
    # رسالة موحّدة + مقارنة ثابتة الزمن لتجنّب كشف الوجود/التوقيت
    if not branch or not branch.kiosk_key or not hmac.compare_digest(branch.kiosk_key, key):
        raise HTTPException(status_code=403, detail="مفتاح الشاشة غير صالح")
    token, exp = make_qr_token(branch.id)
    now = datetime.now(timezone.utc)
    return {
        "token": token,
        "branch_name": branch.name,
        "expires_at": exp.isoformat(),
        "refresh_in_seconds": QR_TTL_SECONDS,
        "server_time": now.isoformat(),
    }
