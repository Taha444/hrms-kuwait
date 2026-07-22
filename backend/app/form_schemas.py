# -*- coding: utf-8 -*-
"""V2.2 §4 — Form Schema Engine.

مصدر الحقيقة الوحيد لحقول كل نوع طلب: يستخدمه الواجهة لبناء الفورم، والـBackend
للتحقق قبل الحفظ. لا يعتمد أي نوع على فورم عام Date/Amount/Details الافتراضي.

بنية الـSchema:
    {
      "fields": [
        {"code": "start_date", "label": "من تاريخ", "type": "date", "required": true},
        ...
      ],
      "conditional": [
        {"when": {"travel_required": true}, "show": ["destination", "passport_action"]}
      ],
      "attachments": {"required": [...], "optional": [...]},
      "meta": {"subtype_field": "loan_type"}
    }

أنواع الحقول المدعومة:
    text, textarea, number, amount, date, time, datetime, select, multi_select,
    checkbox, employee_ref, branch_ref, department_ref, attachment
"""
from typing import Any


# ============================================================================
# مكتبة الحقول المشتركة
# ============================================================================
def _field(code: str, label: str, type_: str = "text", required: bool = False,
           **extra: Any) -> dict:
    d = {"code": code, "label": label, "type": type_, "required": required}
    d.update(extra)
    return d


REASON = _field("reason", "السبب / التفاصيل", "textarea", required=True, max_length=500)
NOTES = _field("notes", "ملاحظات", "textarea", required=False, max_length=500)


