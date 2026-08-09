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
    # ملاحظة: seed.run() مسح جدول audit_log — ندخل سجل جديد بعد الـcommit
    from ..database import SessionLocal
    with SessionLocal() as db2:
        audit(db2, user, "reset_demo_data", entity_type="system",
              request=request, after={"duration_seconds": duration})
        db2.commit()

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


@router.get("/db-status")
def db_status(user: models.User = Depends(require_super_admin)):
    """R9 §15 — تشخيص DB: عدّاد الجداول الأساسية + آخر migration + orphans.
    مفيد لتشخيص "الطلبات فاضية / القوالب فاضية" بدون SQL مباشر."""
    from sqlalchemy import func, select, text
    from ..database import SessionLocal

    counts: dict = {}
    last_rev: str | None = None
    orphan_users: int = 0
    with SessionLocal() as db:
        for model, name in [
            (models.User, "users"),
            (models.Employee, "employees"),
            (models.Company, "companies"),
            (models.Branch, "branches"),
            (models.RequestType, "request_types"),
            (models.DocumentTemplate, "document_templates"),
            (models.Request, "requests"),
            (models.Document, "documents"),
            (models.NotificationTemplate, "notification_templates"),
            (models.GovernmentPortal, "government_portals"),
        ]:
            try:
                counts[name] = db.scalar(select(func.count()).select_from(model))
            except Exception as e:
                counts[name] = f"ERROR: {str(e)[:80]}"

        try:
            row = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
            last_rev = row[0] if row else None
        except Exception as e:
            last_rev = f"ERROR: {str(e)[:80]}"

        try:
            orphan_users = db.scalar(select(func.count()).select_from(models.User).where(
                models.User.employee_id.is_(None),
                models.User.role.notin_(("super_admin", "company_owner")),
                models.User.is_active == True,  # noqa: E712
            )) or 0
        except Exception:
            orphan_users = -1

    return {
        "counts": counts,
        "last_alembic_revision": last_rev,
        "orphan_users_needing_link": orphan_users,
        "environment": "production" if settings.is_production else "development",
    }


@router.post("/ensure-catalog")
def ensure_catalog(request: Request,
                  user: models.User = Depends(require_super_admin)):
    """R9 §15 — تشغيل يدوي لحقن request types + templates الافتراضية.
    نفس المنطق اللي يشتغل في bootstrap على كل startup. idempotent."""
    from ..catalog_seed import ensure_default_catalog
    from ..database import SessionLocal
    with SessionLocal() as db:
        report = ensure_default_catalog(db)
        audit(db, user, "ensure_catalog", entity_type="system", request=request,
              after=report)
        db.commit()
    return report
