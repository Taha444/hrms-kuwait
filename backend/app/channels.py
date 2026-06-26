# -*- coding: utf-8 -*-
"""قنوات الإشعار القابلة للتوصيل (داخل التطبيق + واتساب/SMS).

المرحلة الأولى: قناة داخل التطبيق (جدول tasks) + قناة سجلّ (Log) تعمل فعليًا.
قنوات واتساب/SMS معرّفة بواجهة موحّدة وتُفعَّل بمجرد ضبط بيانات المزوّد في .env
(مثل Twilio) — دون تغيير بقية النظام.
"""
from __future__ import annotations

import logging
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


# القنوات الفعّالة (تُضاف قنوات حقيقية عند ضبط المزوّدين)
_channels: list[NotificationChannel] = [LogChannel()]


def dispatch(to: str | None, title: str, body: str) -> None:
    """يرسل الإشعار عبر كل القنوات الفعّالة (best-effort، لا يكسر العملية)."""
    for ch in _channels:
        try:
            ch.send(to or "", title, body or "")
        except Exception:  # pragma: no cover
            logger.exception("فشل إرسال إشعار عبر القناة %s", getattr(ch, "name", "?"))


def register_channel(channel: NotificationChannel) -> None:
    _channels.append(channel)
