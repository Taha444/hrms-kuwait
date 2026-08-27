# -*- coding: utf-8 -*-
"""مخزن المستندات — مصدر واحد لكل كتابة وقراءة على التخزين.

**AWS-01.** كان كل موضع يكتب على القرص بنفسه: ثلاثة عشر موضع كتابة وثلاثون
موضع قراءة، كلٌّ يفتح ``open(path, "wb")`` ويبني مساره بيده. ومجلد على قرص
الخادم يعني ثلاثة أشياء:

- إعادة نشر أو استبدال الـinstance تمحو كل المستندات؛
- مع أكثر من نسخة، الملف مرفوع على واحدة والباقي لا تراه؛
- لا نسخ احتياطي مستقل عن الخادم.

والنظام يحمل جوازات وبطاقات مدنية وعقوًدا وإقامات. ضياعها ليس عطًلا تقنيًّا.

ولهذا لا يكفي «إضافة S3»: ما دامت الكتابة موزّعة على ثلاثة عشر موضًعا،
سيبقى موضع لم يُحوَّل — وهو بالضبط الملف الذي يضيع. فالتحويل يمرّ من هنا،
ومن هنا وحده.

**المفتاح لا المسار.** ما يُحفظ في القاعدة مفتاح نسبيّ (``archive/ab12_x.pdf``)
لا مسار مطلق: المسار المطلق يربط الصفّ بقرص بعينه فينكسر عند أول نقل.
والصفوف القديمة تحمل مسارات مطلقة، فـ``_to_key`` يقبل الشكلين — التوافق
هنا لا في ثلاثين موضع نداء.
"""
from __future__ import annotations

import os
import secrets
from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse

from .config import settings
from .safe_files import safe_filename


def _to_key(value: str) -> str:
    """يحوّل ما هو محفوظ في القاعدة إلى مفتاح نسبيّ.

    يقبل المفتاح النسبيّ كما هو، ويشتقّه من المسار المطلق للصفوف القديمة.
    """
    if not value:
        return ""
    v = value.replace("\\", "/")
    root = str(Path(settings.upload_dir).resolve()).replace("\\", "/")
    resolved = str(Path(value).resolve()).replace("\\", "/") if os.path.isabs(value) else v
    if resolved.startswith(root + "/"):
        return resolved[len(root) + 1:]
    if os.path.isabs(v):
        # مسار مطلق خارج مجلد الرفع — صفّ قديم من بيئة أخرى. يُعاد كما هو
        # ليعمل محليًّا، وتُبلِّغ عنه أداة الترحيل بدل أن يُبتلع بصمت.
        return v
    return v.lstrip("/")


def _new_key(folder: str, original_name: str | None, prefix: str = "") -> str:
    """مفتاح جديد فريد. الاسم يُنقّى في مكان واحد لكلا الواجهتين."""
    return (f"{folder.strip('/')}/{prefix}{secrets.token_hex(6)}"
            f"_{safe_filename(original_name)}")


