# -*- coding: utf-8 -*-
"""إعدادات التطبيق — تُقرأ من متغيّرات البيئة / ملف .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # الأمان
    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # قاعدة البيانات
    database_url: str = "sqlite:///./hrms.db"

    # الملفات
    upload_dir: str = "./uploads"

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    # كلمة المرور الافتراضية لأول دخول
    default_user_password: str = "Kuwait@2024"

    # المجدول
    scheduler_enabled: bool = True

    # تحديد معدّل الدخول (يُعطَّل في الاختبارات)
    rate_limit_enabled: bool = True

    # واتساب/SMS عبر Twilio — تُترك فارغة لتعطيل القناة (تسجيل فقط)، تُضبط في .env للتفعيل الفعلي
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_sms_from: str = ""          # رقم Twilio المرسِل لل SMS، مثل +1XXXXXXXXXX
    twilio_whatsapp_from: str = ""     # رقم واتساب المفعَّل على Twilio، مثل whatsapp:+1XXXXXXXXXX

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
