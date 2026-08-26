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

    from .notifications import create_task, users_by_role

    db = SessionLocal()
    try:
        for user in users_by_role(db, None, ["super_admin"]):
            create_task(
                db, company_id=user.company_id, assignee_user_id=user.id,
                type="job_failure", severity="critical",
                title=f"فشل مهمة مجدولة: {job}",
                detail=(f"{type(exc).__name__}: {exc}"[:400] +
                        " — النظام لا يولّد تنبيهاته حتى تُعالَج."),
                dedup_key=f"job_fail:{job}:{kuwait_today().isoformat()}",
            )
        db.commit()
    except Exception:  # noqa: BLE001 — التنبيه لا يُسقط المجدوِل
        logger.exception("تعذّر إنشاء تنبيه فشل المهمة %s", job)
    finally:
        db.close()



def _run_daily_scan():
    db = SessionLocal()
    try:
        result = daily_scan(db)
        logger.info("daily_scan: %s", result)
    except Exception as exc:  # pragma: no cover
        logger.exception("فشل المسح اليومي")
        _alert_job_failure("daily_scan", exc)
    finally:
        db.close()


def _run_sla_scan():
    """يفحص المهام المفتوحة كل ساعة ويصعّد أي مهمة تجاوزت مهلة SLA الخاصة بقالبها."""
    db = SessionLocal()
    try:
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
        result = digest_scan(db)
        logger.info("digest_scan: %s", result)
    except Exception as exc:  # pragma: no cover
        logger.exception("فشل digest اليومي")
        _alert_job_failure("digest_scan", exc)
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
    _scheduler.start()
    logger.info("تم تشغيل المجدول (اليومي 6ص + SLA كل ساعة + Digest 8ص)")
    return _scheduler


def shutdown_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
