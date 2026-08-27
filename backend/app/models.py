# -*- coding: utf-8 -*-
"""نماذج قاعدة البيانات (SQLAlchemy 2.0) — كل الكيانات الأساسية للنظام.

كل كيان مرتبط بـ company_id لتطبيق العزل (Multi-Tenancy)، عدا users
حيث الإدارة العليا (super_admin) لها company_id = NULL.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str | None] = mapped_column(String(200))
    # V2.2 §6/Module 6 — اختصار حرفي 3 حروف يظهر في Employee ID مثل KOC-KUW-00142
    abbreviation: Mapped[str | None] = mapped_column(String(6))
    commercial_reg: Mapped[str | None] = mapped_column(String(50))
    file_number: Mapped[str | None] = mapped_column(String(50))  # رقم ملف الشركة (القوى العاملة)
    entity_type: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/inactive/archived
    # سياسات مكافأة نهاية الخدمة
    eos_day_divisor: Mapped[int] = mapped_column(Integer, default=26)
    eos_max_months: Mapped[int] = mapped_column(Integer, default=18)
    alert_lead_days: Mapped[int] = mapped_column(Integer, default=30)
    annual_leave_days: Mapped[int] = mapped_column(Integer, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"))
    civil_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # يُستخدم للدخول
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    role: Mapped[str] = mapped_column(String(30), default="employee")
    # مستوى نطاق البيانات: company=كل الشركة، branch=فرع واحد، multi=عدة فروع، self=سجله فقط
    scope_level: Mapped[str] = mapped_column(String(10), default="company")
    scope_branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))  # الفرع لمستوى branch
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))  # للخدمة الذاتية
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/inactive/suspended/locked
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    last_login: Mapped[datetime | None] = mapped_column(DateTime)
    # V2.2 §9 — إبطال الجلسات القديمة: كل token صادر قبل هذا الوقت يُرفض تلقائيًا.
    # يُبدَّل عند: تغيير كلمة المرور، تعطيل الحساب، اكتشاف اختراق.
    tokens_valid_after: Mapped[datetime | None] = mapped_column(DateTime)
    # QA-23 — آخر نشاط فعلي للجلسة (UTC). الخروج التلقائي كان مؤقًتا في المتصفح
    # وحده: يُتجاوَز بإغلاق التبويب أو باستدعاء الـAPI مباشرة، فالتوكن يظل صالًحا
    # ساعات. الخادم هو من يفرض المهلة الآن، والمؤقّت في الواجهة تحسين تجربة فقط.
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime)
    # V2.2 §9 — 2FA (TOTP RFC 6238): سرّي base32 يُنشأ في الـenroll، ويُستخدم للتحقق كل دخول.
    #   totp_confirmed=True بعد أول تحقق ناجح؛ قبلها لا يُعتبر 2FA مفعّلًا للحساب.
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    totp_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    # QA-30 — رموز الاسترداد: مخزَّنة مُجزَّأة (hash) لا نًصا، وتُستهلك مرة واحدة.
    # بدونها يكون فقدان الهاتف قفًلا تاًما: الدخول يستلزم رمز TOTP، وتعطيل
    # 2FA يستلزم جلسة تستلزم الدخول — حلقة مغلقة لا مخرج منها إلا تدخّل يدوي
    # في قاعدة البيانات.
    totp_recovery_hashes: Mapped[list | None] = mapped_column(JSON)
    totp_last_used_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    # SIG-01 — التوقيع الشخصي: مسار صورة PNG/JPG يرفعها المستخدم مرة واحدة، ويحقنها
    # محرك PDF فوق سطر التوقيع في كل مستند رسمي مطبوع منسوب إليه (شهادات، إنذارات،
    # إخلاء طرف، إلخ). يتحمل المستخدم مسؤولية التوقيع كما لو كان يوقّع بيده على ورقة.
    signature_path: Mapped[str | None] = mapped_column(String(400))
    signature_updated_at: Mapped[datetime | None] = mapped_column(DateTime)
    # PILOT-P0-5 — استبدال التوقيع لازم موافقة HR: أول رفع مباشر، بعده يُخزَّن التوقيع
    # الجديد في pending_signature_path والقديم يفضل نشط حتى موافقة HR.
    pending_signature_path: Mapped[str | None] = mapped_column(String(400))
    pending_signature_uploaded_at: Mapped[datetime | None] = mapped_column(DateTime)
    pending_signature_reason: Mapped[str | None] = mapped_column(String(300))
    # P1-#15 — رقم نسخة التوقيع الحالي (يُبدَّل مع كل approve)
    signature_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # R9 §16 — Multi-company user (مندوب يخدم شركتين مثل محمد فاروق):
    #   is_cross_company=True → company_id يكون NULL، والحساب مربوط بعدة شركات
    #   عبر جدول user_company_links (سطر لكل شركة، فيه employee_id في تلك الشركة).
    #   عند الدخول: يختار الشركة → JWT يحمل active_company_id → السيرفر يستنتج
    #   employee_id تلقائيًا لكل طلب.
    is_cross_company: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # R9 §17 — صورة البروفايل (اختيارية، يرفعها المستخدم لتحل محل الأيقونة الافتراضية)
    avatar_path: Mapped[str | None] = mapped_column(String(400))
    avatar_updated_at: Mapped[datetime | None] = mapped_column(DateTime)

    permissions: Mapped[list[UserPermission]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class EosCase(Base):
    """QA §6 — دورة حياة إنهاء الخدمة الكاملة (9 مراحل، فصل سلطات).

    initiated → calculated → approved → clearance → acknowledged → settled

    V2.2 §3.3/§15 (AP-04) — الطباعة والحفظ **ليستا حالتَي عمل**: كانت الحالة
    تمتدّ إلى ready_to_print → printed → filed، فحالة تشغيلية (هل طُبعت الورقة؟)
    تختلط بحالة قانونية (هل صُرفت المستحقات؟). النتيجة أن تسوية مصروفة تبدو
    "غير مكتملة" لأن أحًدا لم يطبعها، وأن تقارير الإنهاء تعدّ الطباعة إنجاًزا.
    الحالة تنتهي عند settled، ودورة المستند مستقلة في document_status.

    من ينفّذ ماذا (Separation of Duties):
      initiate   : HR (يفتح الحالة ويحدد تاريخ وسبب الإنهاء)
      calculate  : المحاسب/المالية (يحسب من ملف الموظف — لا قيم افتراضية)
      approve    : صاحب صلاحية approve_termination، ويجب ألا يكون هو من حسب
      clearance  : HR (إخلاء الطرف: عهد/مستندات/تسليم)
      acknowledge: الموظف نفسه (إقرار باطلاعه على التسوية)
      settle     : المحاسب (تأكيد الصرف الفعلي)
      print/file : HR (الأرشفة الورقية)

    settlement_json يُملأ في مرحلة الحساب من سجل الموظف (راتب/تاريخ تعيين)
    ولا يُقبَل من الإدخال — نفس قاعدة /eos/for-employee.
    """
    __tablename__ = "eos_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="initiated", index=True)
    # V2.2 §3.3 (AP-04) — دورة المستند مستقلة عن حالة الحالة نفسها
    document_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    reference_no: Mapped[str | None] = mapped_column(String(60), unique=True, index=True)

    termination_date: Mapped[date | None] = mapped_column(Date)
    termination_reason: Mapped[str | None] = mapped_column(String(40))
    used_leave_days: Mapped[float] = mapped_column(Float, default=0)
    settlement_json: Mapped[dict | None] = mapped_column(JSON)

    initiated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    initiated_at: Mapped[datetime | None] = mapped_column(DateTime)
    calculated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    clearance_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    clearance_at: Mapped[datetime | None] = mapped_column(DateTime)
    clearance_notes: Mapped[str | None] = mapped_column(Text)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime)
    acknowledgment_note: Mapped[str | None] = mapped_column(Text)
    settled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime)
    payment_reference: Mapped[str | None] = mapped_column(String(80))
    printed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    printed_at: Mapped[datetime | None] = mapped_column(DateTime)
    filed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    filed_at: Mapped[datetime | None] = mapped_column(DateTime)
    filing_location: Mapped[str | None] = mapped_column(String(200))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class UserSignatureVersion(Base):
    """QA §12 — سجل نسخ التوقيع غير القابل للتعديل (immutable evidence trail).

    كل نسخة تُعتمَد تُسجَّل هنا مرة واحدة ولا تُحدَّث أبدًا. المستندات المُصدَرة
    تشير لرقم النسخة (signature_version)، فيمكن دائمًا إثبات أي توقيع كان
    ساريًا لحظة الإصدار ومن اعتمده ولماذا.

    الحقول تغطي متطلبات الـevidence: الفاعل ودوره وشركته وفرعه، المُعتمِد،
    السبب، المرحلة، والـcorrelation_id الذي يربط الطلب بالاعتماد في سجل التدقيق.
    لا يُخزَّن مسار التخزين للعميل — يُعرَض عبر endpoint موثّق فقط.
    """
    __tablename__ = "user_signature_versions"
    __table_args__ = (
        UniqueConstraint("user_id", "version", name="uq_user_signature_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str | None] = mapped_column(String(400))  # داخلي — لا يُعاد للعميل
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    # سياق الفاعل (صاحب التوقيع) لحظة التسجيل
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    actor_role: Mapped[str | None] = mapped_column(String(30))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))
    # سياق الاعتماد
    stage: Mapped[str] = mapped_column(String(30), default="approved")  # first_upload/approved/rejected
    reason: Mapped[str | None] = mapped_column(String(300))
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approver_role: Mapped[str | None] = mapped_column(String(30))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    # ربط بسجل التدقيق
    correlation_id: Mapped[str | None] = mapped_column(String(80), index=True)
    reference_no: Mapped[str | None] = mapped_column(String(60), unique=True, index=True)
    before_json: Mapped[dict | None] = mapped_column(JSON)
    after_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class UserCompanyLink(Base):
    """R9 §16 — عضوية user في شركة (لمستخدمي is_cross_company=True).

    كل سطر يربط user_id بـcompany_id مع employee_id (سجل الموظف في تلك الشركة).
    الشرط: employee.company_id لازم يطابق company_id (نفرضه في service layer).
    الفريدية: (user_id, company_id) — يُمنع سطرين لنفس الشركة.
    """
    __tablename__ = "user_company_links"
    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_user_company_link"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    role: Mapped[str] = mapped_column(String(30), default="delegate")  # الدور في هذه الشركة
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class UserPermission(Base):
    __tablename__ = "user_permissions"
    __table_args__ = (UniqueConstraint("user_id", "perm_code", name="uq_user_perm"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    perm_code: Mapped[str] = mapped_column(String(50))
    expires_at: Mapped[date | None] = mapped_column(Date)  # صلاحية مؤقتة

    user: Mapped[User] = relationship(back_populates="permissions")


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str | None] = mapped_column(String(200))
    # V2.2 §6/Module 6 — كود حرفي للفرع يظهر في Employee ID (KOC-KUW-00142)
    code: Mapped[str | None] = mapped_column(String(6))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    geofence_radius_m: Mapped[int] = mapped_column(Integer, default=100)
    qr_secret: Mapped[str] = mapped_column(String(64))  # سرّ توليد رمز QR المتغيّر
    kiosk_key: Mapped[str | None] = mapped_column(String(64))  # مفتاح شاشة عرض QR (قابل للتدوير)
    auto_checkout_minutes: Mapped[int] = mapped_column(Integer, default=15)
    address: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class BranchSupervisor(Base):
    """ربط مسؤولي الفروع بفروعهم (متعدد لمتعدد)."""
    __tablename__ = "branch_supervisors"
    __table_args__ = (UniqueConstraint("branch_id", "user_id", name="uq_branch_supervisor"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


class ResidencyRenewal(Base):
    """معاملة تجديد الإقامة (مبكر/عادي) بحالاتها المتعددة — DEMO-001/002.

    R4 §7 — حقول إتمام المعاملة الحكومية (يعبّئها المندوب في finalize):
      - gov_reference_no: الرقم المرجعي الحكومي للمعاملة
      - fees_amount + fees_receipt_no: قيمة الرسوم ورقم الإيصال
      - new_permit_number + new_expiry_date: بيانات الإقامة الجديدة
    ثم HR يتحقق (hr_verified_by/at) قبل الإغلاق النهائي COMPLETED.
    """
    __tablename__ = "residency_renewals"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    permit_id: Mapped[int | None] = mapped_column(ForeignKey("permits.id"))  # الإقامة محل التجديد
    renewal_type: Mapped[str] = mapped_column(String(10), default="early")  # early / normal
    status: Mapped[str] = mapped_column(String(30), default="new", index=True)
    reason: Mapped[str | None] = mapped_column(Text)          # سبب التجديد المبكر (إلزامي للمبكر)
    notes: Mapped[str | None] = mapped_column(Text)
    reject_reason: Mapped[str | None] = mapped_column(Text)   # سبب الرفض
    days_left_at_request: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    # R4 §7 — Government Transaction Metadata
    gov_reference_no: Mapped[str | None] = mapped_column(String(60), index=True)
    fees_amount: Mapped[float | None] = mapped_column(Float)
    fees_receipt_no: Mapped[str | None] = mapped_column(String(60))
    new_permit_number: Mapped[str | None] = mapped_column(String(60))
    new_expiry_date: Mapped[date | None] = mapped_column(Date)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime)
    finalized_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    hr_verified_at: Mapped[datetime | None] = mapped_column(DateTime)
    hr_verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    hr_verification_note: Mapped[str | None] = mapped_column(Text)
    # RNW-12 — مصدر كل قيمة معتمَدة: هل قرأها النظام أم أدخلها إنسان، وبأي
    # ثقة، ومن أي مستند، ومن أكّدها ومتى. بعد سنة حين يُسأل عن تاريخ انتهاء
    # في ملف موظف، هذا هو الفرق بين جواب مكتوب وتخمين.
    confirmed_data_json: Mapped[dict | None] = mapped_column(JSON)


class Department(Base):
    """الإدارة/القسم داخل فرع (الهرم: شركة ← فرع ← إدارة ← موظفون)."""
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    manager_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    start_time: Mapped[time] = mapped_column(Time, default=time(8, 0))
    end_time: Mapped[time] = mapped_column(Time, default=time(17, 0))
    work_days: Mapped[str] = mapped_column(String(30), default="0,1,2,3,4")  # 0=الأحد
    grace_minutes: Mapped[int] = mapped_column(Integer, default=15)


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    # PILOT-P0-6 — الرقم الوظيفي المرئي (لا يتغيّر مع نقل الفرع). صيغة "CO-BR-####"
    # حيث CO = مختصر الشركة (رقم شركة داخلي مبسّط) و BR = مختصر الفرع و #### = تسلسل.
    # يُولَّد تلقائيًا لكل موظف جديد ولا يقبل التعديل من الواجهة.
    employee_no: Mapped[str | None] = mapped_column(String(30), unique=True, index=True)
    civil_id: Mapped[str | None] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str | None] = mapped_column(String(200))
    nationality: Mapped[str | None] = mapped_column(String(100))
    gender: Mapped[str | None] = mapped_column(String(10))  # male / female
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    marital_status: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(150))
    passport_number: Mapped[str | None] = mapped_column(String(40))
    passport_expiry: Mapped[date | None] = mapped_column(Date)
    health_insurance: Mapped[str | None] = mapped_column(String(100))
    direct_manager_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))
    worker_type: Mapped[str | None] = mapped_column(String(50))  # عامل / موظف
    job_title: Mapped[str | None] = mapped_column(String(150))  # المهنة الرسمية (إذن العمل)
    # الوظيفة الفعلية: ما يؤديه الموظف عمليًا وقد يختلف عن مهنة إذن العمل —
    # يقابل ثنائية (رسمي/فعلي) القائمة أصلًا في الراتب والفرع والترخيص.
    actual_job_title: Mapped[str | None] = mapped_column(String(150))
    job_title_en: Mapped[str | None] = mapped_column(String(150))  # للعقد الحكومي ثنائي اللغة
    nationality_en: Mapped[str | None] = mapped_column(String(80))  # للعقد الحكومي
    basic_salary: Mapped[float] = mapped_column(Float, default=0)  # الراتب الرسمي (عقد/إذن عمل/حكومي)
    actual_salary: Mapped[float | None] = mapped_column(Float)  # الراتب الفعلي (صلاحية خاصة)
    # ساعات الدوام: "محددة" تعني ساعات معلومة تُكتب رسميًا وفعليًا، و"غير محددة"
    # تعني طبيعة عمل بلا ساعات ثابتة (مندوب/مياومة) فلا معنى لرقمَي الساعات.
    work_hours_type: Mapped[str | None] = mapped_column(String(20))  # fixed / unfixed
    official_work_hours: Mapped[float | None] = mapped_column(Float)  # المعلَنة في العقد
    actual_work_hours: Mapped[float | None] = mapped_column(Float)    # المؤدّاة فعليًا
    hire_date: Mapped[date | None] = mapped_column(Date)
    contract_type: Mapped[str] = mapped_column(String(20), default="indefinite")  # indefinite/definite
    status: Mapped[str] = mapped_column(String(20), default="active")
    license_id: Mapped[int | None] = mapped_column(ForeignKey("licenses.id"))  # الترخيص الرسمي
    actual_license_id: Mapped[int | None] = mapped_column(ForeignKey("licenses.id"))  # ترخيص الدوام الفعلي
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))  # الفرع الرسمي
    actual_branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))  # فرع الدوام الفعلي
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # من أضاف الموظف
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id"))
    attendance_mode: Mapped[str] = mapped_column(String(10), default="none")  # none/qr/gps/both
    # SEC2-17: كل Active موظف يجب أن يكون له وضع حضور صريح، أو مُعفى بسبب موثّق
    #   attendance_mode="none" مقبولة فقط مع attendance_exempt=True + سبب
    attendance_exempt: Mapped[bool] = mapped_column(Boolean, default=False)
    attendance_exempt_reason: Mapped[str | None] = mapped_column(String(200))
    attendance_exempt_approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    attendance_exempt_approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    annual_leave_balance: Mapped[float] = mapped_column(Float, default=30)
    # QA-18 — سجل وصول/صلاحية فقط، لا وظيفة على كشف الرواتب.
    # المندوب الذي يخدم شركتين يحتاج سجل موظف في كل منهما ليعمل فيهما، لكن
    # راتبه في واحدة فقط. بلا هذا التمييز يدخل كشف الشركة الثانية براتب صفر
    # ويُحتسب له مستحق نهاية خدمة لا وجود له.
    non_payroll: Mapped[bool] = mapped_column(Boolean, default=False)
    non_payroll_reason: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    photo: Mapped[str | None] = mapped_column(String(300))
    # نهاية الخدمة: تُحفظ نتيجة الحسبة في ملف الموظف عند الإنهاء
    termination_date: Mapped[date | None] = mapped_column(Date)
    termination_reason: Mapped[str | None] = mapped_column(String(40))
    eos_settlement_json: Mapped[str | None] = mapped_column(Text)
    # PILOT-P0-8 — دورة إنهاء الخدمة المتدرجة:
    #   prepared (HR يحسب المسودة) → approved (المحاسب يعتمد ماليًا) → executed (الفصل الفعلي)
    #   الموظف يبقى status="active" حتى الاعتماد، ولا يتم الفصل مباشرة.
    pending_termination_json: Mapped[str | None] = mapped_column(Text)
    pending_termination_prepared_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    pending_termination_prepared_at: Mapped[datetime | None] = mapped_column(DateTime)
    pending_termination_approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    pending_termination_approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    # V2.2 §13 — Full EOS workflow: بعد approve نضيف مرحلتين قبل execute:
    #   Clearance (إخلاء الطرف من الأقسام) + Employee Acknowledgment (توقيع الموظف)
    pending_termination_cleared_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    pending_termination_cleared_at: Mapped[datetime | None] = mapped_column(DateTime)
    pending_termination_clearance_note: Mapped[str | None] = mapped_column(Text)
    pending_termination_acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    license_no: Mapped[str | None] = mapped_column(String(80))
    issuing_authority: Mapped[str | None] = mapped_column(String(200))
    license_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="active")
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    allowed_workers: Mapped[int] = mapped_column(Integer, default=0)
    address: Mapped[str | None] = mapped_column(String(300))


class Permit(Base):
    """إقامة / إذن عمل."""
    __tablename__ = "permits"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    kind: Mapped[str] = mapped_column(String(30))  # residency / work_permit
    number: Mapped[str | None] = mapped_column(String(80))
    start_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")


class DocumentType(Base):
    __tablename__ = "document_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    has_expiry: Mapped[bool] = mapped_column(Boolean, default=True)
    lead_days_json: Mapped[list | None] = mapped_column(JSON, default=list)  # مهل التنبيه


class Document(Base):
    """مستند بنُسخ/تأريخ — الأحدث is_current=True والقديم محفوظ.

    Immutable Artifact Metadata (R1-A §8):
    - `is_issued`: True فقط لمستندات مُولّدة عبر /generate (لا preview)
    - `reference_no`: رقم مرجعي مقروء بشريًا (unique per company)
    - `template_version`: نسخة القالب اللي وُلِّد منها (لتتبّع التعديلات)
    - `checksum_sha256`: بصمة SHA-256 للملف — تُحسب عند التوليد
    - `generated_at/by`: من نفّذ التوليد ومتى (UTC)
    - `signature_version`: نسخة توقيع المُصدر إن كانت مدمجة
    Mark Printed/Filed مرفوضة على مستند is_issued=False.
    """
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(30), default="employee")  # employee/company/license
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    document_type_code: Mapped[str] = mapped_column(String(50))
    title: Mapped[str | None] = mapped_column(String(200))
    file_path: Mapped[str | None] = mapped_column(String(400))
    mime: Mapped[str | None] = mapped_column(String(100))
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    extracted_data_json: Mapped[dict | None] = mapped_column(JSON)  # نتيجة OCR (مقترحة)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    # Immutable Artifact Metadata
    is_issued: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    reference_no: Mapped[str | None] = mapped_column(String(60), unique=True, index=True)
    template_version: Mapped[int | None] = mapped_column(Integer)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime)
    generated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    signature_version: Mapped[int | None] = mapped_column(Integer)
    # R8 §2 — Dynamic Custom Documents: يفعّل تنبيهات قبل الانتهاء لمستندات مخصّصة
    notify_on_expiry: Mapped[bool] = mapped_column(Boolean, default=False)
    # RNW-08 — النسخة الموقّعة تشير إلى النسخة المولّدة التي وُقّعت بالضبط.
    # الربط بالمعاملة وحدها لا يكفي: إعادة التوليد تُنشئ إصدارًا جديًدا، فلو
    # أعاد المندوب التوليد بعد الإرسال لم يعد أحد يعرف أي نسخة وقّعها الموظف
    # فعًلا — وهو سؤال يُطرح حين تعترض جهة رسمية على المستند.
    source_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id"), nullable=True, index=True)


class Task(Base):
    """محرّك المهام/الإشعارات — كل صلاحية قاربت على الانتهاء = مهمة لها مسؤول."""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(250))
    detail: Mapped[str | None] = mapped_column(Text)
    assignee_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    related_entity_type: Mapped[str | None] = mapped_column(String(30))
    related_entity_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open/in_progress/done/dismissed
    severity: Mapped[str] = mapped_column(String(20), default="info")  # info/warning/critical
    due_date: Mapped[date | None] = mapped_column(Date)
    dedup_key: Mapped[str | None] = mapped_column(String(120), index=True)  # لمنع التكرار
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    # سجل التسليم (FIX-004): قالب الإشعار المُستخدَم والقناة الفعلية للإرسال
    template_code: Mapped[str | None] = mapped_column(String(50))
    channel: Mapped[str | None] = mapped_column(String(20))
    # V1.5 Phase 3 — Claim/Delegate/SLA (V2.2 §3.2 Approver/Executor lifecycle):
    # المهمة الموزعة على مجموعة أدوار (مثل all HR) يجب أن "يلتقطها" مستخدم واحد قبل
    # التنفيذ لمنع التكرار — القيمة تُملأ عبر POST /api/tasks/{id}/claim.
    claimed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime)
    # مهلة الاستجابة المتوقعة (SLA) — يُملأ من قالب الإشعار عند الإنشاء؛ يستخدمه
    # المجدول لإصدار مهام تصعيد إن انقضى دون تنفيذ.
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime)
    escalation_task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))
    # V2.2 §20 — تتبّع محاولات التسليم للقنوات الخارجية (email/SMS/webhook).
    #   in_app دائمًا 1 محاولة (الإدراج في الجدول). القنوات الأخرى قد تفشل
    #   وتعاد المحاولة مع سقف أقصى.
    delivery_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_delivery_error: Mapped[str | None] = mapped_column(String(400))
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime)


class FeatureFlag(Base):
    """V1.5 Phase 5 — Feature flag لكل شركة (V1.5 §3 الترحيل الآمن).

    كل شركة تُدار مستقلة خلال فترة الانتقال من التصميم القديم إلى canonical V1.5:
    - `key`: اسم الميزة (`v15_canonical_display`, `v15_status_labels`, ...)
    - `company_id`: NULL للتفعيل العام؛ رقم شركة للتفعيل الخاص بها فقط
    - `value`: "on" / "off" / JSON لتكوينات معقّدة
    - القاعدة: القيمة الخاصة بالشركة تعلو على العام؛ والعام يعلو على default الكود

    يُدير القيم super_admin فقط عبر `/api/feature-flags`؛ لا يتعامل معها المستخدم مباشرة.
    """
    __tablename__ = "feature_flags"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    value: Mapped[str] = mapped_column(String(500))
    note: Mapped[str | None] = mapped_column(String(250))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class ApprovalDelegation(Base):
    """V1.5 Phase 3 — تفويض مؤقت لصلاحية الاعتماد (V2.2 Approver actions: تفويض مؤقت).

    مثال استخدام: مدير في إجازة لفترة محددة يفوّض نائبه لاعتماد طلبات فريقه فقط —
    محرك الـ workflow يعامل التفويض كإضافة للـ approvers الحاليين لكل مسار، مع تسجيل
    كل قرار باسم المفوَّض إليه وذكر أن التفويض من الأصلي في سجل التدقيق.
    """
    __tablename__ = "approval_delegations"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    delegator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    delegate_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reason: Mapped[str | None] = mapped_column(String(250))
    starts_at: Mapped[datetime] = mapped_column(DateTime)
    ends_at: Mapped[datetime] = mapped_column(DateTime)
    # نطاق التفويض: 'all' لجميع الطلبات ضمن صلاحيات المفوِّض، أو قائمة أنواع طلب محددة
    scope: Mapped[str] = mapped_column(String(20), default="all")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class RequestType(Base):
    __tablename__ = "request_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(150))
    # تصنيف النوع (حضور وإجازات / إقامة ومعاملات حكومية / بيانات وتوثيق / شهادات / مالية /
    # شكاوى وتظلمات / عام / تطوير وظيفي / عقود وإنهاء خدمة / نماذج إدارية) — حزمة V1.3
    category: Mapped[str | None] = mapped_column(String(60))
    # سلسلة المراحل: [{order, label, approver_role, produces_document, requires_signature, ...}]
    approval_chain_json: Mapped[list] = mapped_column(JSON, default=list)
    requires_physical_signature: Mapped[bool] = mapped_column(Boolean, default=False)
    produces_document: Mapped[bool] = mapped_column(Boolean, default=False)
    template_html: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # سرّية (FIX-014): يمنع تجاوز المدير العام/المالك الاعتيادي لمراحل هذا النوع، ويقصر
    # الاطلاع والقرار على معتمدي المرحلة الفعليين (مثل الشؤون القانونية) + الإدارة العليا فقط.
    is_confidential: Mapped[bool] = mapped_column(Boolean, default=False)
    # هل يظهر هذا النوع في قائمة "طلب جديد" للموظف كخدمة ذاتية (P0-06)؟ الإجراءات الداخلية
    # (نماذج ADM* وما يبدأ من HR/الإدارة/المندوب/PRO بشأن الموظف) لا تظهر له لأنه لا يبدأها بنفسه.
    visible_to_employee: Mapped[bool] = mapped_column(Boolean, default=False)
    # ربط تتبّعي اختياري بأحد قوالب الطباعة الرسمية HRMS-PR-001..042 (P0-02) — ليس كل نوع
    # طلب له قالب مطابق (49+ نوعًا مقابل 42 قالبًا)، فيبقى None حين لا يوجد تطابق مناسب.
    default_template_code: Mapped[str | None] = mapped_column(String(20))
    # V2.2/§4 — Form Schema Engine: تعريف الحقول والتحقق الشرطي والمرفقات لكل نوع.
    #   الواجهة والـBackend يستهلكانه معًا؛ لا Forms مبنية بالخطأ (Date/Amount/Details) لكل نوع.
    #   الشكل: {"fields": [...], "conditional": [...], "attachments": {...}, "meta": {...}}
    form_schema_json: Mapped[dict | None] = mapped_column(JSON)


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    requester_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    request_type_code: Mapped[str] = mapped_column(String(50))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # V2.2 §13.8 (AC-08) + RW-18 — لقطة القواعد الفاعلة لحظة الإرسال.
    # تعديل سياسة بعد الإرسال يجب ألّا يغيّر الطلب القائم: من قدّم مصروًفا تحت
    # الحد القديم لا تُضاف له مرحلة اعتماد ظهرت بعده. وبلا اللقطة يستحيل بعد
    # شهور تفسير لماذا مرّ هذا الطلب بمرحلتين وذاك بثلاث.
    policy_snapshot_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    current_stage: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    # V2.2/§5 Workflow Engine: needs_info + cancel + return_to_submitter
    needs_info_note: Mapped[str | None] = mapped_column(Text)
    cancelled_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime)
    cancel_reason: Mapped[str | None] = mapped_column(String(300))


class RequestApproval(Base):
    __tablename__ = "request_approvals"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"), index=True)
    stage_order: Mapped[int] = mapped_column(Integer)
    stage_label: Mapped[str] = mapped_column(String(150))
    approver_role: Mapped[str | None] = mapped_column(String(30))
    approver_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(20))  # approved/rejected
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    note: Mapped[str | None] = mapped_column(Text)


class RequestDocument(Base):
    __tablename__ = "request_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # generated_pdf/signed_scan/exit_permit/...
    file_path: Mapped[str | None] = mapped_column(String(400))
    version: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    # دورة حياة الطباعة/الأرشفة (FIX-008): READY_TO_PRINT → PRINTED → FILED
    print_status: Mapped[str] = mapped_column(String(20), default="ready_to_print")
    printed_at: Mapped[datetime | None] = mapped_column(DateTime)
    printed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    filed_at: Mapped[datetime | None] = mapped_column(DateTime)
    filed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    # V1.5 Phase 4 — canonical document code (OD-001..OD-025) بجانب legacy print_status
    od_code: Mapped[str | None] = mapped_column(String(10), index=True)
    # دورة حياة المستند V1.5 (منفصلة عن حالة الطلب):
    # NOT_REQUIRED → QUEUED → GENERATING → GENERATED → SIGNED → DELIVERED → ARCHIVED
    lifecycle_status: Mapped[str] = mapped_column(String(20), default="GENERATED")
    # V2.2 §13 — Immutable Artifact: بصمة SHA256 للملف تُحسب عند التوليد وتبقى ثابتة
    # لإثبات عدم التلاعب. Reference Number مقروء بشريًا للمستند.
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    reference_no: Mapped[str | None] = mapped_column(String(40), unique=True, index=True)
    signature_version: Mapped[int | None] = mapped_column(Integer)
    # V2.2 §30 (DOC-20) — نسخة القالب التي وُلِّد بها هذا المستند.
    # القالب يتطوّر والمستند الصادر يبقى، وحُجّيته على نصّه لا على نصّ اليوم:
    # بلا هذين العمودين يستحيل بعد شهور إثبات بأي نصٍّ صدرت شهادةٌ بعينها.
    template_code: Mapped[str | None] = mapped_column(String(50))
    template_version: Mapped[int | None] = mapped_column(Integer)
    # V2.2 §30 (DOC-10) — إلغاء مستند: **الملف لا يُحذف**.
    # مستند صدر ووصل جهة خارجية لا يُمحى من الوجود بضغطة؛ محوُه يُفقد القدرة
    # على إثبات ما صدر ولمن. يُوسَم ملغى، ويُعلن رمز التحقق ذلك لمن يفحصه.
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime)
    revoked_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    revocation_reason: Mapped[str | None] = mapped_column(String(300))


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("requests.id"))
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime)
    location: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")  # scheduled/done/missed


class AttendanceMonthClose(Base):
    """V2.2 §17 — قفل شهر حضور: بعد اعتماد كل التصحيحات، يُقفَل الشهر لتأمين مصدر بيانات
    الرواتب. أي تصحيح لاحق يحتاج فتح صريح من HR + سبب مسجَّل في audit.
    """
    __tablename__ = "attendance_month_closes"
    __table_args__ = (
        UniqueConstraint("company_id", "period", name="uq_att_close_company_period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    period: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    status: Mapped[str] = mapped_column(String(20), default="closed")  # closed/reopened
    closed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    reopened_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime)
    reopen_reason: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))
    check_in_at: Mapped[datetime | None] = mapped_column(DateTime)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime)
    method: Mapped[str] = mapped_column(String(10), default="qr")  # qr/gps/manual
    in_lat: Mapped[float | None] = mapped_column(Float)
    in_lng: Mapped[float | None] = mapped_column(Float)
    out_lat: Mapped[float | None] = mapped_column(Float)
    out_lng: Mapped[float | None] = mapped_column(Float)
    selfie_in_path: Mapped[str | None] = mapped_column(String(400))
    selfie_out_path: Mapped[str | None] = mapped_column(String(400))
    status: Mapped[str] = mapped_column(String(20), default="present")  # present/late/early_leave/absent
    worked_minutes: Mapped[int] = mapped_column(Integer, default=0)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Leave(Base):
    __tablename__ = "leaves"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    request_id: Mapped[int | None] = mapped_column(ForeignKey("requests.id"))
    leave_type: Mapped[str] = mapped_column(String(30), default="annual")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    days: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(20), default="approved")


class EmployeeEvent(Base):
    """أحداث الموارد البشرية على الموظف: إنذار/جزاء/مكافأة/ترقية/ملاحظة."""
    __tablename__ = "employee_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # warning/penalty/bonus/promotion/note
    title: Mapped[str] = mapped_column(String(200))
    detail: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[float | None] = mapped_column(Float)  # للجزاء/المكافأة
    date: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Deduction(Base):
    __tablename__ = "deductions"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    amount: Mapped[float] = mapped_column(Float, default=0)
    reason: Mapped[str | None] = mapped_column(String(250))
    ded_type: Mapped[str] = mapped_column(String(30), default="violation")
    date: Mapped[date | None] = mapped_column(Date)


class PayrollRun(Base):
    __tablename__ = "payroll_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    period: Mapped[str] = mapped_column(String(30))  # YYYY-MM أو YYYY-MM-ADJ-<id> للتسويات
    status: Mapped[str] = mapped_column(String(20), default="prepared")
    totals_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # PILOT-P0-7 — دورة الاعتماد المتدرجة (فصل السلطات)
    prepared_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    finalized_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime)
    locked_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime)
    # Adjustment run بعد قفل الفترة الأصلية
    adjustment_of_run_id: Mapped[int | None] = mapped_column(ForeignKey("payroll_runs.id"))
    adjustment_reason: Mapped[str | None] = mapped_column(Text)


class GovernmentPortal(Base):
    """R8 §1 — روابط المواقع الحكومية للمندوب (PRO). قابلة للتعديل من الإدارة بلا كود.

    مثال: PACI (بطاقة مدنية)، Sahel، PIFSS، Ministry of Commerce، إلخ.
    الترتيب داخل كل فئة يتحكم فيه sort_order (أصغر يظهر أولاً).
    """
    __tablename__ = "government_portals"

    id: Mapped[int] = mapped_column(primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str | None] = mapped_column(String(200))
    description_ar: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(500))
    # فئات: residency / work_permits / civil_id / moci / municipality / insurance / other
    category: Mapped[str] = mapped_column(String(30), default="other", index=True)
    icon: Mapped[str | None] = mapped_column(String(60))  # emoji أو icon name اختياري
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class SalaryChangeRequest(Base):
    """R7-G §4 — طلب اعتماد لتغيير الراتب أو تاريخ التعيين أو العقد.

    HR تقترح تغييرًا (proposed_by) — يبقى في status="pending" — ثم مدير الشركة
    أو الإدارة العليا يعتمد (approved_by) → يُطبَّق على الموظف + يُنشأ صف
    EmployeeFieldChange نهائي. طالب الاعتماد لا يقدر يعتمد نفسه (فصل واجبات).
    """
    __tablename__ = "salary_change_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    field_name: Mapped[str] = mapped_column(String(40))  # basic_salary / actual_salary / hire_date / job_title / contract_type
    old_value: Mapped[str | None] = mapped_column(String(200))
    new_value: Mapped[str] = mapped_column(String(200))
    effective_date: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending/approved/rejected/applied
    proposed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    proposed_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)
    rejected_reason: Mapped[str | None] = mapped_column(Text)
    applied_change_id: Mapped[int | None] = mapped_column(ForeignKey("employee_field_changes.id"))


class UserTourState(Base):
    """R5 §3 — حالة إكمال الجولة التعليمية لكل (مستخدم × مفتاح جولة).

    tour_key يميّز الجولة (عادةً "role:{role}:v1") — بحيث لو أُصدرت نسخة جديدة من
    جولة دور معيّن، تُعتبر جولة جديدة ويظهر onboarding مرة أخرى.
    مسار Replay: DELETE (أو reset) يمسح السجل → الجولة تظهر تلقائيًا مجددًا.
    """
    __tablename__ = "user_tour_states"
    __table_args__ = (
        UniqueConstraint("user_id", "tour_key", name="uq_tour_user_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tour_key: Mapped[str] = mapped_column(String(60), index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)  # تمييز "تجاوز" عن "أكمل"
    step_reached: Mapped[int | None] = mapped_column(Integer)  # آخر خطوة وصلها (لو skip)


class EmployeeFieldChange(Base):
    """R3-C §4 — سجل نسخي للتغييرات الحرجة على ملف الموظف.

    مختلف عن AuditLog:
      - AuditLog: كل الأحداث (login/print/export/...) — عام
      - EmployeeFieldChange: فقط الحقول المالية/التعاقدية (basic_salary, actual_salary,
        hire_date, job_title, contract_type)، مع effective_date منفصل عن changed_at
        (لأن الشركة قد تسجّل زيادة راتب اليوم تسري الشهر القادم).

    يُقرأ عبر GET /employees/{id}/change-history لعرض تاريخ التغييرات في ملف الموظف.
    """
    __tablename__ = "employee_field_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"), index=True)
    field_name: Mapped[str] = mapped_column(String(40))  # basic_salary, hire_date, ...
    old_value: Mapped[str | None] = mapped_column(String(200))  # serialized (JSON/str)
    new_value: Mapped[str | None] = mapped_column(String(200))
    effective_date: Mapped[date] = mapped_column(Date)  # متى يسري التغيير (قد يكون بالمستقبل)
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=_now)  # متى سُجِّل التغيير
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str | None] = mapped_column(Text)


class Transfer(Base):
    """نقل موظف بين شركتين مع سجل تاريخي."""
    __tablename__ = "transfers"

    id: Mapped[int] = mapped_column(primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    from_company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    to_company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    transferred_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class DocumentTemplate(Base):
    """صيغة/نموذج قابل للتعبئة التلقائية ثم الطباعة (خطابات، شهادات، نماذج)."""
    __tablename__ = "document_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str | None] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    name_en: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60), default="عام")
    body_html: Mapped[str] = mapped_column(Text)  # نص الصيغة مع متغيّرات {{...}}
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # R1-A §8 — عداد نسخة القالب: يُزاد عند كل تعديل، ويُختم على كل مستند مُولّد
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AuthorizedSignatory(Base):
    """SEC2-15 — سجل المخوّلين بالتوقيع (Authorized Signatories Registry).

    مصدر الحقيقة الذي يُستعلَم منه توليد كل مستند رسمي (شهادة/خطاب/عقد/طلب) عند
    وضع خانة "المخول بالتوقيع". يمنع طباعة أي مستند رسمي بدون توقيع مُعتمَد.

    scope_type:
      - "any"        → مخول عام لكل مستندات الشركة
      - "code"       → مقيَّد برمز مستند/طلب محدد (HRMS-PR-001, REQEOS...)
      - "prefix"     → مقيَّد بمجموعة رموز (مثل HRMS-PR-00* للشهادات)
      - "category"   → مقيَّد بفئة (شهادات، عقود، إجراءات إدارية...)

    الفترة الزمنية effective_from/effective_to لدعم تفويض مؤقت (إجازة/سفر...).
    """
    __tablename__ = "authorized_signatories"
    __table_args__ = (
        UniqueConstraint("company_id", "user_id", "scope_type", "scope_value",
                         name="uq_signatory_scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title_ar: Mapped[str] = mapped_column(String(120))  # مثل: المدير العام
    title_en: Mapped[str | None] = mapped_column(String(120))
    scope_type: Mapped[str] = mapped_column(String(20), default="any")
    scope_value: Mapped[str | None] = mapped_column(String(80))
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class DocumentTemplateVersion(Base):
    """V2.2 §14 — سجل نسخ القوالب: كل تعديل يُنشئ نسخة جديدة والقديمة تُحفظ للأرشيف.
    المستندات المصدَرة قبل التعديل تشير للنسخة التي أُصدرت بها (immutable audit trail)."""
    __tablename__ = "document_template_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("document_templates.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    body_html: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60))
    edited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    edited_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    change_note: Mapped[str | None] = mapped_column(String(300))


class GovLog(Base):
    """سجلّ معاملات المندوب الحكومية: ملاحظات وتجديدات على الإقامات/التراخيص."""
    __tablename__ = "gov_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(20))  # permit / license
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(20), default="note")  # note / renew
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class ConsumedToken(Base):
    """منع إعادة استخدام رموز QR وتذاكر التسجيل (anti-replay)."""
    __tablename__ = "consumed_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    kind: Mapped[str] = mapped_column(String(20))  # qr / checkin_ticket
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class NotificationTemplate(Base):
    """قالب إشعار مُسمّى (FIX-004) — 74 قالبًا تغطي كل أحداث دورة حياة الطلبات والنظام.

    body_text يدعم متغيّرات {{...}} تُعبَّأ عند الإرسال (نفس أسلوب DocumentTemplate).
    channel_default: in_app / whatsapp / sms / email. sla_hours: مهلة الاستجابة المتوقعة
    (لتصعيد المهمة إن لم تُعالَج، تُستخدم من المسح اليومي).
    """
    __tablename__ = "notification_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(60))
    event_type: Mapped[str] = mapped_column(String(40))  # يطابق Task.type
    channel_default: Mapped[str] = mapped_column(String(20), default="in_app")
    sla_hours: Mapped[int | None] = mapped_column(Integer)
    body_text: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class NotificationPreference(Base):
    """تفضيل تسليم الإشعارات لكل مستخدم حسب الفئة (قناة مفعّلة أم لا)."""
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", "category", "channel", name="uq_notif_pref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(60))
    channel: Mapped[str] = mapped_column(String(20))  # in_app / whatsapp / sms / email
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RevokedToken(Base):
    """رمز أُبطل قبل انتهاء صلاحيته.

    JWT بطبيعته لا يُسترجع: من حمله ظلّ صالًحا حتى انقضاء مدّته مهما فعل
    صاحبه. فكان «تسجيل الخروج» يمسح الرمز من المتصفح ولا يمسّ الرمز نفسه —
    يبقى صالًحا نصف ساعة، ورمز التجديد أربعة عشر يوًما. والزرّ يقول إن
    الجلسة انتهت وهي لم تنتهِ.

    والبديل الأسهل — رفع ``tokens_valid_after`` — مرفوض عمًدا: يُخرج
    المستخدم من كل أجهزته، وفي حالة الانتحال يعاقب المُنتحَل على فعل غيره
    (انظر deps.py:48). الإبطال هنا **لرمز بعينه** لا لمستخدم.

    والصفّ يُحذف بعد ``expires_at``: بعدها يرفض الرمزَ انتهاءُ مدّته نفسه،
    فحفظه بلا معنى ونموّ الجدول بلا حدّ ثمن بلا مقابل.
    """

    __tablename__ = "revoked_tokens"

    #: jti الرمز — المفتاح نفسه، فالإدراج المكرّر مستحيل والبحث فهرسيّ.
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    #: متى تنتهي صلاحية الرمز أصًلا — بعدها يُحذف الصفّ
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    #: logout | impersonate_end — يشرح السجل نفسه عند التفتيش
    reason: Mapped[str | None] = mapped_column(String(40))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(Integer, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(50))
    # V2.2 §21 — تدقيق موسَّع:
    #   - original_user_id: هوية الفاعل الحقيقي عند الانتحال (impersonation)
    #   - user_agent: عميل المتصفح المستخدم
    #   - correlation_id: ربط أحداث نفس الطلب/الجلسة
    #   - before_json / after_json: حالة الكيان قبل وبعد التعديل
    original_user_id: Mapped[int | None] = mapped_column(Integer)
    user_agent: Mapped[str | None] = mapped_column(String(400))
    correlation_id: Mapped[str | None] = mapped_column(String(80), index=True)
    before_json: Mapped[dict | None] = mapped_column(JSON)
    after_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class LeaveLedger(Base):
    """سجل حركات رصيد الإجازة السنوية.

    الرصيد كان عمودًا واحدًا (annual_leave_balance) لا يُخصم منه شيء أصلًا، ولو
    خُصم لما أمكن تفسير الرقم: كم كان، ومتى تغيّر، وبأي طلب. كل حركة تُسجَّل هنا
    بالرصيد قبلها وبعدها، فالرقم الحالي قابل لإعادة البناء من السجل والاعتراض
    عليه يُحسم بمستند.

    الإجازة السنوية وحدها تُخصم: المرضية والطارئة وبدون راتب لها أحكامها ولا
    تُنقص الرصيد السنوي.
    """
    __tablename__ = "leave_ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(Integer, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="CASCADE"),
                                             index=True)
    # deduction = استهلاك إجازة، grant = رصيد سنوي جديد، adjustment = تسوية يدوية
    kind: Mapped[str] = mapped_column(String(20))
    days: Mapped[float] = mapped_column(Float)          # موجب دائًما؛ الاتجاه من kind
    balance_before: Mapped[float] = mapped_column(Float)
    balance_after: Mapped[float] = mapped_column(Float)
    leave_type: Mapped[str | None] = mapped_column(String(30))
    request_id: Mapped[int | None] = mapped_column(Integer, index=True)
    leave_id: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class PolicyRule(Base):
    """V2.2 §7 (STR-05) — حدود السياسة بياًنا لا كوًدا.

    ROOT CAUSE: الحدود المالية والمدد كانت إمّا مزروعة في الكود أو غير موجودة
    أصًلا. فمرحلة "اعتماد فوق الحد" (RW-07) لم يكن لها وجود لأن الحد نفسه لم
    يكن له وجود، وتغيير مهلة الإنذار يعني نشر إصدار جديد.

    القاعدة تُنسخ ولا تُعدَّل: تعديل حدٍّ يُنشئ صًفا جديًدا بإصدار أعلى ويُنهي
    سريان القديم. الطلبات القائمة تحتفظ بلقطتها (policy_snapshot_json)، فيبقى
    قرار قديم مفهوًما على ضوء القاعدة التي حكمته لا القاعدة الحالية.

    company_id = NULL ⇒ قاعدة عامة (افتراضي المنصّة)؛ صف الشركة يتقدّم عليها.
    """
    __tablename__ = "policy_rules"
    __table_args__ = (
        UniqueConstraint("company_id", "key", "version", name="uq_policy_rule_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    key: Mapped[str] = mapped_column(String(80), index=True)
    value_json: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(300))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class BreakGlassSession(Base):
    """V2.2 §13.5 (AC-05) — نافذة تجاوز طارئة لـSuper Admin، موقّتة وموثّقة.

    ROOT CAUSE: ``has_permission`` تعيد True لـsuper_admin مطلًقا، فيملك
    ``override_approval`` دائًما ويعتمد أي مرحلة عمل بلا أن يطلبها أحد ولا أن
    ينتبه إليها أحد. الحساب التقني صار معتمًِدا تجارًيا بحكم الأمر الواقع.

    القاعدة: التجاوز يبقى ممكًنا — منعه كلًيا يشلّ النظام حين يتعطّل الإسناد —
    لكنه يصير حدًثا: بسبب مكتوب، ومدة تنتهي وحدها، وسجل يُراجَع.
    نافذة مفتوحة إلى الأبد ليست تجاوًزا طارًئا بل صلاحية دائمة بثوب آخر.
    """
    __tablename__ = "break_glass_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    reason: Mapped[str] = mapped_column(String(400))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    uses: Mapped[int] = mapped_column(Integer, default=0)


# ===========================================================================
# QA-26 — لا سجل تدقيق بلا فاعل ولا IP.
#
# ROOT CAUSE: سجلات محرّك المسار (request_completed / request_apply_success /
# request_apply_failed) تُكتب داخل _finalize، ولا يصلها user ولا Request عبر
# سلسلة enter_stage → _advance، فكانت تُحفظ بـuser_id=None وip=None. تمرير
# الفاعل يدوًيا في كل نداء يعالج المواضع الثلاثة اليوم ويعود العطل مع أول
# مسار جديد؛ فالتعبئة هنا عند الإدراج، مصدًرا واحًدا لكل كتابة قائمة ومقبلة.
#
# لا يُدهس ما مُرِّر صراحًة — القيمة الصريحة أدق دائًما من سياق الطلب.
# ===========================================================================
@event.listens_for(AuditLog, "before_insert")
def _fill_audit_actor(mapper, connection, target: "AuditLog") -> None:  # noqa: ARG001
    from .audit_context import get_actor

    actor = get_actor()
    if target.user_id is None:
        target.user_id = actor.get("user_id")
    if target.ip is None:
        target.ip = actor.get("ip")
    if target.user_agent is None:
        target.user_agent = actor.get("user_agent")
