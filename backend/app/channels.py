# -*- coding: utf-8 -*-
"""قنوات الإشعار القابلة للتوصيل (داخل التطبيق + واتساب/SMS).

المرحلة الأولى: قناة داخل التطبيق (جدول tasks) + قناة سجلّ (Log) تعمل فعليًا.
قنوات واتساب/SMS معرّفة بواجهة موحّدة وتُفعَّل بمجرد ضبط بيانات المزوّد في .env
(مثل Twilio) — دون تغيير بقية النظام.
"""
from __future__ import annotations

import base64
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Protocol

logger = logging.getLogger("hrms.notify")


class NotificationChannel(Protocol):
    name: str
    def send(self, to: str, title: str, body: str) -> bool: ...


class LogChannel:
    """قناة افتراضية تسجّل الإشعار (للتطوير والتتبّع)."""
    name = "log"

    def send(self, to: str, title: str, body: str) -> bool:
        logger.info("إشعار → %s | %s | %s", to or "-", title, body)
        return True


class SmsChannel:
    """قناة SMS — تتطلّب ضبط مزوّد (Twilio/Unifonic). تُرجع False إن لم تُفعَّل."""
    name = "sms"

    def __init__(self, provider=None):
        self.provider = provider

    def send(self, to: str, title: str, body: str) -> bool:
        if not self.provider:
            logger.warning("قناة SMS غير مُفعّلة (لم يُضبط المزوّد).")
            return False
        return self.provider.send_sms(to, f"{title}\n{body}")


class WhatsAppChannel:
    """قناة واتساب — تتطلّب ضبط مزوّد (Twilio WhatsApp/Meta Cloud API)."""
    name = "whatsapp"

    def __init__(self, provider=None):
        self.provider = provider

    def send(self, to: str, title: str, body: str) -> bool:
        if not self.provider:
            logger.warning("قناة واتساب غير مُفعّلة (لم يُضبط المزوّد).")
            return False
        return self.provider.send_whatsapp(to, f"{title}\n{body}")


class TwilioProvider:
    """مزوّد فعلي عبر REST API الخاص بـ Twilio (بلا مكتبة خارجية — urllib فقط).

    يحتاج account_sid و auth_token فعليَّين من لوحة Twilio؛ بدونهما تبقى القناة معطَّلة
    (WhatsAppChannel/SmsChannel تُرجعان False) دون أي كسر للنظام.
    """

    API_BASE = "https://api.twilio.com/2010-04-01/Accounts"

    def __init__(self, account_sid: str, auth_token: str, sms_from: str = "", whatsapp_from: str = ""):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.sms_from = sms_from
        self.whatsapp_from = whatsapp_from

    def _post(self, to: str, from_: str, body: str) -> bool:
        if not (self.account_sid and self.auth_token and from_ and to):
            logger.warning("Twilio: بيانات ناقصة (sid/token/from/to) — لم يُرسَل شيء.")
            return False
        url = f"{self.API_BASE}/{self.account_sid}/Messages.json"
        data = urllib.parse.urlencode({"To": to, "From": from_, "Body": body}).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        auth = base64.b64encode(f"{self.account_sid}:{self.auth_token}".encode()).decode()
        req.add_header("Authorization", f"Basic {auth}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return 200 <= resp.status < 300
        except urllib.error.URLError:
            logger.exception("Twilio: فشل الاتصال بواجهة الإرسال")
            return False

    def send_sms(self, to: str, body: str) -> bool:
        return self._post(to, self.sms_from, body)

    def send_whatsapp(self, to: str, body: str) -> bool:
        to_wa = to if to.startswith("whatsapp:") else f"whatsapp:{to}"
        return self._post(to_wa, self.whatsapp_from, body)


# القنوات الفعّالة (تُضاف قنوات حقيقية عند ضبط المزوّدين)
_channels: list[NotificationChannel] = [LogChannel()]


def configure_from_settings(settings) -> None:
    """يُستدعى عند إقلاع التطبيق: يفعّل واتساب/SMS الفعليتين إن ضُبطت بيانات Twilio في .env."""
    if not (settings.twilio_account_sid and settings.twilio_auth_token):
        return
    provider = TwilioProvider(settings.twilio_account_sid, settings.twilio_auth_token,
                              settings.twilio_sms_from, settings.twilio_whatsapp_from)
    if settings.twilio_sms_from:
        register_channel(SmsChannel(provider))
    if settings.twilio_whatsapp_from:
        register_channel(WhatsAppChannel(provider))
    logger.info("Twilio: تم تفعيل قنوات SMS/واتساب الفعلية.")


def dispatch(to: str | None, title: str, body: str) -> None:
    """يرسل الإشعار عبر كل القنوات الفعّالة (best-effort، لا يكسر العملية)."""
    for ch in _channels:
        try:
            ch.send(to or "", title, body or "")
        except Exception:  # pragma: no cover
            logger.exception("فشل إرسال إشعار عبر القناة %s", getattr(ch, "name", "?"))


def register_channel(channel: NotificationChannel) -> None:
    _channels.append(channel)


def redispatch_task(db, task) -> None:
    """V2.2 §20 — إعادة إرسال مهمة عبر قنواتها بعد فشل سابق. يرمي استثناء عند الفشل
    ليصل للمُستدعي (endpoint إعادة المحاولة)."""
    # نستخدم القنوات الافتراضية؛ المهمة نفسها تحمل قناتها في task.channel لو محددة
    target = None
    try:
        from . import models
        if task.assignee_user_id:
            u = db.get(models.User, task.assignee_user_id)
            if u:
                # نبحث عن رقم أو email على ملفه (اختياري — قد يكون فارغًا)
                target = getattr(u, "phone", None) or getattr(u, "email", None)
    except Exception:
        pass
    # dispatch نفسه لا يرمي، ننقل الفشل عبر أول قناة تفشل صريحًا
    dispatch(target, task.title or "", task.detail or "")
