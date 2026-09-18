# -*- coding: utf-8 -*-
"""المهام المجدولة (APScheduler): المسح اليومي لتوليد مهام انتهاء المستندات."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .database import SessionLocal
from .notifications import daily_scan, digest_scan, sla_scan
from .clock import today as kuwait_today

logger = logging.getLogger("hrms.scheduler")
_scheduler: BackgroundScheduler | None = None

def _alert_job_failure(job: str, exc: Exception) -> None:
    """DLV-23 — فشل مهمة مجدولة يصل مسؤوًلا لا سجًلا وحده.

    ROOT CAUSE: كل مهمة كانت تُسجّل خطأها بـlogger.exception ثم تصمت. سجل
    الخادم لا يقرأه أحد يومًيا، فالمسح اليومي يتوقف أسابيع بلا أن ينتبه أحد —
    وتنتهي إقامات بلا تنبيه لأن المُنبِّه نفسه هو المتعطّل.

    التنبيه مهمة حرجة في النظام: تظهر لمن يفتحه، ولا تحتاج بريًدا ولا تكامًلا
    خارجًيا قد يكون معطًلا هو الآخر. ومفتاح التكرار يمنع مهمة لكل يوم فشل.
    """
    from datetime import date

    from .notifications import create_task

    db = SessionLocal()
    try:
        # **وصاحُب الشركات يتلقّاه** — لا super_admin عند العميل (قاعدة
        # المالك)، فتنبيٌه لا يصل إلا إليه لا يصل أحًدا هناك. وأخطرُه فشُل
        # النسخ الاحتياطي: يتوقّف بصمت حتى يُحتاج إليه.
        from .notifications import oversight_users

        for user in oversight_users(db, None):
            create_task(
                db, company_id=user.company_id, assignee_user_id=user.id,
                type="job_failure", severity="critical",
                title=f"فشل مهمة مجدولة: {job}",
                detail=(f"{type(exc).__name__}: {exc}"[:400] +
                        " — النظام لا يولّد تنبيهاته حتى تُعالَج."),
                # المفتاح لكل مستلِم: مفتاٌح واحٌد للجميع يُسلِّم المهمَة لأوّلهم
                # ويُسقطها عن البقية على أنها «مكرَّرة».
                dedup_key=f"job_fail:{job}:{kuwait_today().isoformat()}:u{user.id}",
            )
        db.commit()
    except Exception:  # noqa: BLE001 — التنبيه لا يُسقط المجدوِل
        logger.exception("تعذّر إنشاء تنبيه فشل المهمة %s", job)
    finally:
        db.close()



def _run_daily_scan():
    db = SessionLocal()
    try:
        # AWS-02 — مرة واحدة عبر كل النسخ. التخطّي ليس عطًلا: نسخة
        # أخرى نفّذت هذه الجولة.
        key = daily_key("daily_scan")
        with run_once(db, "daily_scan", key) as granted:
            if not granted:
                return
            # **ولا يتزامن مع مسحٍ يدويٍّ جارٍ** — كلاهما ``daily_scan`` كاملًا.
            from .job_lock import running_elsewhere
            if running_elsewhere(db, "daily_scan", exclude_key=key):
                logger.info("daily_scan: مسحٌ يدويٌّ جارٍ — يُكتفى به لهذه الجولة")
                return
            result = daily_scan(db)
            logger.info("daily_scan: %s", result)
            # قرار المالك (2026-09-17) — الانصرافُ المنسيّ يُغلق بقاعدته.
            from .routers.attendance import close_all_forgotten

            closed = close_all_forgotten(db)
            if closed:
                db.commit()
                logger.info("attendance auto-closed: %s", closed)
            # **والأثر المؤجَّل يجد يومه.** ترقيٌة بنفاٍذ مستقبلي لا تُطبَّق
            # يوم اعتمادها، فلولا هذا المسح لبقيت «مؤجَّلة» إلى الأبد —
            # وتأجيٌل بلا يوٍم يحلّ فيه تسويٌف لا تأجيل.
            from .request_effects import apply_due_effects

            due = apply_due_effects(db)
            if due["applied"] or due["failed"]:
                logger.info("apply_due_effects: %s", due)
    except Exception as exc:  # pragma: no cover
        logger.exception("فشل المسح اليومي")
        _alert_job_failure("daily_scan", exc)
    finally:
        db.close()


def _run_sla_scan():
    """يفحص المهام المفتوحة كل ساعة ويصعّد أي مهمة تجاوزت مهلة SLA الخاصة بقالبها."""
    db = SessionLocal()
    try:
        # AWS-02 — مرة واحدة عبر كل النسخ. التخطّي ليس عطًلا: نسخة
        # أخرى نفّذت هذه الجولة.
        with run_once(db, "sla_scan", hourly_key("sla_scan")) as granted:
            if not granted:
                return
            result = sla_scan(db)
            if result.get("escalated"):
                logger.info("sla_scan: %s", result)
    except Exception as exc:  # pragma: no cover
        logger.exception("فشل مسح SLA")
        _alert_job_failure("sla_scan", exc)
    finally:
        db.close()


def _run_digest():
    """V2.2 §20 — Digest يومي 8 صباحًا: ملخص المهام لكل مستخدم بدل إشعارات متكررة."""
    db = SessionLocal()
    try:
        # AWS-02 — مرة واحدة عبر كل النسخ. التخطّي ليس عطًلا: نسخة
        # أخرى نفّذت هذه الجولة.
        with run_once(db, "digest_scan", daily_key("digest_scan")) as granted:
            if not granted:
                return
            result = digest_scan(db)
            logger.info("digest_scan: %s", result)
    except Exception as exc:  # pragma: no cover
        logger.exception("فشل digest اليومي")
        _alert_job_failure("digest_scan", exc)
    finally:
        db.close()


def _run_backup():
    """النسخة الليلية خارج الخادم — قرار المالك (2026-09-19). لا تُجدوَل بلا إعداد."""
    from .backup import BackupConfig, run_backup
    from .job_lock import daily_key, run_once

    cfg = BackupConfig.from_env()
    if cfg is None:
        return
    db = SessionLocal()
    try:
        with run_once(db, "backup", daily_key("backup")) as granted:
            if not granted:
                return
            result = run_backup(cfg)
            logger.info("backup: %s", result)
    except Exception as exc:  # pragma: no cover
        logger.exception("فشل النسخ الاحتياطي")
        _alert_job_failure("backup", exc)
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="Asia/Kuwait")
    # يوميًا الساعة 6 صباحًا بتوقيت الكويت
    _scheduler.add_job(_run_daily_scan, CronTrigger(hour=6, minute=0), id="daily_scan",
                       replace_existing=True)
    # كل ساعة على رأس الساعة: مسح SLA (P1-NOTIF-01)
    _scheduler.add_job(_run_sla_scan, CronTrigger(minute=0), id="sla_scan",
                       replace_existing=True)
    # يوميًا 8 صباحًا: digest إحصائيات المهام لكل مستخدم (V2.2 §20)
    _scheduler.add_job(_run_digest, CronTrigger(hour=8, minute=0), id="digest_scan",
                       replace_existing=True)
    # يوميًا 2:30 فجرًا: النسخة المشفّرة خارج الخادم — إن ضُبطت (قرار المالك 2026-09-19)
    from .backup import BackupConfig
    if BackupConfig.from_env() is not None:
        _scheduler.add_job(_run_backup, CronTrigger(hour=2, minute=30), id="backup",
                           replace_existing=True)
    else:
        logger.warning("النسخ الاحتياطي خارج الخادم غير مضبوط (BACKUP_S3_BUCKET / "
                       "BACKUP_ENCRYPTION_KEY) — لا نسخة ليلية")
    _scheduler.start()
    logger.info("تم تشغيل المجدول (اليومي 6ص + SLA كل ساعة + Digest 8ص)")
    return _scheduler


def shutdown_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
