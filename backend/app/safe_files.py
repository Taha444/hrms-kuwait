# -*- coding: utf-8 -*-
"""أدوات أمان للملفات: تنقية أسماء الملفات (منع Path Traversal) وحدّ حجم الرفع."""
import os
import re
import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 ميجابايت كحدّ أقصى للرفع
_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]")
_ALLOWED_EXT = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf", ".doc", ".docx",
    ".xls", ".xlsx", ".txt", ".html", ".csv",
}


def safe_filename(name: str | None) -> str:
    """يحوّل اسم الملف إلى اسم آمن (لا مسارات، امتداد مسموح، طول محدود)."""
    base = os.path.basename(name or "")
    base = base.replace("\x00", "")
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    if ext not in _ALLOWED_EXT:
        ext = ".bin"
    stem = _SAFE_RE.sub("_", stem)[:60].strip("._") or "file"
    return f"{stem}{ext}"


def unique_path(folder: str, original_name: str | None, prefix: str = "") -> str:
    """مسار فريد وآمن داخل المجلد المحدّد (لا يخرج عنه)."""
    os.makedirs(folder, exist_ok=True)
    token = secrets.token_hex(6)
    fname = f"{prefix}{token}_{safe_filename(original_name)}"
    target = (Path(folder) / fname).resolve()
    # تأكيد بقاء المسار داخل المجلد
    if Path(folder).resolve() not in target.parents:
        raise HTTPException(status_code=400, detail="اسم ملف غير صالح")
    return str(target)


async def read_limited(file: UploadFile, max_bytes: int = MAX_UPLOAD_BYTES) -> bytes:
    """يقرأ محتوى الملف مع فرض حدّ أقصى للحجم (يمنع استنزاف الذاكرة)."""
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="حجم الملف يتجاوز الحدّ المسموح (15MB)")
    return data
