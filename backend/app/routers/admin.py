# -*- coding: utf-8 -*-
"""نقاط إدارية للعرض التوضيحي: إعادة تعيين البيانات، معلومات النظام.

كل النقاط هنا محميّة بـsuper_admin + متغيّر بيئة صريح `ALLOW_DEMO_RESET`
عشان يستحيل تشغيلها بالغلط على قاعدة إنتاج حقيقية.
"""
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db
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


@router.post("/break-glass")
def open_break_glass(request: Request, reason: str, minutes: int = 60,
                     user: models.User = Depends(require_super_admin),
                     db: Session = Depends(get_db)):
    """V2.2 §13.5 (AC-05) — يفتح نافذة تجاوز طارئة موقّتة.

    التجاوز يبقى ممكًنا — منعه كلًيا يشلّ النظام حين يتعطّل الإسناد (موظف بلا
    فرع، معتمِد غادر الشركة) — لكنه يصير حدًثا: سبب مكتوب، ومدة تنتهي وحدها،
    وسجل يُراجَع. نافذة مفتوحة إلى الأبد ليست تجاوًزا طارًئا بل صلاحية دائمة.
    """
    from .. import break_glass

    try:
        session = break_glass.open_session(db, user, reason, minutes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit(db, user, "break_glass_open", "user", user.id,
          detail=f"{session.reason} (ينتهي {session.expires_at:%Y-%m-%d %H:%M})",
          request=request)
    db.commit()
    return {"ok": True, "id": session.id, "reason": session.reason,
            "expires_at": session.expires_at.isoformat()}


@router.post("/break-glass/close")
def close_break_glass(request: Request,
                      user: models.User = Depends(require_super_admin),
                      db: Session = Depends(get_db)):
    """يغلق النافذة السارية فوًرا بدل انتظار انتهائها."""
    from datetime import datetime

    from .. import break_glass

    session = break_glass.active_session(db, user.id)
    if not session:
        return {"ok": True, "already_closed": True}
    session.closed_at = datetime.now()
    audit(db, user, "break_glass_close", "user", user.id,
          detail=f"استُخدمت {session.uses} مرة", request=request)
    db.commit()
    return {"ok": True, "closed": True, "uses": session.uses}


@router.get("/break-glass")
def list_break_glass(limit: int = 50,
                     user: models.User = Depends(require_super_admin),
                     db: Session = Depends(get_db)):
    """سجل النوافذ — نافذة استُخدمت عشرين مرة ليست حالة طارئة."""
    from datetime import datetime

    rows = db.scalars(select(models.BreakGlassSession).order_by(
        models.BreakGlassSession.id.desc()).limit(max(1, min(limit, 200)))).all()
    now = datetime.now()
    return [{"id": r.id, "user_id": r.user_id, "reason": r.reason,
             "started_at": r.started_at, "expires_at": r.expires_at,
             "closed_at": r.closed_at, "uses": r.uses,
             "active": r.closed_at is None and r.expires_at > now} for r in rows]
