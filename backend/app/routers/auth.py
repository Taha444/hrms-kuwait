# -*- coding: utf-8 -*-
"""المصادقة: دخول بالرقم المدني، تجديد الرمز، تغيير كلمة المرور، إعادة التعيين."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import audit, get_current_user, get_user_perms, require_perm
from ..permissions import effective_permissions
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILED = 5
LOCK_MINUTES = 15

# تحديد معدّل بسيط في الذاكرة لمنع القوة الغاشمة على الدخول (لكل IP)
_RATE_WINDOW = 60          # ثانية
_RATE_MAX = 10             # محاولات كحدّ أقصى في النافذة
_login_hits: dict[str, list[float]] = {}


def _rate_limit(ip: str):
    import time

    from ..config import settings
    if not settings.rate_limit_enabled:
        return
    now = time.time()
    hits = [t for t in _login_hits.get(ip, []) if now - t < _RATE_WINDOW]
    if len(hits) >= _RATE_MAX:
        raise HTTPException(status_code=429, detail="محاولات كثيرة، انتظر دقيقة ثم أعد المحاولة")
    hits.append(now)
    _login_hits[ip] = hits


def _perm_list(user: models.User, db: Session) -> list[str]:
    return sorted(effective_permissions(user.role, get_user_perms(user, db)))


@router.post("/login", response_model=schemas.TokenOut)
def login(data: schemas.LoginIn, request: Request, db: Session = Depends(get_db)):
    _rate_limit(request.client.host if request.client else "?")
    user = db.scalar(select(models.User).where(models.User.civil_id == data.civil_id))
    now = datetime.now(timezone.utc)
    if not user:
        raise HTTPException(status_code=401, detail="الرقم المدني أو كلمة المرور غير صحيحة")

    if user.locked_until and user.locked_until.replace(tzinfo=timezone.utc) > now:
        raise HTTPException(status_code=423, detail="الحساب مقفل مؤقتًا، حاول لاحقًا")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="الحساب غير مفعّل")

    if not verify_password(data.password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED:
            user.locked_until = now + timedelta(minutes=LOCK_MINUTES)
            user.failed_attempts = 0
        db.commit()
        raise HTTPException(status_code=401, detail="الرقم المدني أو كلمة المرور غير صحيحة")

    user.failed_attempts = 0
    user.locked_until = None
    user.last_login = now
    audit(db, user, "login", "user", user.id, request=request)
    db.commit()

    return schemas.TokenOut(
        access_token=create_access_token(user.id, user.role, user.company_id),
        refresh_token=create_refresh_token(user.id),
        must_change_password=user.must_change_password,
        role=user.role, full_name=user.full_name, company_id=user.company_id,
        permissions=_perm_list(user, db),
    )


@router.post("/refresh", response_model=schemas.TokenOut)
def refresh(data: schemas.RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError
        user = db.get(models.User, int(payload["sub"]))
    except Exception:
        raise HTTPException(status_code=401, detail="رمز التجديد غير صالح")
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="رمز التجديد غير صالح")
    return schemas.TokenOut(
        access_token=create_access_token(user.id, user.role, user.company_id),
        refresh_token=create_refresh_token(user.id),
        must_change_password=user.must_change_password,
        role=user.role, full_name=user.full_name, company_id=user.company_id,
        permissions=_perm_list(user, db),
    )


@router.get("/me")
def me(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from ..permissions import CROSS_COMPANY_ROLES

    return {
        "id": user.id, "civil_id": user.civil_id, "full_name": user.full_name,
        "role": user.role, "company_id": user.company_id, "email": user.email,
        "must_change_password": user.must_change_password,
        "employee_id": user.employee_id,
        "is_cross_company": user.role in CROSS_COMPANY_ROLES,
        "permissions": _perm_list(user, db),
    }


@router.post("/change-password")
def change_password(data: schemas.ChangePasswordIn, request: Request,
                    user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="كلمة المرور الحالية غير صحيحة")
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    audit(db, user, "change_password", "user", user.id, request=request)
    db.commit()
    return {"ok": True, "message": "تم تغيير كلمة المرور بنجاح"}


@router.post("/reset-password")
def reset_password(data: schemas.ResetPasswordIn, request: Request,
                   actor: models.User = Depends(require_perm("manage_users")),
                   db: Session = Depends(get_db)):
    from ..permissions import CROSS_COMPANY_ROLES, can_manage_role

    target = db.get(models.User, data.user_id)
    if not target:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    # العزل + التسلسل الهرمي
    if actor.role not in CROSS_COMPANY_ROLES and target.company_id != actor.company_id:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")
    if actor.id != target.id and not can_manage_role(actor.role, target.role):
        raise HTTPException(status_code=403, detail="لا يمكنك إدارة مستخدم بهذا المستوى")
    new_pw = data.new_password or settings.default_user_password
    target.password_hash = hash_password(new_pw)
    target.must_change_password = True
    target.failed_attempts = 0
    target.locked_until = None
    audit(db, actor, "reset_password", "user", target.id, request=request)
    db.commit()
    return {"ok": True, "message": "تمت إعادة تعيين كلمة المرور", "temporary_password": new_pw}
