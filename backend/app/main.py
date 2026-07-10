# -*- coding: utf-8 -*-
"""نقطة الدخول لتطبيق FastAPI — يجمع كل الموديولات ويضبط CORS والملفات والمجدول."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import DEFAULT_SECRET_KEYS, settings
from .database import init_db
from .routers import (
    archive,
    attendance,
    auth,
    companies,
    dashboard,
    documents,
    employees,
    eos,
    kiosk,
    audit as audit_router,
    notification_settings,
    operations,
    org,
    payroll as payroll_router,
    pro,
    reports,
    search,
    renewals,
    requests as requests_router,
    selfservice,
    tasks,
    templates,
    users,
    verify,
)


import logging  # noqa: E402

logger = logging.getLogger("hrms")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # أمان: مفتاح JWT الافتراضي يجب تغييره قبل أي نشر حقيقي — نرفض الإقلاع كليًا في
    # بيئة تبدو إنتاجية (قاعدة بيانات حقيقية لا SQLite)، ونكتفي بتحذير في التطوير المحلي.
    if settings.secret_key in DEFAULT_SECRET_KEYS:
        if settings.is_production:
            raise RuntimeError(
                "SECRET_KEY افتراضي وغير آمن في بيئة إنتاج (DATABASE_URL يشير لقاعدة بيانات "
                "حقيقية). اضبط SECRET_KEY بقيمة عشوائية طويلة في .env قبل التشغيل."
            )
        logger.warning("⚠ SECRET_KEY افتراضي — غيّره في .env قبل الإنتاج!")
    # إنشاء الجداول للتطوير (في الإنتاج تُدار عبر Alembic)
    init_db()
    os.makedirs(settings.upload_dir, exist_ok=True)

    from .channels import configure_from_settings
    configure_from_settings(settings)
    scheduler = None
    if settings.scheduler_enabled:
        from .scheduler import shutdown_scheduler, start_scheduler
        scheduler = start_scheduler()
    yield
    if scheduler:
        from .scheduler import shutdown_scheduler
        shutdown_scheduler()


app = FastAPI(
    title="نظام إدارة الموارد البشرية متعدد الشركات — الكويت",
    description="نظام ERP لإدارة الموارد البشرية مع عزل تام بين الشركات (Multi-Tenancy).",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ملاحظة أمنية: لا نكشف مجلد uploads كملفات عامة (يحوي سيلفي ومستندات حسّاسة).
# تنزيل أي ملف يمرّ عبر نقطة موثّقة تتحقق من العزل والصلاحية.
os.makedirs(settings.upload_dir, exist_ok=True)

for r in (auth, companies, users, employees, org, attendance, kiosk, documents, tasks,
          requests_router, templates, payroll_router, reports, pro, archive, search,
          operations, audit_router, eos, dashboard, selfservice, renewals, notification_settings,
          verify):
    app.include_router(r.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "hrms-kuwait"}


# ---------------------------------------------------------------------------
# تقديم الواجهة الأمامية المبنية (frontend/dist) من نفس الخادم — بلا بروكسي.
# يُفعَّل تلقائيًا متى وُجد مجلد dist (بعد `npm run build`).
# ---------------------------------------------------------------------------
from pathlib import Path  # noqa: E402

from fastapi import HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND_DIST.is_dir():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    _DIST_ROOT = FRONTEND_DIST.resolve()
    _RESERVED = ("api", "uploads", "docs", "redoc", "openapi.json")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # لا تبتلع مسارات الـ API أو التوثيق
        if full_path.startswith(_RESERVED):
            raise HTTPException(status_code=404, detail="غير موجود")
        # منع Path Traversal: المسار الناتج يجب أن يبقى داخل مجلد dist
        target = (FRONTEND_DIST / full_path).resolve()
        if full_path and (target == _DIST_ROOT or _DIST_ROOT in target.parents) and target.is_file():
            return FileResponse(str(target))
        # مسارات الـ SPA كلها ترجع index.html
        return FileResponse(str(_DIST_ROOT / "index.html"))
