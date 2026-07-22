# -*- coding: utf-8 -*-
"""مخططات Pydantic للتحقق من المدخلات وتسلسل المخرجات."""
from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ----------------------------- المصادقة -----------------------------


def _check_password_strength(v: str) -> str:
    """سياسة كلمة مرور دنيا (تدقيق أمني): 8 أحرف على الأقل، وتحتوي حرًفا ورقًما معًا —
    تمنع كلمات مرور ضعيفة مثل أرقام بحتة أو كلمات قصيرة يسهل تخمينها."""
    if len(v) < 8:
        raise ValueError("كلمة المرور يجب ألا تقل عن 8 أحرف")
    if not re.search(r"[A-Za-z؀-ۿ]", v):
        raise ValueError("كلمة المرور يجب أن تحتوي حرًفا واحدًا على الأقل")
    if not re.search(r"\d", v):
        raise ValueError("كلمة المرور يجب أن تحتوي رقًما واحدًا على الأقل")
    return v


class LoginIn(BaseModel):
    civil_id: str
    password: str
    # V2.2 §9 — رمز TOTP الاختياري في نفس الطلب (لتقليل الـround-trip للأدوار الحساسة).
    #   لو 2FA مفعّل ولم يُمرَّر، يعود 401 مع requires_2fa=true؛ الواجهة تعرض حقل الرمز
    #   وتُعيد الإرسال. الرمز 6 خانات وصالح ±30 ثانية.
    totp_code: str | None = None


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_change_password: bool
    role: str
    full_name: str | None = None
    company_id: int | None = None
    permissions: list[str] = []


class RefreshIn(BaseModel):
    refresh_token: str


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)

    _check_new_password = field_validator("new_password")(_check_password_strength)


class ResetPasswordIn(BaseModel):
    user_id: int
    new_password: str | None = None  # إن لم تُحدّد تُستخدم الافتراضية

    @field_validator("new_password")
    @classmethod
    def _check_new_password(cls, v: str | None) -> str | None:
        return _check_password_strength(v) if v else v


# ----------------------------- الشركات -----------------------------

class CompanyIn(BaseModel):
    name: str
    name_en: str | None = None
    commercial_reg: str | None = None
    entity_type: str | None = None
    eos_day_divisor: int = 26
    eos_max_months: int = 18
    alert_lead_days: int = 30
    annual_leave_days: int = 30


class CompanyOut(CompanyIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str


# ----------------------------- المستخدمون -----------------------------

class UserIn(BaseModel):
    civil_id: str
    full_name: str | None = None
    role: str = "employee"
    company_id: int | None = None
    email: str | None = None
    phone: str | None = None
    employee_id: int | None = None
    password: str | None = None  # إن لم تُحدّد تُستخدم الافتراضية

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str | None) -> str | None:
        return _check_password_strength(v) if v else v


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    civil_id: str
    full_name: str | None
    role: str
    company_id: int | None
    email: str | None
    phone: str | None
    is_active: bool
    status: str = "active"
    scope_level: str = "company"
    scope_branch_id: int | None = None
    must_change_password: bool


class PermissionAssignIn(BaseModel):
    perm_codes: list[str]
    expires_at: date | None = None


class CopyPermsIn(BaseModel):
    from_user_id: int
    to_user_id: int


class MatrixIn(BaseModel):
    # {صفحة: [أفعال مسموحة]} — كل صفحة مذكورة تصبح مُدارة صراحةً
    grants: dict[str, list[str]]


# ----------------------------- الموظفون -----------------------------

class EmployeeIn(BaseModel):
    company_id: int | None = None  # تُستخدم من الإدارة العليا/المالك لاختيار الشركة
    civil_id: str | None = None
    name: str
    name_en: str | None = None
    nationality: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    marital_status: str | None = None
    email: str | None = None
    passport_number: str | None = None
    passport_expiry: date | None = None
    health_insurance: str | None = None
    direct_manager_id: int | None = None
    worker_type: str | None = None
    job_title: str | None = None
    basic_salary: float = 0                 # الراتب الرسمي (عقد/حكومي)
    hire_date: date | None = None
    contract_type: str = "indefinite"
    license_id: int | None = None           # الترخيص الرسمي
    actual_license_id: int | None = None    # ترخيص الدوام الفعلي
    branch_id: int | None = None            # الفرع الرسمي
    actual_branch_id: int | None = None     # فرع الدوام الفعلي
    department_id: int | None = None
    shift_id: int | None = None
    attendance_mode: str = "none"
    annual_leave_balance: float = 30
    phone: str | None = None
    # SEC2-17 — إعفاء صريح من الحضور (مثل المدير/المندوب/الحقلي بلا Shift)
    attendance_exempt: bool = False
    attendance_exempt_reason: str | None = None

    @field_validator("civil_id")
    @classmethod
    def _civil(cls, v):
        if v and not (v.isdigit() and 6 <= len(v) <= 12):
            raise ValueError("الرقم المدني يجب أن يكون أرقامًا (6 إلى 12 خانة)")
        return v

    @field_validator("basic_salary", "annual_leave_balance")
    @classmethod
    def _non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("القيمة لا يمكن أن تكون سالبة")
        return v

    @field_validator("attendance_mode")
    @classmethod
    def _mode(cls, v):
        if v not in ("none", "qr", "gps", "both"):
            raise ValueError("نمط حضور غير صالح")
        return v


