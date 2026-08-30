# -*- coding: utf-8 -*-
"""نقطة الدخول لتطبيق FastAPI — يجمع كل الموديولات ويضبط CORS والملفات والمجدول."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import DEFAULT_SECRET_KEYS, settings
from .database import init_db
from .routers import (
    admin as admin_router,
    archive,
    attendance,
    auth,
    avatars,
    portals as portals_router,
    companies,
    dashboard,
    delegations,
    documents,
    feature_flags as feature_flags_router,
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
    signatories,
    signatures,
    tasks,
    templates,
    twofa,
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


# ============================================================================
# SEC-HEADERS — ترويسات أمان لكل استجابة (يعالج فشل فحص Mozilla Observatory)
# ============================================================================
# مصفوفة الترويسات مبنية على تقرير الفحص + توصيات OWASP:
#   - HSTS: يجبر HTTPS لمدة سنة (max-age=31536000) للنطاق والفروع الفرعية
#   - X-Content-Type-Options: nosniff — يمنع browser من "تخمين" نوع المحتوى
#   - Referrer-Policy: strict-origin-when-cross-origin — يمنع تسريب URLs كاملة
#   - Permissions-Policy: تعطيل واجهات المتصفح الحساسة (payment, USB, ...)
#   - CSP: default-src 'self' + object-src 'none' + base-uri 'self' + form-action 'self'
#     — يمنع Stored/Reflected XSS، clickjacking، وحقن نماذج
#   - Cross-Origin-*-Policy: عزل مصدر الاستجابة (COOP + CORP)
# CSP لا يحوي 'unsafe-inline' في script-src — كل JS يأتي كـ bundle خارجي من Vite.
# 'unsafe-inline' في style-src لأن React styled inline attributes تحتاجها.
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    # خطوط جوجل: index.html يطلب Tajawal و IBM Plex Sans Arabic، وسياسة
    # 'self' وحدها كانت تحجبهما — فالنظام يمنع خطوطه هو. النتيجة واجهة عربية
    # بخط بديل تختلف مقاساته، وتخطيط يُحسب على خط لم يصل. المصدران محدَّدان
    # بالاسم لا بـ* — إذن لخادمَي خطوط معروفين، لا فتح للسياسة كلها.
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "connect-src 'self'; "
    "media-src 'self' blob:; "
    "worker-src 'self' blob:; "
    "manifest-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'self'; "
    "upgrade-insecure-requests"
)

_STATIC_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # قائمة سماح صريحة: نُتيح الكاميرا والموقع فقط (للحضور بـ QR والسيلفي) ونمنع الباقي
    "Permissions-Policy": (
        "camera=(self), geolocation=(self), microphone=(), payment=(), usb=(), "
        "magnetometer=(), gyroscope=(), accelerometer=(), interest-cohort=()"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "X-Frame-Options": "SAMEORIGIN",
    "Content-Security-Policy": _CSP,
}


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    for k, v in _STATIC_HEADERS.items():
        response.headers.setdefault(k, v)
    return response


# ============================================================================
# V2.2 §25 — Structured JSON logging (ops: Sentry/Datadog يقرأون JSON مباشرة)
# ============================================================================
import json as _json  # noqa: E402
import time as _time  # noqa: E402
import uuid as _uuid  # noqa: E402


@app.middleware("http")
async def structured_request_log(request, call_next):
    """يُنتج سطر JSON لكل طلب (method/path/status/duration_ms/correlation_id).
    correlation_id يمكن للعميل تمريره كـ X-Correlation-Id، وإلا نولّده."""
    corr = request.headers.get("x-correlation-id") or _uuid.uuid4().hex[:16]
    request.state.correlation_id = corr
    start = _time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = int((_time.perf_counter() - start) * 1000)
        try:
            logger.info(_json.dumps({
                "event": "http_request",
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "duration_ms": duration_ms,
                "correlation_id": corr,
                "client": (request.client.host if request.client else None),
            }, ensure_ascii=False))
        except Exception:
            pass  # logging failure لا يعرقل الاستجابة

# ملاحظة أمنية: لا نكشف مجلد uploads كملفات عامة (يحوي سيلفي ومستندات حسّاسة).
# تنزيل أي ملف يمرّ عبر نقطة موثّقة تتحقق من العزل والصلاحية.
os.makedirs(settings.upload_dir, exist_ok=True)

for r in (auth, companies, users, employees, org, attendance, kiosk, documents, tasks,
          requests_router, templates, payroll_router, reports, pro, archive, search,
          operations, audit_router, eos, dashboard, selfservice, renewals, notification_settings,
          verify, delegations, feature_flags_router, signatures, signatories, twofa,
          admin_router, portals_router, avatars):
    app.include_router(r.router, prefix="/api")
# PILOT-P0-5 — hr_router للاستبدالات المعلّقة (prefix مختلف عن /me/signature)
app.include_router(signatures.hr_router, prefix="/api")


# ---------------------------------------------------------------------------
# F-004 — معرّف رقمي خارج مدى العمود ليس عطًلا في الخادم
# ---------------------------------------------------------------------------
# **العطل**: كل مسار فيه ``/{id}`` يقبل عدًدا صحيًحا بلا حدّ — فـPydantic
# لا يحدّ نطاق ``int``. فيصل الرقم إلى مشغّل القاعدة ويتجاوز مدى العمود،
# فيرتفع ``OverflowError`` على SQLite و``DataError`` على PostgreSQL،
# ويردّ الخادم 500 غير معالَج. أي مستخدم مصادَق يُنتجه بسطر واحد.
#
# ولأن المسارات بالمئات، فالعلاج هنا لا عند كل واحد: قيد في كل توقيع
# يُنسى في المسار التالي، والمعالج يغطّي ما كُتب وما سيُكتب.
#
# و404 هو الردّ الصادق: المعرّف صالح شكًلا ولا سجلّ له — وهذا بالضبط ما
# يعنيه «غير موجود». وإخفاء الفارق عن العميل مقصود: من يجرّب أرقاًما لا
# يتعلّم من الردّ حدود الأعمدة.
_INT32_MAX = 2 ** 31 - 1


def _out_of_range_response(request: Request, exc: Exception):
    """معرّف يتجاوز مدى العمود ⇒ 404، لا 500.

    **العطل**: كل مسار فيه ``/{id}`` يقبل عدًدا صحيًحا بلا حدّ — فـPydantic
    لا يحدّ نطاق ``int``. فيصل الرقم إلى مشغّل القاعدة ويتجاوز مدى العمود،
    فيرتفع ``OverflowError`` على SQLite و``DataError`` على PostgreSQL،
    ويردّ الخادم 500 غير معالَج. أي مستخدم مصادَق يُنتجه بسطر واحد.
    ولأن المسارات بالمئات، فالعلاج مركزيّ: قيد في كل توقيع يُنسى في
    المسار التالي.

    **ولماذا معالج لنوع بعينه لا وسيط ولا معالج عامّ**:
    - الوسيط (``BaseHTTPMiddleware``) يلفّ كل طلب، فيبطئ كل نداء
      **ويعلّق الردود المتدفّقة** — جُرّب فتوقّفت المجموعة عند تنزيل ملف.
    - ومعالج ``Exception`` العامّ تتولّاه ``ServerErrorMiddleware`` وهي
      تُعيد رفعه تحت ``TestClient``، فيمرّ في الإنتاج ويسقط في الاختبار.
    والتسجيل لنوع محدَّد تتولّاه ``ExceptionMiddleware``: بلا لفّ، وبسلوك
    واحد في البيئتين.
    """
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=404, content={"detail": "السجلّ غير موجود"})


app.add_exception_handler(OverflowError, _out_of_range_response)

try:                                   # DataError = تجاوز المدى على PostgreSQL
    from sqlalchemy.exc import DataError as _DataError

    app.add_exception_handler(_DataError, _out_of_range_response)
except Exception:                      # pragma: no cover - نسخة بلا الصنف
    pass


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "hrms-kuwait"}


#: F-001 — من يرى تفصيل حالة النظام.
#:
#: **العطل**: النقطة كانت مفتوحة للجميع وتُفصح عن عدد الشركات والموظفين
#: والمستخدمين والمستندات، ومسار التخزين، ورقم ترحيل القاعدة، ووجود
#: حسابات بذرة من عدمه. أرقام عمل وبصمة بنية تحتية لمن يعرف الرابط فقط.
#:
#: **ولماذا لم تُغلق كلًّيا**: هي طريق التحقّق بعد كل نشرة، وإغلاقها يدفع
#: من يحتاجها إلى تخطّيها لا إلى تأمينها. فالمجهول يرى **حالة كل مكوّن**
#: — وهي ما يلزم للمراقبة الآلية — والتفصيل يحتاج رمًزا أو إدارة عليا.
def _health_detail_allowed(request: Request) -> bool:
    token = (getattr(settings, "health_token", "") or "").strip()
    if token:
        import hmac as _hmac
        given = (request.headers.get("x-health-token")
                 or request.query_params.get("token") or "")
        if given and _hmac.compare_digest(given, token):
            return True
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        try:
            from .security import decode_token
            payload = decode_token(auth.split(" ", 1)[1])
            return payload.get("role") == "super_admin"
        except Exception:
            return False
    return False


def _redact(results: dict) -> dict:
    """حالة كل مكوّن بلا أرقامه.

    تكفي المراقبة الآلية وتكفي التحقّق من نشرة، ولا تعطي عابًرا جرًدا
    لحجم الشركة ولا نسخة قاعدتها.
    """
    checks = {}
    for name, body in (results.get("checks") or {}).items():
        if isinstance(body, dict):
            slim = {"status": body.get("status")}
            # قيمتان لا تكشفان شيًئا ويحتاجهما من ينشر
            for keep in ("up_to_date", "can_render_pdf"):
                if keep in body:
                    slim[keep] = body[keep]
            checks[name] = slim
        else:
            checks[name] = body
    return {"service": results.get("service"), "checks": checks,
            "detail": "مختصر — للتفصيل استعمل رمز الصحّة أو حساب الإدارة العليا"}


@app.get("/api/health/deep")
def health_deep(request: Request):
    """V2.2 §25 — فحص عميق: DB + Scheduler + Storage + Registry counts.
    يعيد 200 مع تفاصيل كل مكوّن، أو 503 عند فشل أي جزء أساسي."""
    from sqlalchemy import text
    from .database import SessionLocal
    from .v15_registry import summary as v15_summary

    results: dict = {"service": "hrms-kuwait", "checks": {}}
    ok = True

    # 1) DB
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        results["checks"]["database"] = {"status": "ok"}
    except Exception as e:
        results["checks"]["database"] = {"status": "fail", "error": str(e)[:200]}
        ok = False

    # 2) Upload dir
    try:
        upload_dir = settings.upload_dir
        exists = os.path.isdir(upload_dir)
        writable = os.access(upload_dir, os.W_OK) if exists else False
        results["checks"]["storage"] = {
            "status": "ok" if exists and writable else "fail",
            "path": upload_dir, "writable": writable,
        }
        if not (exists and writable):
            ok = False
    except Exception as e:
        results["checks"]["storage"] = {"status": "fail", "error": str(e)[:200]}
        ok = False

    # 3) Scheduler
    results["checks"]["scheduler"] = {"status": "ok" if settings.scheduler_enabled else "disabled"}

    # GC-09 — جاهزية إخراج العقد الحكومي. لا تُسقط الفحص: النظام يعمل
    # بلا LibreOffice ويسلّم docx. لكنها تُعرَض لأن الحال الأسوأ — أداة
    # موجودة بلا خطوط عربية — يُنتج عقًدا بمربّعات فارغة يبدو توليده ناجًحا،
    # ولا يُكتشف إلا حين يفتح موظف الهيئة الورقة.
    try:
        from .gov_contract_docx import environment_report
        results["checks"]["gov_contract"] = environment_report()
    except Exception as e:
        results["checks"]["gov_contract"] = {"status": "unknown", "error": str(e)[:200]}

    # 4) Registry counts
    try:
        results["checks"]["registry"] = {"status": "ok", **v15_summary()}
    except Exception as e:
        results["checks"]["registry"] = {"status": "fail", "error": str(e)[:200]}
        ok = False

    # 5) OCR (Tesseract) — لصفحة "حالة النظام" في العرض التوضيحي (DEMO-3)
    try:
        from . import ocr
        tess = ocr._tesseract_status()
        results["checks"]["ocr"] = {
            "status": "ok" if tess["available"] else "disabled",
            "version": tess.get("version"),
            "languages": tess.get("languages", []),
            "arabic_ready": "ara" in (tess.get("languages") or []),
        }
    except Exception as e:
        results["checks"]["ocr"] = {"status": "fail", "error": str(e)[:200]}

    # 6) Data counts (سريعة — للعرض في لوحة الحالة)
    try:
        from . import models
        with SessionLocal() as db:
            counts = {
                "companies": db.query(models.Company).count(),
                "employees": db.query(models.Employee).count(),
                "users": db.query(models.User).count(),
                "requests": db.query(models.Request).count(),
                "templates": db.query(models.DocumentTemplate).count(),
                "documents": db.query(models.Document).count(),
            }
        results["checks"]["data"] = {"status": "ok", **counts}
    except Exception as e:
        results["checks"]["data"] = {"status": "fail", "error": str(e)[:200]}

    # 7) Alembic head (نسخة الهجرات النشطة)
    #    ملاحظة: لو الجدول غير موجود، يعني schema أُنشئ عبر Base.metadata.create_all()
    #    (وضع تطوير/ديمو مع SQLite) — النظام يعمل لكن بلا تتبّع migrations.
    try:
        from sqlalchemy import text
        with SessionLocal() as db:
            row = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
            results["checks"]["alembic"] = {"status": "ok", "head": row[0] if row else None}
    except Exception as e:
        err = str(e)[:200]
        # نميّز بين "الجدول ما موجودش" (وضع create_all) وبين خطأ اتصال حقيقي
        is_missing_table = "no such table" in err or "does not exist" in err
        results["checks"]["alembic"] = {
            "status": "disabled" if is_missing_table else "fail",
            "error": err,
            "note": ("Schema created via Base.metadata.create_all() — no migration "
                    "tracking. Run 'alembic stamp head' to enable versioning.")
                    if is_missing_table else None,
        }

    # 7-b) هل القاعدة على رأس الكود فعًلا؟
    #
    # عرض version_num وحده لا يقول شيًئا: الرقم يبدو سليًما دائًما. ما يهمّ هو
    # المقارنة برأس الكود — فترحيل لم يُطبَّق يظهر هنا بدل أن يُكتشف بعطل في
    # الاستخدام (كما حدث مع قوالب الإشعارات، ومع خمسة بنود أُعلنت "مُتحقَّقة").
    try:
        from alembic.config import Config as _AlConfig
        from alembic.script import ScriptDirectory as _ScriptDir

        _cfg = _AlConfig(os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini"))
        _cfg.set_main_option("script_location",
                             os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic"))
        code_head = _ScriptDir.from_config(_cfg).get_current_head()
        db_head = (results["checks"].get("alembic") or {}).get("head")
        results["checks"]["alembic"]["code_head"] = code_head
        results["checks"]["alembic"]["up_to_date"] = (db_head == code_head)
        if db_head and code_head and db_head != code_head:
            results["checks"]["alembic"]["status"] = "fail"
            results["checks"]["alembic"]["note"] = (
                f"القاعدة عند {db_head} والكود عند {code_head} — شغّل alembic upgrade head")
            ok = False
    except Exception as e:  # noqa: BLE001 — التشخيص لا يُسقط الفحص
        results["checks"].setdefault("alembic", {})["code_head_error"] = str(e)[:200]

    # 7-d) DLV-31 — حسابات بكلمات مرور بذرة ما زالت تعمل
    try:
        from . import seed_guard
        with SessionLocal() as _db:
            _seed_hits = seed_guard.find_seed_accounts(_db)
        results["checks"]["seed_accounts"] = {
            "status": "fail" if _seed_hits else "ok",
            "count": len(_seed_hits),
            # لا كلمات مرور ولا أسماء كاملة — الرقم المدني والدور يكفيان
            "accounts": [{"civil_id": h["civil_id"], "role": h["role"]} for h in _seed_hits],
            "note": ("حسابات تقبل كلمات مرور البذرة — غيّرها قبل التسليم (DLV-31)"
                     if _seed_hits else None),
        }
        if _seed_hits:
            ok = False
    except Exception as e:  # noqa: BLE001
        results["checks"]["seed_accounts"] = {"status": "unknown", "error": str(e)[:200]}

    # 7-c) انحراف ساعة الخادم — QA-30/QA-22
    #
    # TOTP يقارن بالوقت لا بالسر، فانحراف الساعة يُبطل النظام كله بلا أي خطأ
    # ظاهر في الكود. وُجدت الساعة متأخرة ~111 ثانية فرُفضت رموز صحيحة تماًما،
    # وكان تشخيصها بالتجربة والخطأ. تظهر هنا الآن بحكم صريح.
    try:
        from .routers.twofa import clock_skew_seconds
        skew = clock_skew_seconds()
        if skew is None:
            results["checks"]["clock"] = {"status": "unknown",
                                          "note": "تعذّر الوصول لمصدر وقت خارجي"}
        else:
            # نافذة TOTP 30 ثانية؛ تجاوز 60 يعني رفض رموز صحيحة
            bad = abs(skew) > 60
            results["checks"]["clock"] = {
                "status": "fail" if bad else "ok",
                "skew_seconds": skew,
                "note": ("ساعة الخادم منحرفة — رموز 2FA الصحيحة سُترفض. اضبط NTP."
                         if bad else None),
            }
            if bad:
                ok = False
    except Exception as e:  # noqa: BLE001
        results["checks"]["clock"] = {"status": "unknown", "error": str(e)[:200]}

    # 8) R7-F — قنوات الإشعار الفعّالة (in-app / log / SMS / WhatsApp)
    try:
        from . import channels
        active = channels.active_channels()
        has_external = any(ch["external"] for ch in active)
        results["checks"]["notifications"] = {
            "status": "ok" if active else "fail",
            "channels": active,
            "external_delivery": has_external,
            "note": ("قنوات خارجية (SMS/WhatsApp) مفعّلة" if has_external
                    else "التسليم داخل التطبيق فقط — لتفعيل SMS/WhatsApp اضبط "
                         "TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN في .env"),
        }
    except Exception as e:
        results["checks"]["notifications"] = {"status": "fail", "error": str(e)[:200]}

    body = results if _health_detail_allowed(request) else _redact(results)
    if not ok:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"status": "degraded", **body})
    return {"status": "ok", **body}


# Evidence Pack + V1.5 Manifest: يُنشر بلا مصادقة لتوثيق أن الـ deployment مربوط بالـ build
# المتفق عليه في تقرير القبول النهائي، ولإثبات نسخة سجل الترحيل النشطة (V1.5 §3 Manifest).
# القيم تُقرأ من متغيرات بيئة تُضبط عند البناء (Railway/CI)؛ إن غابت، تُقرأ محليًا من git.
_DEPLOY_STARTED_AT: str | None = None


@app.get("/api/version")
def version():
    """اختصار للتوافق العكسي — يعيد الحقول الأساسية فقط. للتفاصيل الكاملة راجع /api/manifest."""
    m = manifest()
    return {k: m[k] for k in ("service", "version", "commit", "commit_full", "build_time", "environment")}


def _current_migration_version() -> str | None:
    """رقم ترحيل القاعدة الفاعل — جزء من هوية البناء لا تفصيلة تشخيصية."""
    from sqlalchemy import text as _text

    from .database import SessionLocal
    try:
        with SessionLocal() as db:
            row = db.execute(_text("SELECT version_num FROM alembic_version LIMIT 1")).first()
            return row[0] if row else None
    except Exception:  # noqa: BLE001 — الهوية لا تُسقط النقطة
        return None


@app.get("/api/manifest")
def manifest():
    """V1.5 Manifest: version + commit + build_time + deploy_time + migration_version + registry stats.

    يمكن للمهندس/الاختبار التحقق فورًا أن الـ backend المنشور:
    - يشغل الـ commit الصحيح
    - يستخدم النسخة الحالية من Migration Registry
    - عدد الـ canonical workflows/documents/reports مطابق للـ spec (29/25/6/2/9)
    """
    import subprocess
    from datetime import datetime, timezone
    global _DEPLOY_STARTED_AT
    if _DEPLOY_STARTED_AT is None:
        _DEPLOY_STARTED_AT = datetime.now(timezone.utc).isoformat()

    commit = (os.environ.get("GIT_COMMIT") or os.environ.get("RAILWAY_GIT_COMMIT_SHA")
              or os.environ.get("SOURCE_VERSION") or "")
    if not commit:
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=os.path.dirname(__file__),
                stderr=subprocess.DEVNULL, timeout=2,
            ).decode().strip()
        except Exception:
            commit = "unknown"
    build_time = os.environ.get("BUILD_TIME") or _DEPLOY_STARTED_AT

    from .v15_registry import summary as v15_summary
    return {
        "service": "hrms-kuwait",
        "version": app.version,
        "commit": commit[:12] if commit and commit != "unknown" else commit,
        "commit_full": commit,
        "build_time": build_time,
        "deploy_time": _DEPLOY_STARTED_AT,
        "environment": "production" if settings.is_production else "development",
        # DLV-06 — نسخة الترحيلات جزء من هوية البناء: "أي كود يعمل؟" سؤال ناقص
        # بلا "على أي بنية قاعدة؟". بناءان بنفس الـcommit وقاعدتان مختلفتان
        # يسلكان سلوًكا مختلًفا، وتشخيص ذلك بلا هذا الرقم تخمين.
        "migration_version": _current_migration_version(),
        "spec": {
            "current_spec": "V1.5 Consolidated Revision 2",
            "supersedes": ["V1.3", "V1.4"],
            "management_approval": "V1.6 Executive Review Book",
        },
        "registry": v15_summary(),
    }


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
