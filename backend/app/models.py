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
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"))  # للخدمة الذاتية
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/inactive/suspended/locked
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime)
    last_login: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    permissions: Mapped[list[UserPermission]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


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
    job_title: Mapped[str | None] = mapped_column(String(150))
    basic_salary: Mapped[float] = mapped_column(Float, default=0)
    hire_date: Mapped[date | None] = mapped_column(Date)
    contract_type: Mapped[str] = mapped_column(String(20), default="indefinite")  # indefinite/definite
    status: Mapped[str] = mapped_column(String(20), default="active")
    license_id: Mapped[int | None] = mapped_column(ForeignKey("licenses.id"))
    branch_id: Mapped[int | None] = mapped_column(ForeignKey("branches.id"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    shift_id: Mapped[int | None] = mapped_column(ForeignKey("shifts.id"))
    attendance_mode: Mapped[str] = mapped_column(String(10), default="none")  # none/qr/gps/both
    annual_leave_balance: Mapped[float] = mapped_column(Float, default=30)
    phone: Mapped[str | None] = mapped_column(String(30))
    photo: Mapped[str | None] = mapped_column(String(300))
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
    """مستند بنُسخ/تأريخ — الأحدث is_current=True والقديم محفوظ."""
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


class RequestType(Base):
    __tablename__ = "request_types"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(150))
    # سلسلة المراحل: [{order, label, approver_role, produces_document, requires_signature, ...}]
    approval_chain_json: Mapped[list] = mapped_column(JSON, default=list)
    requires_physical_signature: Mapped[bool] = mapped_column(Boolean, default=False)
    produces_document: Mapped[bool] = mapped_column(Boolean, default=False)
    template_html: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    requester_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    request_type_code: Mapped[str] = mapped_column(String(50))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    current_stage: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)


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
    period: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    status: Mapped[str] = mapped_column(String(20), default="draft")
    totals_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


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
    category: Mapped[str] = mapped_column(String(60), default="عام")
    body_html: Mapped[str] = mapped_column(Text)  # نص الصيغة مع متغيّرات {{...}}
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
