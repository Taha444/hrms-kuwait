# -*- coding: utf-8 -*-
"""SIG-01 — إدارة التوقيع الرقمي للمستخدم.

كل مستخدم (خاصة الموظفين) يرفع صورة توقيعه (PNG/JPG) عبر بروفايله. يخزّنها النظام
داخل uploads/signatures/ ويحقنها في كل PDF رسمي منسوب إليه (شهادات، إنذارات،
إخلاء طرف...). الموظف يقدر يستبدل توقيعه في أي وقت — النسخة الجديدة تُستخدم
لأي مستند يُولَّد بعدها، بينما المستندات القديمة تحتفظ بالتوقيع الأصلي كما هو.

الحدود الأمنية:
- المستخدم يرفع/يعرض/يحذف توقيع نفسه فقط (لا يمس توقيع مستخدم آخر)
- HR/super_admin يستطيعون العرض للتحقق، لكن ليس الاستبدال
- حجم أقصى 500KB، امتدادات: png/jpg/jpeg فقط
- الملف يُخزّن باسم عشوائي غير قابل للتخمين، ولا يُكشف مساره في الاستجابة
"""
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from .. import models
from ..config import settings
from ..database import get_db
from ..deps import audit, get_current_user
from ..safe_files import read_limited, unique_path
from sqlalchemy.orm import Session

router = APIRouter(prefix="/me/signature", tags=["signature"])

_ALLOWED_MIME = {"image/png", "image/jpeg", "image/jpg"}
_ALLOWED_EXT = {".png", ".jpg", ".jpeg"}
_MAX_BYTES = 500 * 1024  # 500 KB — كافٍ لصورة توقيع بجودة عالية


def _signatures_folder() -> str:
    return os.path.join(settings.upload_dir, "signatures")


@router.get("")
def get_my_signature_info(user: models.User = Depends(get_current_user)):
    """يعرض بيانات التوقيع الحالي (بدون الصورة نفسها) — تُنزَّل عبر /image."""
    return {
        "has_signature": bool(user.signature_path and os.path.exists(user.signature_path)),
        "updated_at": user.signature_updated_at,
    }


@router.get("/image")
def get_my_signature_image(user: models.User = Depends(get_current_user)):
    """ينزّل صورة التوقيع الحالية للمستخدم — للعرض في بروفايله كمعاينة."""
    if not user.signature_path or not os.path.exists(user.signature_path):
        raise HTTPException(status_code=404, detail="لا يوجد توقيع محفوظ")
    ext = os.path.splitext(user.signature_path)[1].lower()
    media = "image/png" if ext == ".png" else "image/jpeg"
    return FileResponse(user.signature_path, media_type=media)


@router.post("", status_code=201)
async def upload_my_signature(request: Request, file: UploadFile = File(...),
                              user: models.User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    """يرفع أو يستبدل توقيع المستخدم (PNG/JPG، ≤500KB)."""
    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(status_code=415, detail="نوع الملف يجب أن يكون PNG أو JPG فقط")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=415, detail="امتداد الملف يجب أن يكون .png أو .jpg")
    data = await read_limited(file, max_bytes=_MAX_BYTES)
    if not data:
        raise HTTPException(status_code=400, detail="الملف فارغ")

    folder = _signatures_folder()
    path = unique_path(folder, f"user_{user.id}{ext}", prefix=f"sig_u{user.id}_")
    with open(path, "wb") as f:
        f.write(data)

    # حذف التوقيع القديم (لو موجود) — نحتفظ بالجديد فقط لتقليل تراكم الملفات
    old = user.signature_path
    user.signature_path = path
    user.signature_updated_at = datetime.now(timezone.utc)
    audit(db, user, "signature_upload", "user", user.id,
          detail=f"{len(data)} bytes {ext}", request=request)
    db.commit()
    if old and os.path.exists(old) and old != path:
        try:
            os.remove(old)
        except OSError:
            pass  # ملف قديم فُقد — لا يوقف العملية
    return {"ok": True, "updated_at": user.signature_updated_at,
            "size_bytes": len(data)}


@router.delete("")
def delete_my_signature(request: Request,
                        user: models.User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """يحذف التوقيع الحالي — المستندات المستقبلية تعود لسطر توقيع فارغ."""
    if not user.signature_path:
        raise HTTPException(status_code=404, detail="لا يوجد توقيع محفوظ")
    old = user.signature_path
    user.signature_path = None
    user.signature_updated_at = datetime.now(timezone.utc)
    audit(db, user, "signature_delete", "user", user.id, request=request)
    db.commit()
    if old and os.path.exists(old):
        try:
            os.remove(old)
        except OSError:
            pass
    return {"ok": True}
