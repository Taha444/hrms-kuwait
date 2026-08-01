# -*- coding: utf-8 -*-
"""نقاط إدارية للعرض التوضيحي: إعادة تعيين البيانات، معلومات النظام.

كل النقاط هنا محميّة بـsuper_admin + متغيّر بيئة صريح `ALLOW_DEMO_RESET`
عشان يستحيل تشغيلها بالغلط على قاعدة إنتاج حقيقية.
"""
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from .. import models
from ..config import settings
from ..deps import audit, require_super_admin

router = APIRouter(prefix="/admin", tags=["admin"])


def _reset_allowed() -> bool:
    """إعادة التعيين مسموحة تلقائيًا في التطوير (SQLite)، وتحتاج تصريح صريح في الإنتاج."""
    if not settings.is_production:
        return True
    return os.environ.get("ALLOW_DEMO_RESET", "").lower() in ("1", "true", "yes")


@router.get("/reset-status")
def reset_status(user: models.User = Depends(require_super_admin)):
    """يخبر الواجهة هل زر Reset مسموح — عشان تُخفيه لو غير متاح."""
    return {
        "allowed": _reset_allowed(),
        "environment": "production" if settings.is_production else "development",
        "reason": None if _reset_allowed()
                  else "متغيّر ALLOW_DEMO_RESET غير مضبوط على true في بيئة الإنتاج",
    }


@router.post("/reset-demo-data")
def reset_demo_data(request: Request,
                    user: models.User = Depends(require_super_admin)):
    """يمسح كل البيانات ويعيد تعبئة seed الديمو (super_admin + owner + شركات + موظفين + طلبات).
    مفيد جدًا قبل بداية عرض توضيحي جديد بعد ما يعبث المستخدمون بالبيانات."""
    if not _reset_allowed():
        raise HTTPException(status_code=403, detail=(
            "إعادة التعيين محظورة في هذه البيئة. "
            "اضبط ALLOW_DEMO_RESET=true للسماح صراحةً."
        ))

    started = datetime.utcnow()
    # نستدعي seed.run() اللي بيمسح كل الجداول ثم يعيد التعبئة
    from .. import seed
    # نضمن إن ALLOW_DEMO_SEED مفعّل خلال هذا الاستدعاء (seed يرفض بدونه على prod)
    prev = os.environ.get("ALLOW_DEMO_SEED")
    try:
        os.environ["ALLOW_DEMO_SEED"] = "true"
        seed.run()
    finally:
        if prev is None:
            os.environ.pop("ALLOW_DEMO_SEED", None)
        else:
            os.environ["ALLOW_DEMO_SEED"] = prev

    duration = (datetime.utcnow() - started).total_seconds()
    # تسجيل تدقيقي حسّاس — بس audit جدول اتمسح، فنكتب سطر جديد بعد الـseed
    audit(request, user, "reset_demo_data", entity_type="system",
          details_json={"duration_seconds": duration})

    return {
        "status": "ok",
        "duration_seconds": round(duration, 2),
        "note": "تمت إعادة التعيين — سجّل خروجًا وادخل بحساب seed جديد.",
    }


@router.get("/system-info")
def system_info(user: models.User = Depends(require_super_admin)):
    """معلومات موجزة عن البيئة للعرض في لوحة الحالة."""
    return {
        "environment": "production" if settings.is_production else "development",
        "database_url_type": "postgres" if "postgres" in (settings.database_url or "") else "sqlite",
        "scheduler_enabled": settings.scheduler_enabled,
        "upload_dir": settings.upload_dir,
        "reset_allowed": _reset_allowed(),
        "server_time_utc": datetime.utcnow().isoformat() + "Z",
    }
