# -*- coding: utf-8 -*-
"""إعدادات التطبيق — تُقرأ من متغيّرات البيئة / ملف .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# مفاتيح SECRET_KEY الافتراضية المعروفة في الكود (يجب رفض تشغيل الإنتاج بها)
DEFAULT_SECRET_KEYS = ("dev-secret-change-me", "change-this-to-a-long-random-secret-in-production")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # الأمان
    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    # SEC-04 — تسجيل خروج تلقائي عند الخمول، بالدقائق. صفر يعطّل الميزة.
    # الواجهة تقرأ القيمة من /auth/me فلا يبقى الرقم مكتوًبا في مكانين.
    idle_logout_minutes: int = 10
    #: IMP-03 — أقصى عمر لجلسة انتحال، بالدقائق. الانتحال أداة دعم لحظية:
    #: جلسة تعيش أربع عشرة يوًما بعمر رمز التجديد تصير هوية ثانية دائمة
    #: للمُنتحِل. صفر = بلا حدّ (خيار صريح لا افتراض).
    impersonation_max_minutes: int = 60
    #: F-001 — رمز يفتح تفصيل /api/health/deep لمن يملكه. فارغ = التفصيل
    #: للإدارة العليا وحدها. المجهول يرى حالة المكوّنات بلا أرقامها.
    health_token: str = ""

    # قاعدة البيانات
    database_url: str = "sqlite:///./hrms.db"

    # الملفات
    upload_dir: str = "./uploads"

    # AWS-01 — وجهة التخزين. الافتراضي قرص الخادم كما كان، فلا يتغيّر شيء
    # لمن لم يضبط شيًئا. وعلى AWS تُضبط "s3" فتنتقل كل الكتابة والقراءة بلا
    # لمس موضع نداء واحد — وهذا هو الغرض من وجود طبقة تخزين واحدة.
    storage_backend: str = "local"        # local | s3
    s3_bucket: str = ""
    s3_prefix: str = ""
    s3_region: str = ""
    # لا مفاتيح وصول هنا عمًدا: الاعتماد يُقرأ من IAM role على الـEC2. أي
    # مفتاح يُكتب في .env هو مفتاح يُسرَّب مع أول نسخة احتياطية أو سجلّ.

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    # لا كلمة مرور افتراضية. كانت هنا قيمة ثابتة تُمنح لكل حساب يُنشأ وكل
    # حساب تُعاد كلمته؛ فمن يعرفها — وهي في المستودع — يدخل بأي منها.
    # البديل: security.generate_temp_password() يولّد واحدة لكل شخص وكل مرة.

    # المجدول
    scheduler_enabled: bool = True

    # تحديد معدّل الدخول (يُعطَّل في الاختبارات)
    rate_limit_enabled: bool = True

    # واتساب/SMS عبر Twilio — تُترك فارغة لتعطيل القناة (تسجيل فقط)، تُضبط في .env للتفعيل الفعلي
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_sms_from: str = ""          # رقم Twilio المرسِل لل SMS، مثل +1XXXXXXXXXX
    twilio_whatsapp_from: str = ""     # رقم واتساب المفعَّل على Twilio، مثل whatsapp:+1XXXXXXXXXX

    # الإشعارات الفورية عبر Firebase Cloud Messaging (HTTP v1).
    #
    # تُترك فارغة فتبقى القناة **معلَنة وغير متاحة** — لا مفتاح يُعرَض
    # للمستخدم يَعِد بتسليم لا يقع (P10-33).
    #
    # والمفتاح الخاص **لا يُكتب في .env كسطر واحد**: يُوضع محتوى ملف
    # حساب الخدمة كما هو، أو يُشار إلى مساره. وسرّ يمرّ في متغيّر بيئة
    # يظهر في كل لقطة سجلّ وكل نسخة احتياطية.
    fcm_project_id: str = ""
    fcm_client_email: str = ""
    fcm_private_key: str = ""          # -----BEGIN PRIVATE KEY----- ...
    fcm_credentials_file: str = ""     # بديل: مسار ملف حساب الخدمة

    # إعدادات Firebase **للويب** — علنية بطبعها (تُشحن في حزمة أي تطبيق
    # ويب)، فتُقدَّم للواجهة من الخادم بدل تثبيتها وقت البناء. وبذلك
    # يصير تفعيل الدفع متغيّر بيئة لا نشرة واجهة جديدة.
    #
    # و``fcm_vapid_key`` مفتاح «شهادة الدفع» من لوحة Firebase — بدونه
    # لا يُصدر المتصفّح رمز جهاز أصًلا.
    fcm_web_api_key: str = ""
    fcm_web_app_id: str = ""
    fcm_messaging_sender_id: str = ""
    fcm_vapid_key: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        """لا يوجد متغيّر بيئة صريح (مثل ENV=production) في هذا المشروع، لذا نعتمد على مؤشر
        واقعي: أي نشر حقيقي يستخدم قاعدة بيانات حقيقية (PostgreSQL مثلاً) بدل SQLite
        الافتراضية للتطوير المحلي/الاختبارات."""
        return not self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