# ============================================================================
# قاموس كل الأنواع الرسمية (V2.2 §7) — تعريف موحّد للـcanonical types
# ============================================================================
SCHEMAS: dict[str, dict] = {
    # ------------------------- الإجازات -------------------------
    "REQLV": {
        "fields": [
            _field("start_date", "من تاريخ", "date", required=True),
            _field("end_date", "إلى تاريخ", "date", required=True),
            _field("days", "عدد الأيام", "number", required=True, min=0.5, max=90),
            _field("leave_type", "نوع الإجازة", "select", required=True,
                   options=[
                       {"value": "annual", "label": "سنوية"},
                       {"value": "sick", "label": "مرضية"},
                       {"value": "emergency", "label": "طارئة"},
                       {"value": "unpaid", "label": "بدون راتب"},
                   ]),
            _field("travel_required", "سفر خارج البلاد؟", "checkbox"),
            _field("destination", "الوجهة (إن وجدت)", "text"),
            REASON,
            _field("return_date", "تاريخ العودة المتوقّع", "date"),
        ],
        "conditional": [
            {"when": {"travel_required": True},
             "show": ["destination", "return_date"], "require": ["destination"]},
        ],
        "attachments": {"required": [], "optional": ["medical_report"]},
        "validation": {"end_gte_start": ["start_date", "end_date"]},
        "meta": {"legacy_aliases": ["leave", "annual_leave", "sick_leave"]},
    },
    # ------------------------- تصحيح الحضور -------------------------
    "REQATT": {
        "fields": [
            _field("attendance_date", "تاريخ اليوم المطلوب تصحيحه", "date", required=True),
            _field("correction_type", "نوع التصحيح", "select", required=True,
                   options=[
                       {"value": "check_in", "label": "دخول"},
                       {"value": "check_out", "label": "خروج"},
                       {"value": "both", "label": "دخول وخروج"},
                       {"value": "missing_day", "label": "يوم غير مسجَّل"},
                   ]),
            _field("existing_check_in", "الدخول المسجَّل حاليًا", "datetime", read_only=True),
            _field("existing_check_out", "الخروج المسجَّل حاليًا", "datetime", read_only=True),
            _field("new_check_in", "الدخول الصحيح", "datetime"),
            _field("new_check_out", "الخروج الصحيح", "datetime"),
            REASON,
        ],
        "conditional": [
            {"when": {"correction_type": "check_in"}, "require": ["new_check_in"]},
            {"when": {"correction_type": "check_out"}, "require": ["new_check_out"]},
            {"when": {"correction_type": "both"}, "require": ["new_check_in", "new_check_out"]},
            {"when": {"correction_type": "missing_day"},
             "require": ["new_check_in", "new_check_out"]},
        ],
        "attachments": {"required": [], "optional": ["supporting_doc"]},
        "meta": {"legacy_aliases": ["attendance_correction"]},
    },
    # ------------------------- الإذن / المغادرة المبكرة -------------------------
    "REQPERM": {
        "fields": [
            _field("permission_date", "تاريخ الإذن", "date", required=True),
            _field("subtype", "نوع الإذن", "select", required=True,
                   options=[
                       {"value": "permission", "label": "إذن أثناء الدوام"},
                       {"value": "early_departure", "label": "مغادرة مبكرة"},
                       {"value": "late_arrival", "label": "تأخير دخول"},
                   ]),
            _field("from_time", "من الساعة", "time", required=True),
            _field("to_time", "إلى الساعة", "time"),
            REASON,
        ],
        "attachments": {"required": [], "optional": []},
        "meta": {"legacy_aliases": ["permission", "early_leave"]},
    },
    # ------------------------- شهادة راتب -------------------------
    "REQCERT": {
        "fields": [
            _field("purpose", "الجهة الموجَّهة إليها", "text", required=True, max_length=200),
            _field("include_salary", "تتضمن الراتب؟", "checkbox"),
            _field("include_allowances", "تتضمن البدلات؟", "checkbox"),
            _field("language", "اللغة", "select", required=True,
                   options=[
                       {"value": "ar", "label": "عربي"},
                       {"value": "en", "label": "إنجليزي"},
                       {"value": "both", "label": "عربي وإنجليزي"},
                   ]),
            _field("notes", "ملاحظات إضافية", "textarea", max_length=300),
        ],
        "attachments": {"required": [], "optional": []},
        "meta": {"legacy_aliases": ["salary_certificate", "employment_letter", "noc"]},
    },
    # ------------------------- سلفة / قرض -------------------------
    "REQADV": {
        "fields": [
            _field("loan_type", "نوع الطلب", "select", required=True,
                   options=[
                       {"value": "advance", "label": "سلفة (خصم شهر واحد)"},
                       {"value": "loan", "label": "قرض (خصم على عدة أشهر)"},
                   ]),
            _field("amount", "المبلغ (د.ك)", "amount", required=True, min=1),
            _field("months", "عدد أشهر السداد", "number", min=1, max=24),
            _field("first_deduction_month", "بداية الخصم (YYYY-MM)", "text", required=True),
            REASON,
        ],
        "conditional": [
            {"when": {"loan_type": "loan"}, "require": ["months"]},
            {"when": {"loan_type": "advance"}, "hide": ["months"]},
        ],
        "attachments": {"required": [], "optional": ["supporting_doc"]},
        "meta": {"legacy_aliases": ["advance", "loan", "advance_loan"],
                 "subtype_field": "loan_type"},
    },
    # ------------------------- مصروفات -------------------------
    "REQEXP": {
        "fields": [
            _field("expense_date", "تاريخ الصرف", "date", required=True),
            _field("category", "الفئة", "select", required=True,
                   options=[
                       {"value": "travel", "label": "سفر"},
                       {"value": "supplies", "label": "مستلزمات"},
                       {"value": "meals", "label": "وجبات"},
                       {"value": "other", "label": "أخرى"},
                   ]),
            _field("amount", "المبلغ (د.ك)", "amount", required=True, min=0.001),
            REASON,
        ],
        "attachments": {"required": ["receipt"], "optional": []},
        "meta": {"legacy_aliases": ["expense", "reimbursement"]},
    },
    # ------------------------- العمل الإضافي -------------------------
    "REQOT": {
        "fields": [
            _field("overtime_date", "تاريخ الإضافي", "date", required=True),
            _field("from_time", "من الساعة", "time", required=True),
            _field("to_time", "إلى الساعة", "time", required=True),
            _field("hours", "عدد الساعات", "number", required=True, min=0.5, max=12),
            REASON,
        ],
        "attachments": {"required": [], "optional": []},
        "meta": {"legacy_aliases": ["overtime"]},
    },
    # ------------------------- تحديث البيانات الشخصية -------------------------
    "REQUPD": {
        "fields": [
            _field("field_to_update", "الحقل المطلوب تعديله", "select", required=True,
                   options=[
                       {"value": "phone", "label": "رقم الهاتف"},
                       {"value": "email", "label": "البريد الإلكتروني"},
                       {"value": "address", "label": "العنوان"},
                       {"value": "emergency_contact", "label": "شخص للطوارئ"},
                       {"value": "marital_status", "label": "الحالة الاجتماعية"},
                   ]),
            _field("new_value", "القيمة الجديدة", "text", required=True, max_length=200),
            _field("effective_date", "تاريخ السريان", "date"),
            REASON,
        ],
        "attachments": {"required": [], "optional": ["supporting_doc"]},
        "meta": {"legacy_aliases": ["personal_update", "data_update"]},
    },
    # ------------------------- تحديث الحساب البنكي -------------------------
    "REQBANK": {
        "fields": [
            _field("bank_name", "اسم البنك", "text", required=True, max_length=100),
            _field("iban", "IBAN", "text", required=True, max_length=30,
                   pattern="^KW[0-9A-Z]{28}$"),
            _field("account_holder", "اسم صاحب الحساب", "text", required=True),
            _field("effective_month", "شهر التطبيق (YYYY-MM)", "text", required=True),
            REASON,
        ],
        "attachments": {"required": ["bank_letter"], "optional": []},
        "meta": {"legacy_aliases": ["bank_update", "iban_change"]},
    },
    # ------------------------- الاستقالة -------------------------
    "REQRESIGN": {
        "fields": [
            _field("submitted_at", "تاريخ التقديم", "date", required=True),
            _field("proposed_last_day", "آخر يوم عمل مقترح", "date", required=True),
            _field("notice_period_days", "فترة الإشعار (أيام)", "number", required=True,
                   min=0, max=180),
            REASON,
        ],
        "attachments": {"required": [], "optional": ["resignation_letter"]},
        "meta": {"legacy_aliases": ["resignation"]},
    },
    # ------------------------- إنهاء الخدمة (طلب) -------------------------
    "REQEOS": {
        "fields": [
            _field("hire_date", "تاريخ التعيين", "date", required=True, read_only=True),
            _field("last_day", "آخر يوم عمل", "date", required=True),
            _field("reason", "سبب الإنهاء", "select", required=True,
                   options=[
                       {"value": "termination", "label": "فصل غير تأديبي"},
                       {"value": "contract_expiry", "label": "انتهاء عقد"},
                       {"value": "resignation", "label": "استقالة"},
                       {"value": "death", "label": "وفاة"},
                       {"value": "disability", "label": "عجز"},
                       {"value": "marriage", "label": "استقالة للزواج"},
                       {"value": "misconduct", "label": "فصل تأديبي"},
                   ]),
            _field("used_leave_days", "الإجازات المستهلَكة", "number", required=True, min=0),
            _field("salary_basis", "أساس احتساب الراتب", "text", read_only=True),
        ],
        "attachments": {"required": [], "optional": ["termination_letter"]},
        "meta": {"legacy_aliases": ["eos", "end_of_service", "settlement"]},
    },
    # ------------------------- إخلاء طرف -------------------------
    "REQCLR": {
        "fields": [
            _field("last_day", "آخر يوم عمل", "date", required=True),
            _field("assets_handed", "العهدة المسلَّمة", "textarea", required=True),
            _field("finance_cleared", "المالية أخلَت طرفه؟", "checkbox"),
            _field("department_signoffs", "توقيعات الأقسام", "text"),
            REASON,
        ],
        "attachments": {"required": [], "optional": ["clearance_doc"]},
        "meta": {"legacy_aliases": ["clearance", "khilase"]},
    },
    # ------------------------- تجديد إقامة -------------------------
    "REQREN": {
        "fields": [
            _field("residency_expiry", "تاريخ انتهاء الإقامة", "date", required=True, read_only=True),
            _field("renewal_type", "نوع التجديد", "select", required=True,
                   options=[
                       {"value": "normal", "label": "طبيعي (≤30 يوم)"},
                       {"value": "early", "label": "مبكر (31-90 يوم)"},
                   ]),
            _field("civil_id_no", "رقم البطاقة المدنية", "text", read_only=True),
            REASON,
        ],
        "attachments": {"required": [], "optional": ["passport_copy", "civil_id_copy"]},
        "meta": {"legacy_aliases": ["residency_renewal", "iqama_renewal"]},
    },
    # ------------------------- تحديث الجواز -------------------------
    "REQPASS": {
        "fields": [
            _field("old_passport", "الجواز السابق", "text"),
            _field("new_passport", "الجواز الجديد", "text", required=True),
            _field("new_expiry", "تاريخ انتهاء الجواز الجديد", "date", required=True),
            _field("issue_country", "دولة الإصدار", "text"),
            REASON,
        ],
        "attachments": {"required": ["passport_scan"], "optional": []},
        "meta": {"legacy_aliases": ["passport_update"]},
    },
    # ------------------------- تحديث البطاقة المدنية -------------------------
    "REQCIVIL": {
        "fields": [
            _field("new_civil", "الرقم المدني الجديد", "text", required=True),
            _field("new_expiry", "تاريخ انتهاء البطاقة", "date", required=True),
            REASON,
        ],
        "attachments": {"required": ["civil_id_scan"], "optional": []},
        "meta": {"legacy_aliases": ["civil_id_update"]},
    },
    # ------------------------- تظلّم -------------------------
    "REQGRV": {
        "fields": [
            _field("subject", "موضوع التظلم", "text", required=True, max_length=200),
            _field("category", "الفئة", "select", required=True,
                   options=[
                       {"value": "harassment", "label": "تحرش/سلوك"},
                       {"value": "salary", "label": "راتب"},
                       {"value": "workload", "label": "عبء عمل"},
                       {"value": "management", "label": "علاقة إدارية"},
                       {"value": "other", "label": "أخرى"},
                   ]),
            _field("against_user_id", "المُشتكى منه (اختياري)", "employee_ref"),
            _field("details", "التفاصيل الكاملة", "textarea", required=True, max_length=2000),
            _field("confidential", "سرّي؟", "checkbox", default=True),
        ],
        "attachments": {"required": [], "optional": ["evidence"]},
        "meta": {"legacy_aliases": ["grievance", "complaint"], "confidential": True},
    },
    # ------------------------- اعتراض راتب/خصم -------------------------
    "REQPAY": {
        "fields": [
            _field("payroll_period", "شهر الراتب (YYYY-MM)", "text", required=True),
            _field("expected_amount", "المبلغ المتوقَّع", "amount"),
            _field("actual_amount", "المبلغ المدفوع", "amount"),
            _field("difference_amount", "الفرق", "amount"),
            REASON,
        ],
        "attachments": {"required": [], "optional": ["payslip_copy"]},
        "meta": {"legacy_aliases": ["payroll_objection"]},
    },
    "REQDED": {
        "fields": [
            _field("deduction_ref", "رقم/تاريخ الخصم", "text", required=True),
            _field("amount", "قيمة الخصم", "amount", required=True),
            REASON,
        ],
        "attachments": {"required": [], "optional": ["evidence"]},
        "meta": {"legacy_aliases": ["deduction_objection"]},
    },
    # ------------------------- طلب تدريب -------------------------
    "REQTRAIN": {
        "fields": [
            _field("training_name", "اسم الدورة", "text", required=True),
            _field("provider", "الجهة المقدِّمة", "text"),
            _field("start_date", "من تاريخ", "date", required=True),
            _field("end_date", "إلى تاريخ", "date", required=True),
            _field("cost", "التكلفة (د.ك)", "amount"),
            REASON,
        ],
        "attachments": {"required": [], "optional": ["course_brochure"]},
        "meta": {"legacy_aliases": ["training"]},
    },
    # ------------------------- نقل بين فروع/شركات -------------------------
    "REQTRANS": {
        "fields": [
            _field("to_branch_id", "الفرع الهدف", "branch_ref"),
            _field("to_company_id", "الشركة الهدف", "number"),
            _field("effective_date", "تاريخ السريان", "date", required=True),
            REASON,
        ],
        "attachments": {"required": [], "optional": []},
        "meta": {"legacy_aliases": ["transfer"]},
    },
    # ------------------------- ترقية / مراجعة راتب -------------------------
    "REQPROM": {
        "fields": [
            _field("new_title", "المسمى الوظيفي الجديد", "text", required=True),
            _field("new_salary", "الراتب الجديد (اختياري)", "amount"),
            _field("effective_date", "تاريخ السريان", "date", required=True),
            REASON,
        ],
        "attachments": {"required": [], "optional": []},
        "meta": {"legacy_aliases": ["promotion", "salary_review"]},
    },
    # ------------------------- إجراء حكومي عام -------------------------
    "REQGOV": {
        "fields": [
            _field("gov_action", "نوع المعاملة", "text", required=True),
            _field("authority", "الجهة الحكومية", "text", required=True),
            _field("deadline", "الموعد النهائي", "date"),
            REASON,
        ],
        "attachments": {"required": [], "optional": ["documents"]},
        "meta": {"legacy_aliases": ["government_transaction"]},
    },
    # ------------------------- إذن مغادرة (سفر) -------------------------
    "REQEXIT": {
        "fields": [
            _field("travel_date", "تاريخ السفر", "date", required=True),
            _field("return_date", "تاريخ العودة", "date", required=True),
            _field("destination", "الوجهة", "text", required=True),
            _field("passport_no", "رقم الجواز", "text", required=True),
            REASON,
        ],
        "attachments": {"required": ["passport_copy"], "optional": []},
        "meta": {"legacy_aliases": ["exit_permit"]},
    },
    # ------------------------- طلب مستند -------------------------
    "REQDOC": {
        "fields": [
            _field("document_type", "نوع المستند", "text", required=True),
            _field("purpose", "الغرض من الطلب", "text", required=True),
            _field("delivery_method", "طريقة التسليم", "select",
                   options=[
                       {"value": "printed", "label": "نسخة مطبوعة"},
                       {"value": "digital", "label": "نسخة رقمية"},
                       {"value": "both", "label": "الاثنين"},
                   ]),
        ],
        "attachments": {"required": [], "optional": []},
        "meta": {"legacy_aliases": ["document_request"]},
    },
}


