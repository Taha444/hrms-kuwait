# -*- coding: utf-8 -*-
"""
إرسال البريد الإلكتروني للإشعارات. مُعطّل افتراضيًا؛ يُفعّل بضبط HRMS_MAIL_* في البيئة.
عند التعطيل يُسجّل الرسالة فقط (للتطوير) ولا يفشل النظام.
"""
import logging
import smtplib
from email.header import Header
from email.mime.text import MIMEText

from config import config

log = logging.getLogger("hrms.mailer")


def send_email(to_addr, subject, body):
    """يرسل بريدًا. يرجع True عند النجاح (أو عند التعطيل في التطوير)."""
    if not config.MAIL_ENABLED:
        log.info("[MAIL disabled] to=%s subject=%s", to_addr, subject)
        return False
    if not to_addr:
        return False
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = config.MAIL_FROM
        msg["To"] = to_addr
        with smtplib.SMTP(config.MAIL_HOST, config.MAIL_PORT, timeout=15) as server:
            if config.MAIL_USE_TLS:
                server.starttls()
            if config.MAIL_USERNAME:
                server.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
            server.sendmail(config.MAIL_FROM, [to_addr], msg.as_string())
        return True
    except Exception as e:  # لا نُسقط الطلب بسبب فشل البريد
        log.warning("فشل إرسال البريد إلى %s: %s", to_addr, e)
        return False
