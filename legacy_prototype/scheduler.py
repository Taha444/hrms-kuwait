# -*- coding: utf-8 -*-
"""
مهام مجدولة: فحص يومي للتنبيهات (إقامات/تراخيص/مستندات) وإرسال إشعارات،
وإعادة حساب رصيد الإجازات. يعتمد APScheduler ويُفعّل بـ HRMS_SCHEDULER_ENABLED=true.
"""
import logging

from config import config

log = logging.getLogger("hrms.scheduler")
_scheduler = None


def _daily_scan(app):
    """يفحص التنبيهات الحرجة ويُنشئ إشعارات لمديري كل شركة."""
    import db
    import leave_service
    import notify
    from alerts import generate_alerts

    with app.app_context():
        try:
            leave_service.recalc_all()
        except Exception as e:
            log.warning("فشل إعادة حساب رصيد الإجازات: %s", e)

        alerts = generate_alerts(None)
        critical = [a for a in alerts if a["severity"] in ("expired", "critical")]
        if not critical:
            return
        # إشعار مديري كل شركة بعدد التنبيهات الحرجة لشركتهم
        by_company = {}
        for a in critical:
            by_company.setdefault(a["company_id"], []).append(a)
        for cid, items in by_company.items():
            managers = db.query(
                "SELECT * FROM users WHERE company_id=? AND role IN ('company_manager') AND is_active=1",
                (cid,))
            for m in db.rows_to_list(managers):
                notify.push(
                    m["id"], cid, "alert",
                    f"لديك {len(items)} تنبيه حرج",
                    "هناك إقامات/تراخيص/مستندات منتهية أو على وشك الانتهاء.",
                    email=m.get("email"), phone=m.get("phone"))
        log.info("الفحص اليومي: %d تنبيه حرج", len(critical))


def start_scheduler(app):
    """يبدأ الجدولة إن كانت مفعّلة. آمن للاستدعاء مرة واحدة."""
    global _scheduler
    if not config.SCHEDULER_ENABLED or _scheduler is not None:
        return None
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except Exception:
        log.warning("APScheduler غير مثبّت؛ تم تخطّي الجدولة.")
        return None

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(lambda: _daily_scan(app), "cron", hour=config.ALERTS_SCAN_HOUR,
                       id="daily_alerts_scan", replace_existing=True)
    _scheduler.start()
    log.info("بدأت الجدولة: فحص يومي الساعة %d", config.ALERTS_SCAN_HOUR)
    return _scheduler