class Storage(ABC):
    """الواجهة التي تراها بقيّة الشيفرة. لا تعرف أين يقع الملف فعًلا."""

    @abstractmethod
    def save(self, data: bytes, folder: str, original_name: str | None,
             prefix: str = "") -> str:
        """يحفظ ويعيد **المفتاح** الذي يُخزَّن في القاعدة."""

    @abstractmethod
    def save_at(self, data: bytes, key: str) -> str:
        """يحفظ على مفتاح محدَّد سلًفا.

        بعض المخرجات اسمها جزء من هويّتها — ملف الصيغة يحمل رقمها المرجعي
        ليُتتبَّع. فلا يصلح لها مفتاح عشوائي، ويُقبل الاستبدال عمًدا: إعادة
        توليد الصيغة نفسها تكتب فوق نسختها لا تُنشئ يتيمة ثانية.
        """

    @abstractmethod
    def read(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> bool: ...

    @abstractmethod
    def response(self, key: str, filename: str | None = None,
                 media_type: str | None = None) -> Response:
        """ردّ HTTP يخدم الملف.

        يمرّ عبر الخادم عمًدا ولا يُعطى العميل رابط تخزين مباشر: الرابط
        المباشر يتجاوز فحص الصلاحيات ويبقى صالًحا بعد سحبها.
        """


class LocalStorage(Storage):
    """قرص الخادم — السلوك القائم، ويبقى الافتراضي للتطوير."""

    def _abs(self, key: str) -> Path:
        k = _to_key(key)
        if os.path.isabs(k):
            return Path(k)
        target = (Path(settings.upload_dir) / k).resolve()
        root = Path(settings.upload_dir).resolve()
        if root != target and root not in target.parents:
            raise HTTPException(status_code=400, detail="مسار ملف غير صالح")
        return target

    def save(self, data: bytes, folder: str, original_name: str | None,
             prefix: str = "") -> str:
        key = _new_key(folder, original_name, prefix)
        path = self._abs(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return key

    def save_at(self, data: bytes, key: str) -> str:
        path = self._abs(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return _to_key(key)

    def read(self, key: str) -> bytes:
        p = self._abs(key)
        if not p.exists():
            raise HTTPException(status_code=404, detail="الملف غير موجود")
        return p.read_bytes()

    def exists(self, key: str) -> bool:
        try:
            return self._abs(key).exists()
        except HTTPException:
            return False

    def delete(self, key: str) -> bool:
        p = self._abs(key)
        if p.exists():
            p.unlink()
            return True
        return False

    def response(self, key: str, filename: str | None = None,
                 media_type: str | None = None) -> Response:
        p = self._abs(key)
        if not p.exists():
            raise HTTPException(status_code=404, detail="الملف غير موجود")
        return FileResponse(str(p), filename=filename or p.name,
                            media_type=media_type)


class S3Storage(Storage):
    """S3 عبر IAM role على الـEC2 — لا مفاتيح مكتوبة في ملف.

    الاعتماد متروك لسلسلة boto3 الافتراضية: تقرأ الـrole تلقائيًّا. وأي
    مفتاح يُكتب في ``.env`` هو مفتاح يُسرَّب مع نسخة احتياطية أو سجلّ.
    """

    def __init__(self) -> None:
        import boto3                                   # يُستورد عند الحاجة فقط

        self._bucket = settings.s3_bucket
        self._prefix = (settings.s3_prefix or "").strip("/")
        if not self._bucket:
            raise RuntimeError("STORAGE_BACKEND=s3 بلا S3_BUCKET")
        self._c = boto3.client("s3", region_name=settings.s3_region or None)

    def _k(self, key: str) -> str:
        k = _to_key(key)
        return f"{self._prefix}/{k}" if self._prefix else k

    def save(self, data: bytes, folder: str, original_name: str | None,
             prefix: str = "") -> str:
        key = _new_key(folder, original_name, prefix)
        self._c.put_object(Bucket=self._bucket, Key=self._k(key), Body=data,
                           ServerSideEncryption="AES256")
        return key

    def save_at(self, data: bytes, key: str) -> str:
        self._c.put_object(Bucket=self._bucket, Key=self._k(key), Body=data,
                           ServerSideEncryption="AES256")
        return _to_key(key)

    def read(self, key: str) -> bytes:
        from botocore.exceptions import ClientError

        try:
            return self._c.get_object(Bucket=self._bucket,
                                      Key=self._k(key))["Body"].read()
        except ClientError:
            raise HTTPException(status_code=404, detail="الملف غير موجود")

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._c.head_object(Bucket=self._bucket, Key=self._k(key))
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> bool:
        self._c.delete_object(Bucket=self._bucket, Key=self._k(key))
        return True

    def response(self, key: str, filename: str | None = None,
                 media_type: str | None = None) -> Response:
        import io

        data = self.read(key)
        name = filename or os.path.basename(_to_key(key))
        return StreamingResponse(
            io.BytesIO(data),
            media_type=media_type or "application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )


_backend: Storage | None = None


def get_storage() -> Storage:
    global _backend
    if _backend is None:
        _backend = (S3Storage() if (settings.storage_backend or "local").lower() == "s3"
                    else LocalStorage())
    return _backend


def reset_storage() -> None:
    """للاختبارات وحدها — يُعيد اختيار الواجهة بعد تغيير الإعداد."""
    global _backend
    _backend = None


# ---- اختصارات: بقيّة الشيفرة تناديها لا الأصناف مباشرة ----
def save_bytes(data: bytes, folder: str, original_name: str | None,
               prefix: str = "") -> str:
    return get_storage().save(data, folder, original_name, prefix)


def save_at_key(data: bytes, key: str) -> str:
    return get_storage().save_at(data, key)


def read_bytes(key: str) -> bytes:
    return get_storage().read(key)


def file_response(key: str, filename: str | None = None,
                  media_type: str | None = None) -> Response:
    return get_storage().response(key, filename, media_type)


def delete_key(key: str) -> bool:
    return get_storage().delete(key)


def key_exists(key: str) -> bool:
    return get_storage().exists(key)