def get_schema(code: str) -> dict | None:
    """يعيد schema بالكود الـcanonical أو عبر legacy alias."""
    if code in SCHEMAS:
        return SCHEMAS[code]
    for canonical, s in SCHEMAS.items():
        if code in (s.get("meta") or {}).get("legacy_aliases", []):
            return s
    return None


def validate_payload(code: str, payload: dict) -> list[str]:
    """يتحقق من الـpayload وفق الـschema — يعيد قائمة أخطاء (فارغة = نجاح).
    الأخطاء بصيغة "{field}: {message}" للعرض بجانب الحقل الصحيح في الواجهة.

    القاعدة العامة (§4 مع توافق خلفي):
    - التحقق يتم فقط عند meta.strict_validation=True في الـschema.
    - الأنواع الأخرى تعتمد على _missing_required_fields العام (workflow) للتوافق الخلفي
      حتى يُهاجَر كل نوع تدريجيًا.
    """
    s = get_schema(code)
    if not s:
        return []
    if not (s.get("meta") or {}).get("strict_validation"):
        return []
    errors: list[str] = []
    payload = payload or {}

    # القيود الشرطية: يُضاف "مطلوب" لحقول conditional.require
    dynamic_required: set[str] = set()
    hidden: set[str] = set()
    for cond in s.get("conditional") or []:
        when = cond.get("when") or {}
        matches = all(payload.get(k) == v for k, v in when.items())
        if matches:
            for f in cond.get("require") or []:
                dynamic_required.add(f)
            for f in cond.get("hide") or []:
                hidden.add(f)

    # التحقق من الحقول
    for f in s.get("fields") or []:
        code_ = f["code"]
        if code_ in hidden:
            continue
        val = payload.get(code_)
        required = bool(f.get("required")) or code_ in dynamic_required
        if required and (val is None or (isinstance(val, str) and not val.strip())):
            errors.append(f"{code_}: {f.get('label', code_)} مطلوب")
            continue
        if val is None:
            continue
        # قيود إضافية على الأرقام
        if f.get("type") in ("number", "amount"):
            try:
                n = float(val)
                if "min" in f and n < f["min"]:
                    errors.append(f"{code_}: القيمة أقل من الحد الأدنى ({f['min']})")
                if "max" in f and n > f["max"]:
                    errors.append(f"{code_}: القيمة أعلى من الحد الأقصى ({f['max']})")
            except (TypeError, ValueError):
                errors.append(f"{code_}: يجب أن تكون رقمًا")
        # قيود النص
        if f.get("type") in ("text", "textarea"):
            if isinstance(val, str) and f.get("max_length") and len(val) > f["max_length"]:
                errors.append(f"{code_}: النص أطول من الحد ({f['max_length']})")
        # قيود select
        if f.get("type") == "select":
            valid_values = {o["value"] for o in (f.get("options") or [])}
            if valid_values and val not in valid_values:
                errors.append(f"{code_}: قيمة غير صالحة (المتوقَّع أحد: {sorted(valid_values)})")

    # قيود التحقق المتقاطع (validation.*)
    validation = s.get("validation") or {}
    if "end_gte_start" in validation:
        s_key, e_key = validation["end_gte_start"]
        s_val, e_val = payload.get(s_key), payload.get(e_key)
        if s_val and e_val and str(e_val) < str(s_val):
            errors.append(f"{e_key}: يجب أن يكون في نفس {s_key} أو بعده")

    return errors