class EmployeeOut(EmployeeIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_id: int
    status: str
    # PILOT-P0-6 — الرقم الوظيفي المرئي (read-only، مولَّد تلقائيًا)
    employee_no: str | None = None


class EmployeeCreateIn(EmployeeIn):
    """مخطط الإنشاء/التعديل — يفرض هوية وبيانات وظيفية أساسية (QA-P1-EMP-01): لا يُستخدم
    للعرض (EmployeeOut) حتى لا تُطبَّق هذه القيود الصارمة على سجلات قديمة مقروءة من القاعدة
    قد تسبق هذا التشديد وتكسر استجابة القراءة بالكامل."""
    civil_id: str
    name: str

    @field_validator("civil_id")
    @classmethod
    def _civil_required(cls, v):
        if not v or not v.strip() or not (v.isdigit() and 6 <= len(v) <= 12):
            raise ValueError("الرقم المدني مطلوب ويجب أن يكون أرقامًا (6 إلى 12 خانة)")
        return v

    @field_validator("name")
    @classmethod
    def _name_required(cls, v):
        if not v or not v.strip():
            raise ValueError("اسم الموظف مطلوب")
        return v.strip()

    @field_validator("basic_salary")
    @classmethod
    def _salary_required(cls, v):
        if not v or v <= 0:
            raise ValueError("الراتب الأساسي مطلوب ويجب أن يكون أكبر من صفر")
        return v

    @model_validator(mode="after")
    def _attendance_policy_required(self):
        """SEC2-17 — إن كان attendance_exempt صريحًا يجب سبب موثّق. النمط "none" الافتراضي
        الصامت يُترك للتوافق العكسي، ويُفرَض تحويله عبر endpoint مخصّص قبل التشغيل."""
        if self.attendance_exempt:
            if not (self.attendance_exempt_reason and self.attendance_exempt_reason.strip()):
                raise ValueError("الإعفاء من الحضور يتطلب سببًا صريحًا (attendance_exempt_reason)")
        return self


class OcrApplyIn(BaseModel):
    """بيانات OCR بعد مراجعة المستخدم — تُطبَّق على ملف الموظف."""
    name: str | None = None
    civil_id: str | None = None
    nationality: str | None = None
    date_of_birth: date | None = None
    passport_number: str | None = None
    passport_expiry: date | None = None
    job_title: str | None = None
    basic_salary: float | None = None


# ----------------------------- الفروع والورديات -----------------------------

class BranchIn(BaseModel):
    name: str
    latitude: float | None = None
    longitude: float | None = None
    geofence_radius_m: int = 100
    auto_checkout_minutes: int = 15
    address: str | None = None


class BranchOut(BranchIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    company_id: int


class ShiftIn(BaseModel):
    name: str
    start_time: time = time(8, 0)
    end_time: time = time(17, 0)
    work_days: str = "0,1,2,3,4"
    grace_minutes: int = 15


# ----------------------------- الحضور -----------------------------

class ValidateQrIn(BaseModel):
    qr_token: str
    lat: float | None = None
    lng: float | None = None


# ----------------------------- المهام -----------------------------

class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: str
    title: str
    detail: str | None
    status: str
    severity: str
    due_date: date | None
    related_entity_type: str | None
    related_entity_id: int | None
    created_at: datetime


# ----------------------------- الطلبات -----------------------------

class RequestTypeIn(BaseModel):
    code: str
    name: str
    category: str | None = None
    approval_chain_json: list[dict[str, Any]] = []
    requires_physical_signature: bool = False
    produces_document: bool = False
    template_html: str | None = None
    is_confidential: bool = False
    visible_to_employee: bool = False
    default_template_code: str | None = None


class RequestIn(BaseModel):
    employee_id: int | None = None  # إن لم يُحدّد يُؤخذ من حساب الموظف
    request_type_code: str
    payload_json: dict[str, Any] = {}


class ApprovalDecisionIn(BaseModel):
    decision: str  # approved / rejected
    note: str | None = None


class AppointmentIn(BaseModel):
    scheduled_at: datetime
    location: str | None = None


# ----------------------------- مكافأة نهاية الخدمة -----------------------------

class EosIn(BaseModel):
    basic_salary: float
    hire_date: date
    end_date: date
    reason: str = "termination"
    contract_type: str = "indefinite"
    used_leave_days: int = 0          # المُدخل الوحيد للإجازات؛ المتبقّي يُحسب آليًا
    annual_leave_days: int = 30       # سياسة الأيام السنوية (افتراضي 30)
    day_divisor: int | None = None
    max_months: int | None = None

    @field_validator("basic_salary")
    @classmethod
    def _salary_positive(cls, v):
        # راتب سالب/صفري ينتج مكافأة/تسوية سالبة غير منطقية (QA-P1-EOS-01)
        if v is None or v <= 0:
            raise ValueError("الراتب الأساسي يجب أن يكون أكبر من صفر")
        return v

    @field_validator("used_leave_days", "annual_leave_days")
    @classmethod
    def _leave_non_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("عدد أيام الإجازة لا يمكن أن يكون سالبًا")
        return v


class EosForEmployeeIn(BaseModel):
    employee_id: int
    end_date: date
    reason: str = "termination"
    used_leave_days: int = 0          # المتبقّي يُحسب آليًا من مدة الخدمة


# ----------------------------- مستندات -----------------------------

class DocumentTemplateIn(BaseModel):
    name: str
    name_en: str | None = None
    category: str = "عام"
    body_html: str
    code: str | None = None


class TemplateRenderIn(BaseModel):
    employee_id: int
    extra: dict[str, str] = {}
    save: bool = True


class DocumentMetaIn(BaseModel):
    entity_type: str = "employee"
    entity_id: int
    document_type_code: str
    title: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    extracted_data_json: dict | None = None
