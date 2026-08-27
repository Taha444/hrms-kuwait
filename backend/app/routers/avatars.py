# -*- coding: utf-8 -*-
"""R9 §17 — Profile avatars.

كل مستخدم يقدر يرفع صورته الشخصية (avatar). تظهر في TopBar وأي مكان بيعرض
اسم المستخدم. الاستبدال مباشر (بدون approval workflow — مش توقيع رسمي).

Endpoints:
- GET  /me/avatar          → بيانات (has_avatar, updated_at)
- GET  /me/avatar/image    → الصورة نفسها (لعرضها في UI)
- GET  /users/{id}/avatar/image → صورة مستخدم آخر (لعرضها في قوائم)
- POST /me/avatar          → رفع/استبدال
- DELETE /me/avatar        → حذف (رجوع للأيقونة الافتراضية)

قيود:
- PNG/JPG/WEBP ≤ 2 MB
- الملف يُخزَّن في uploads/avatars/user_<id>.<ext>
- Content-Type يُحسم من امتداد الملف الأصلي
"""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db
from ..deps import audit, get_current_user
from ..safe_files import read_limited, unique_path
from ..storage import delete_key, file_response, key_exists, save_bytes


router = APIRouter(tags=["avatars"])

_MAX_BYTES = 2 * 1024 * 1024  # 2 MB
_ALLOWED_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
_ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp"}
_MIME_BY_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".webp": "image/webp"}


def _avatars_folder() -> str:
    folder = os.path.join(settings.upload_dir, "avatars")
    os.makedirs(folder, exist_ok=True)
    return folder


@router.get("/me/avatar")
def my_avatar_status(user: models.User = Depends(get_current_user)):
    """يعيد حالة صورة المستخدم الحالي (بدون بيانات الصورة نفسها)."""
    has = bool(user.avatar_path and key_exists(user.avatar_path))
    return {
        "has_avatar": has,
        "updated_at": user.avatar_updated_at.isoformat() if user.avatar_updated_at else None,
    }


@router.get("/me/avatar/image")
def my_avatar_image(user: models.User = Depends(get_current_user)):
    """يرد الصورة الفعلية للمستخدم الحالي."""
    if not user.avatar_path or not key_exists(user.avatar_path):
        raise HTTPException(status_code=404, detail="لا توجد صورة بروفايل")
    ext = os.path.splitext(user.avatar_path)[1].lower()
    mime = _MIME_BY_EXT.get(ext, "application/octet-stream")
    return file_response(user.avatar_path, media_type=mime)


@router.get("/users/{user_id}/avatar/image")
def user_avatar_image(user_id: int,
                     user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """يرد صورة مستخدم آخر — أي مسجّل دخول يقدر يشوفها (لعرضها في قوائم/سلاسل اعتماد)."""
    target = db.get(models.User, user_id)
    if not target or not target.avatar_path or not key_exists(target.avatar_path):
        raise HTTPException(status_code=404, detail="لا توجد صورة بروفايل")
    ext = os.path.splitext(target.avatar_path)[1].lower()
    mime = _MIME_BY_EXT.get(ext, "application/octet-stream")
    return file_response(target.avatar_path, media_type=mime)


@router.post("/me/avatar")
async def upload_my_avatar(request: Request,
                          file: UploadFile = File(...),
                          user: models.User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """R9 §17 — يرفع/يستبدل صورة المستخدم الحالي.
    - PNG/JPG/WEBP فقط
    - حد أقصى 2 MB
    - الصورة القديمة تُحذف من القرص بعد نجاح الرفع
    """
    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(status_code=415,
                          detail="نوع الملف يجب أن يكون PNG أو JPG أو WEBP فقط")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=415,
                          detail="امتداد الملف يجب أن يكون .png أو .jpg أو .webp")

    data = await read_limited(file, max_bytes=_MAX_BYTES)
    if not data:
        raise HTTPException(status_code=400, detail="الملف فارغ")

    # AWS-01 — عبر طبقة التخزين لا على القرص مباشرة
    path = save_bytes(data, "avatars", f"user_{user.id}{ext}",
                      prefix=f"av_u{user.id}_")

    old = user.avatar_path
    user.avatar_path = path
    user.avatar_updated_at = datetime.now(timezone.utc)
    audit(db, user, "avatar_upload", "user", user.id,
          detail=f"{len(data)}B ({file.content_type})", request=request)
    db.commit()

    # امسح الملف القديم بعد نجاح الحفظ
    if old and old != path and key_exists(old):
        try:
            delete_key(old)
        except OSError:
            pass

    return {"ok": True, "updated_at": user.avatar_updated_at.isoformat(),
            "size_bytes": len(data)}


@router.delete("/me/avatar")
def delete_my_avatar(request: Request,
                    user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """R9 §17 — يمسح صورة البروفايل (رجوع للأيقونة الافتراضية)."""
    if not user.avatar_path:
        return {"ok": True, "note": "لم تكن هناك صورة"}
    old = user.avatar_path
    user.avatar_path = None
    user.avatar_updated_at = None
    audit(db, user, "avatar_delete", "user", user.id, request=request)
    db.commit()
    if old and key_exists(old):
        try:
            delete_key(old)
        except OSError:
            pass
    return {"ok": True}
