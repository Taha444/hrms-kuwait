# -*- coding: utf-8 -*-
"""المهام المجدولة (APScheduler): المسح اليومي لتوليد مهام انتهاء المستندات."""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .database import SessionLocal
from .notifications import daily_scan

logger = logging.getLogger("hrms.scheduler")
_scheduler: BackgroundScheduler | None = None


def _run_daily_scan():
    db = SessionLocal()
    try:
        result = daily_scan(db)
        logger.info("daily_scan: %s", result)
    except Exception:  # pragma: no cover
        logger.exception("فشل المسح اليومي")
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
    _scheduler.start()
    logger.info("تم تشغيل المجدول (المسح اليومي 6 صباحًا)")
    return _scheduler


def shutdown_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
