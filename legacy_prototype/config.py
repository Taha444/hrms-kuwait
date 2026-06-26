# -*- coding: utf-8 -*-
"""
إعدادات النظام المركزية. تُقرأ من متغيّرات البيئة (مع قيم افتراضية آمنة للتطوير).
يدعم تحميل ملف .env إن وُجد (python-dotenv اختياري).
"""
import os

BASE_DIR = os.path.dirname(__file__)

# تحميل .env إن توفّرت المكتبة والملف
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except Exception:
    pass


def _bool(name, default=False):
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    # تشغيل
    DEBUG = _bool("HRMS_DEBUG", False)
    HOST = os.environ.get("HRMS_HOST", "127.0.0.1")
    PORT = _int("HRMS_PORT", 5000)

    # المفتاح السري (الأفضل تعيينه عبر البيئة في الإنتاج)
    SECRET_KEY = os.environ.get("HRMS_SECRET_KEY")  # إن None يُولّد ويُحفظ في ملف

    # الجلسات والكوكي
    SESSION_LIFETIME_HOURS = _int("HRMS_SESSION_HOURS", 8)
    SESSION_IDLE_MINUTES = _int("HRMS_SESSION_IDLE_MINUTES", 60)  # خمول
    SESSION_COOKIE_SECURE = _bool("HRMS_COOKIE_SECURE", False)    # True خلف HTTPS

    # الأمان
    CSRF_ENABLED = _bool("HRMS_CSRF", True)
    MAX_LOGIN_ATTEMPTS = _int("HRMS_MAX_LOGIN_ATTEMPTS", 5)
    LOCK_MINUTES = _int("HRMS_LOCK_MINUTES", 15)
    PASSWORD_MIN_LEN = _int("HRMS_PASSWORD_MIN_LEN", 8)
    RATE_LIMIT_PER_MINUTE = _int("HRMS_RATE_LIMIT_PER_MINUTE", 120)
    LOGIN_RATE_LIMIT_PER_MINUTE = _int("HRMS_LOGIN_RATE_LIMIT", 10)

    # رفع الملفات
    MAX_CONTENT_LENGTH = _int("HRMS_MAX_UPLOAD_MB", 16) * 1024 * 1024
    ALLOWED_UPLOAD_EXTENSIONS = {
        "pdf", "png", "jpg", "jpeg", "gif", "webp",
        "doc", "docx", "xls", "xlsx", "txt", "csv",
    }

    # البريد (للإشعارات) — يحتاج بيانات اعتماد لتعمل فعليًا
    MAIL_ENABLED = _bool("HRMS_MAIL_ENABLED", False)
    MAIL_HOST = os.environ.get("HRMS_MAIL_HOST", "")
    MAIL_PORT = _int("HRMS_MAIL_PORT", 587)
    MAIL_USERNAME = os.environ.get("HRMS_MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("HRMS_MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("HRMS_MAIL_FROM", "hrms@example.com")
    MAIL_USE_TLS = _bool("HRMS_MAIL_TLS", True)

    # الرسائل النصية (SMS) — واجهة قابلة للتوصيل بأي مزوّد
    SMS_ENABLED = _bool("HRMS_SMS_ENABLED", False)
    SMS_PROVIDER = os.environ.get("HRMS_SMS_PROVIDER", "")
    SMS_API_KEY = os.environ.get("HRMS_SMS_API_KEY", "")

    # جدولة فحص التنبيهات اليومي
    SCHEDULER_ENABLED = _bool("HRMS_SCHEDULER_ENABLED", False)
    ALERTS_SCAN_HOUR = _int("HRMS_ALERTS_SCAN_HOUR", 7)

    # النسخ الاحتياطي
    BACKUP_DIR = os.environ.get("HRMS_BACKUP_DIR", os.path.join(BASE_DIR, "backups"))


config = Config()
