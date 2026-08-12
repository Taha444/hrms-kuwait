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
            # R7-E — الإجازة المرضية تستلزم تقرير طبي (attachment.medical_report)
            {"when": {"leave_type": "sick"}, "require_attachments": ["medical_report"]},
        ],
        "attachments": {"required": [], "optional": ["medical_report"]},
        "validation": {"end_gte_start": ["start_date", "end_date"]},
        # ملاحظة: strict_validation مُطفَأة على REQLV للتوافق مع اختبارات موجودة
        # تعتمد على schema مرن. الـsick→medical_report يطبَّق فعليًا فقط لو المستخدم
        # اختار leave_type=sick صراحًة عبر الفورم (لا للـpayload القديم اللي بلا نوع).
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
        "meta": {"legacy_aliases": ["attendance_correction"], "strict_validation": False},
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
        "meta": {"legacy_aliases": ["permission", "early_leave"], "strict_validation": False},
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
        "meta": {"legacy_aliases": ["salary_certificate", "employment_letter", "noc"],
                 "strict_validation": False},
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
        "conditional": [
            # R7-E — تعديل الحالة الاجتماعية يستلزم وثيقة داعمة (عقد زواج/طلاق/إلخ)
            {"when": {"field_to_update": "marital_status"},
             "require_attachments": ["supporting_doc"]},
        ],
        "attachments": {"required": [], "optional": ["supporting_doc"]},
        "meta": {"legacy_aliases": ["personal_update", "data_update"],
                 "strict_validation": False},
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
        # R7-E — تجديد الإقامة يستلزم نسخة الجواز والبطاقة (لا يمكن تقديمها للحكومة بدونها)
        "attachments": {"required": ["passport_copy", "civil_id_copy"], "optional": []},
        "meta": {"legacy_aliases": ["residency_renewal", "iqama_renewal"],
                 "strict_validation": False},
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
        "meta": {"legacy_aliases": ["passport_update"], "strict_validation": False},
    },
    # ------------------------- تحديث البطاقة المدنية -------------------------
    "REQCIVIL": {
        "fields": [
            _field("new_civil", "الرقم المدني الجديد", "text", required=True),
            _field("new_expiry", "تاريخ انتهاء البطاقة", "date", required=True),
            REASON,
        ],
        "attachments": {"required": ["civil_id_scan"], "optional": []},
        "meta": {"legacy_aliases": ["civil_id_update"], "strict_validation": False},
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
        # R7-E — اعتراض راتب: يجب تقديم نسخة القسيمة المُعترَض عليها (بلاها لا دليل)
        "attachments": {"required": ["payslip_copy"], "optional": []},
        "meta": {"legacy_aliases": ["payroll_objection"], "strict_validation": False},
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
    # ------------------------- إذن مغادرة البلاد (سفر) -------------------------
    # المفتاح كان "REQEXIT" فيتصادم مع نوع الطلب REQEXIT — واسمه "طلب مغادرة
    # مبكرة" ونصّه في workflow.py يقول صراحة: «لا يستخدم هذا النموذج لإذن خروج
    # السفر». التصادم كان يفرض على طالب الانصراف المبكر إدخال جواز ووجهة سفر.
    # سُمّي باسم محتواه، وبقيت كنيته exit_permit عاملة. لا نوع طلب يستخدمه
    # حاليًا — يبقى جاهزًا لنوع "إذن مغادرة البلاد" إن أُضيف.
    "REQTRAVEL": {
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


# ============================================================================
# نماذج أنواع V1.3 التي لم يكن لها schema — كانت تسقط على النموذج العام
# (تاريخ/مبلغ/تفاصيل). كل نموذج هنا مصمَّم على غرض نوعه وسلسلة اعتماده الفعلية.
# ============================================================================
SCHEMAS.update({
    # ------------------------- الحضور والإجازات -------------------------
    "REQLATE": {  # تبرير تأخير — المسؤول المباشر ثم شؤون الموظفين
        "fields": [
            _field("late_date", "تاريخ التأخير", "date", required=True),
            _field("expected_time", "وقت الحضور المقرر", "time", required=True),
            _field("actual_time", "وقت الحضور الفعلي", "time", required=True),
            _field("late_cause", "سبب التأخير", "select", required=True,
                   options=[
                       {"value": "traffic", "label": "ازدحام مروري"},
                       {"value": "medical", "label": "ظرف صحي"},
                       {"value": "family", "label": "ظرف عائلي طارئ"},
                       {"value": "transport", "label": "عطل مواصلات"},
                       {"value": "other", "label": "سبب آخر"},
                   ]),
            REASON,
        ],
        # الظرف الصحي يستوجب إثباتًا — بقية الأسباب لا
        "conditional": [
            {"when": {"late_cause": "medical"}, "require_attachments": ["medical_note"]},
        ],
        "attachments": {"required": [], "optional": ["supporting_doc"]},
        "meta": {"legacy_aliases": ["late_justification"], "strict_validation": False},
    },
    "REQSHIFT": {  # تغيير وردية — المسؤول المباشر ثم المدير العام
        "fields": [
            _field("current_shift", "الوردية الحالية", "text", read_only=True),
            _field("requested_shift_id", "الوردية المطلوبة", "shift_ref", required=True),
            _field("effective_from", "اعتبارًا من تاريخ", "date", required=True),
            _field("is_permanent", "دائم أم مؤقت", "select", required=True,
                   options=[
                       {"value": "permanent", "label": "تغيير دائم"},
                       {"value": "temporary", "label": "تغيير مؤقت"},
                   ]),
            _field("effective_to", "حتى تاريخ (للمؤقت)", "date"),
            REASON,
        ],
        "conditional": [
            {"when": {"is_permanent": "temporary"}, "require": ["effective_to"]},
        ],
        "validation": {"end_gte_start": ["effective_from", "effective_to"]},
        "attachments": {"required": [], "optional": []},
        "meta": {"legacy_aliases": ["shift_change"], "strict_validation": False},
    },
    "REQWLOC": {  # تكليف مؤقت بموقع/فرع — 3 مراحل اعتماد
        "fields": [
            _field("target_branch_id", "الفرع أو الموقع المطلوب", "branch_ref", required=True),
            _field("from_date", "من تاريخ", "date", required=True),
            _field("to_date", "إلى تاريخ", "date", required=True),
            _field("transport_needed", "يحتاج مواصلات", "checkbox"),
            _field("housing_needed", "يحتاج سكن", "checkbox"),
            REASON,
        ],
        "validation": {"end_gte_start": ["from_date", "to_date"]},
        "attachments": {"required": [], "optional": []},
        "meta": {"legacy_aliases": ["temp_assignment", "work_location"],
                 "strict_validation": False},
    },
    "REQMIS": {  # مهمة عمل خارجية — المسؤول المباشر ثم المدير العام
        "fields": [
            _field("destination", "جهة المهمة", "text", required=True, max_length=200),
            _field("from_date", "من تاريخ", "date", required=True),
            _field("to_date", "إلى تاريخ", "date", required=True),
            _field("mission_type", "نوع المهمة", "select", required=True,
                   options=[
                       {"value": "government", "label": "مراجعة جهة حكومية"},
                       {"value": "client", "label": "زيارة عميل أو مورّد"},
                       {"value": "training", "label": "تدريب أو مؤتمر"},
                       {"value": "other", "label": "أخرى"},
                   ]),
            _field("estimated_cost", "التكلفة التقديرية (د.ك)", "number", min=0),
            REASON,
        ],
        "validation": {"end_gte_start": ["from_date", "to_date"]},
        "attachments": {"required": [], "optional": ["supporting_doc"]},
        "meta": {"legacy_aliases": ["mission", "business_trip"], "strict_validation": False},
    },
    # ------------------------- الإقامة والمعاملات الحكومية -------------------------
    "REQWP": {  # تجديد إذن عمل — شؤون الموظفين ثم المدير ثم المندوب
        "fields": [
            _field("permit_no", "رقم إذن العمل الحالي", "text", required=True, max_length=40),
            _field("permit_expiry", "تاريخ انتهاء الإذن", "date", required=True),
            _field("profession", "المهنة في الإذن", "text", max_length=150),
            _field("license_id", "الترخيص التابع له", "license_ref"),
            _field("urgency", "درجة الاستعجال", "select",
                   options=[
                       {"value": "normal", "label": "عادي"},
                       {"value": "urgent", "label": "مستعجل (قارب على الانتهاء)"},
                   ]),
            REASON,
        ],
        "attachments": {"required": [], "optional": ["current_permit", "passport_copy"]},
        "meta": {"legacy_aliases": ["work_permit_renewal"], "strict_validation": False},
    },
    "REQTRFLIC": {  # نقل عامل بين فرع أو ترخيص — 3 مراحل
        "fields": [
            _field("transfer_kind", "نوع النقل", "select", required=True,
                   options=[
                       {"value": "branch", "label": "نقل بين فروع"},
                       {"value": "license", "label": "نقل بين تراخيص"},
                       {"value": "both", "label": "نقل فرع وترخيص معًا"},
                   ]),
            _field("to_branch_id", "الفرع الجديد", "branch_ref"),
            _field("to_license_id", "الترخيص الجديد", "license_ref"),
            _field("effective_date", "تاريخ النفاذ", "date", required=True),
            _field("gov_transaction_needed", "يستلزم معاملة حكومية", "checkbox"),
            REASON,
        ],
        "conditional": [
            {"when": {"transfer_kind": "branch"}, "require": ["to_branch_id"]},
            {"when": {"transfer_kind": "license"}, "require": ["to_license_id"]},
            {"when": {"transfer_kind": "both"}, "require": ["to_branch_id", "to_license_id"]},
        ],
        "attachments": {"required": [], "optional": []},
        "meta": {"legacy_aliases": ["license_transfer"], "strict_validation": False},
    },
    # ------------------------- بيانات الموظف والمستندات -------------------------
    "REQCONTACT": {  # تحديث بيانات الاتصال والطوارئ — شؤون الموظفين فقط
        "fields": [
            _field("new_phone", "رقم الهاتف الجديد", "text", max_length=30),
            _field("new_email", "البريد الإلكتروني الجديد", "text", max_length=150),
            _field("new_address", "العنوان الجديد", "textarea", max_length=300),
            _field("emergency_name", "اسم شخص الطوارئ", "text", max_length=150),
            _field("emergency_relation", "صلة القرابة", "text", max_length=60),
            _field("emergency_phone", "هاتف الطوارئ", "text", max_length=30),
            NOTES,
        ],
        "attachments": {"required": [], "optional": []},
        "meta": {"legacy_aliases": ["contact_update", "emergency_contact"],
                 "strict_validation": False},
    },
    "REQFILE": {  # نسخة من ملف أو مستند — شؤون الموظفين فقط
        "fields": [
            _field("document_kind", "المستند المطلوب", "select", required=True,
                   options=[
                       {"value": "contract", "label": "عقد العمل"},
                       {"value": "payslips", "label": "قسائم رواتب"},
                       {"value": "certificates", "label": "شهادات صادرة"},
                       {"value": "attendance", "label": "سجل حضور"},
                       {"value": "full_file", "label": "الملف كاملًا"},
                       {"value": "other", "label": "مستند آخر"},
                   ]),
            _field("period_from", "من تاريخ (إن وُجد)", "date"),
            _field("period_to", "إلى تاريخ (إن وُجد)", "date"),
            _field("copies", "عدد النسخ", "number", min=1, max=5),
            _field("delivery_method", "طريقة التسليم", "select",
                   options=[
                       {"value": "pickup", "label": "استلام باليد"},
                       {"value": "email", "label": "بريد إلكتروني"},
                   ]),
            REASON,
        ],
        "validation": {"end_gte_start": ["period_from", "period_to"]},
        "attachments": {"required": [], "optional": []},
        "meta": {"legacy_aliases": ["file_copy"], "strict_validation": False},
    },
    # ------------------------- الطلبات المالية -------------------------
    "REQALLOW": {  # بدل أو ميزة — المسؤول المباشر ثم المدير العام
        "fields": [
            _field("allowance_type", "نوع البدل", "select", required=True,
                   options=[
                       {"value": "transport", "label": "بدل مواصلات"},
                       {"value": "housing", "label": "بدل سكن"},
                       {"value": "phone", "label": "بدل هاتف"},
                       {"value": "nature_of_work", "label": "بدل طبيعة عمل"},
                       {"value": "other", "label": "بدل آخر"},
                   ]),
            _field("amount", "المبلغ الشهري المطلوب (د.ك)", "number", required=True, min=0),
            _field("effective_from", "اعتبارًا من", "date", required=True),
            _field("is_recurring", "شهري متكرر", "checkbox"),
            REASON,
        ],
        "attachments": {"required": [], "optional": ["supporting_doc"]},
        "meta": {"legacy_aliases": ["allowance"], "strict_validation": False},
    },
    # ------------------------- الشكاوى والتظلمات -------------------------
    "REQVIO": {  # اعتراض على مخالفة — شؤون الموظفين ثم المدير العام
        "fields": [
            _field("violation_ref", "رقم المخالفة أو تاريخها", "text", required=True,
                   max_length=80),
            _field("violation_date", "تاريخ المخالفة", "date", required=True),
            _field("objection_ground", "أساس الاعتراض", "select", required=True,
                   options=[
                       {"value": "not_committed", "label": "لم أرتكب المخالفة"},
                       {"value": "excuse", "label": "لديّ عذر مقبول"},
                       {"value": "disproportionate", "label": "الجزاء غير متناسب"},
                       {"value": "procedural", "label": "خلل في الإجراء"},
                   ]),
            REASON,
        ],
        # الاعتراض بعذر يستلزم إثباتًا يدعمه
        "conditional": [
            {"when": {"objection_ground": "excuse"},
             "require_attachments": ["supporting_doc"]},
        ],
        "attachments": {"required": [], "optional": ["supporting_doc"]},
        "meta": {"legacy_aliases": ["violation_objection"], "strict_validation": False},
    },
    "REQWARN": {  # إقرار أو رد على إنذار — شؤون الموظفين فقط
        "fields": [
            _field("warning_ref", "رقم الإنذار أو تاريخه", "text", required=True,
                   max_length=80),
            _field("acknowledgment", "الموقف من الإنذار", "select", required=True,
                   options=[
                       {"value": "acknowledge", "label": "أقر بالاطلاع"},
                       {"value": "acknowledge_disagree", "label": "أقر بالاطلاع مع الاعتراض"},
                       {"value": "dispute", "label": "أعترض على مضمونه"},
                   ]),
            _field("response", "ردّي على الإنذار", "textarea", required=True, max_length=1000),
        ],
        "attachments": {"required": [], "optional": ["supporting_doc"]},
        "meta": {"legacy_aliases": ["warning_response"], "strict_validation": False},
    },
    # ------------------------- طلبات عامة -------------------------
    "REQGEN": {  # طلب عام أو اقتراح — المسؤول المباشر فقط
        "fields": [
            _field("subject", "الموضوع", "text", required=True, max_length=200),
            _field("request_kind", "نوع الطلب", "select", required=True,
                   options=[
                       {"value": "suggestion", "label": "اقتراح تطوير"},
                       {"value": "request", "label": "طلب إداري"},
                       {"value": "inquiry", "label": "استفسار"},
                   ]),
            _field("details", "التفاصيل", "textarea", required=True, max_length=1000),
        ],
        "attachments": {"required": [], "optional": ["supporting_doc"]},
        "meta": {"legacy_aliases": ["general_request", "suggestion"],
                 "strict_validation": False},
    },
    # ------------------------- العقود وإنهاء الخدمة -------------------------
    "REQCON": {  # تجديد عقد أو عدم تجديد — شؤون الموظفين ثم المدير العام
        "fields": [
            _field("current_contract_end", "تاريخ انتهاء العقد الحالي", "date", required=True),
            _field("decision", "المطلوب", "select", required=True,
                   options=[
                       {"value": "renew", "label": "تجديد العقد"},
                       {"value": "not_renew", "label": "عدم التجديد"},
                       {"value": "amend", "label": "تجديد مع تعديل شروط"},
                   ]),
            _field("new_duration_months", "مدة التجديد (بالأشهر)", "number", min=1, max=60),
            _field("proposed_changes", "التعديلات المقترحة", "textarea", max_length=600),
            REASON,
        ],
        "conditional": [
            {"when": {"decision": "renew"}, "require": ["new_duration_months"]},
            {"when": {"decision": "amend"},
             "require": ["new_duration_months", "proposed_changes"]},
        ],
        "attachments": {"required": [], "optional": []},
        "meta": {"legacy_aliases": ["contract_renewal"], "strict_validation": False},
    },

    # طلب تغيير التوقيع — يفتحه الموظف من ملفه الشخصي حين يضغط "استبدال التوقيع".
    # صورة التوقيع الجديدة تُرفع كمرفق على الطلب ويعتمدها HR؛ لا تصبح نافذة قبل
    # ذلك، فيبقى التوقيع القديم ساريًا على المستندات حتى تُقرّ النسخة الجديدة.
    "REQSIG": {
        "fields": [
            _field("change_reason", "سبب تغيير التوقيع", "select", required=True,
                   options=[
                       {"value": "improve", "label": "تحسين وضوح التوقيع"},
                       {"value": "name_change", "label": "تغيير الاسم"},
                       {"value": "compromised", "label": "تسرّب أو استخدام غير مصرّح"},
                       {"value": "other", "label": "سبب آخر"},
                   ]),
            REASON,
        ],
        "attachments": {"required": ["signature"], "optional": []},
        "meta": {"enforce_required": True, "strict_validation": True},
    },
})


# ---------------------------------------------------------------------------
# ربط أكواد أنواع الطلبات (V1.3، جدول request_types) بمفاتيح الـschemas.
#
# المفاتيح هنا اختيرت بأسماء مختصرة (REQCERT/REQPERM/REQREN...) بينما كتالوج
# أنواع الطلبات يستخدم أكوادًا أطول (REQCERTSAL/REQPER/REQRESN...). الاختلاف
# جعل get_schema يعيد None لـ34 نوعًا من 53، فتسقط كلها على النموذج العام
# (تاريخ/مبلغ/تفاصيل) بدل نموذجها الحقيقي.
#
# كل سطر هنا تحقّقنا من تطابق اسم النوع مع حقول الـschema — لا تخمين بالاسم:
# مثلاً REQTRN اسمه "طلب تدريب" لا نقل، فيُربط بـREQTRAIN لا REQTRANS.
# الأنواع الإدارية (ADM*) لا نماذج لها عمدًا — سجلات داخلية لا يملؤها موظف.
# ---------------------------------------------------------------------------
REQUEST_TYPE_SCHEMA_MAP: dict[str, str] = {
    "REQPER": "REQPERM",        # طلب إذن أثناء الدوام
    "exit_permission": "REQPERM",  # طلب إذن خروج/استئذان (نفس نموذج الإذن)
    # نوع REQEXIT اسمه "طلب مغادرة مبكرة" — عمل داخل الدوام. لكن schema REQEXIT
    # يخص إذن مغادرة البلاد (destination/passport_no/return_date)، فكان يطالب من
    # يطلب انصرافًا مبكرًا برقم جواز ووجهة سفر. المغادرة المبكرة أصلاً خيار
    # (early_departure) داخل REQPERM، فهي موطنه الصحيح. schema REQEXIT يبقى
    # متاحًا لنوع "إذن مغادرة البلاد" إن أُضيف لاحقًا.
    "REQEXIT": "REQPERM",
    "REQCERTSAL": "REQCERT",    # طلب شهادة راتب
    "REQCERTEMP": "REQCERT",    # طلب شهادة لمن يهمه الأمر
    "REQCERTEXP": "REQCERT",    # طلب شهادة خبرة
    "REQDATA": "REQUPD",        # طلب تعديل البيانات الشخصية
    "REQRESN": "REQREN",        # طلب تجديد إقامة عادي
    "REQRESE": "REQREN",        # طلب تجديد إقامة مبكر (نفس النموذج، renewal_type يميّز)
    "REQCID": "REQCIVIL",       # طلب تحديث/تجديد البطاقة المدنية
    "REQPROMO": "REQPROM",      # طلب ترقية أو تعديل راتب
    "REQTRF": "REQTRANS",       # طلب نقل داخلي
    "REQTRN": "REQTRAIN",       # طلب تدريب
}


# ---------------------------------------------------------------------------
# النماذج القديمة التي روجعت حقولها الإلزامية مقابل استخدامها الفعلي، فصار
# فرضها على الخادم آمنًا (meta.enforce_required).
#
# منهج المراجعة لكل نوع: مَن يرسل الحمولة فعلًا؟
#   - نوع له نموذج مبرمج في Requests.tsx → أسماء حقوله تحكمها
#     REQUIRED_PAYLOAD_FIELDS وتسبق الـschema دائمًا، فالفرض هنا بلا أثر.
#   - نوع بنموذج عام → الواجهة تبنيه من الـschema نفسه، فالـschema هو المرجع
#     وحقوله الإلزامية صحيحة بالتعريف.
# ثم قوبل ذلك بالحمولات الفعلية في الاختبارات لاكتشاف أي تعارض.
#
# المستثنون عمدًا:
#   REQEOS / REQCLR — يُنشآن برمجيًا بحمولة خاصة (hire_date/last_day/
#     entitlements/net) لا تمر بنموذج، وschemaهما يطلب reason/used_leave_days
#     غير الموجودَين فيها. فرضهما يكسر تدفق إنهاء الخدمة.
#   REQEXIT — أُعيد توجيهه لـREQPERM أعلاه (تعارض دلالي في الـschema).
# ---------------------------------------------------------------------------
_VERIFIED_ENFORCE_REQUIRED = (
    "REQATT",     # تصحيح حضور — الحمولة الفعلية تطابق (attendance_date/correction_type/reason)
    "REQPERM",    # إذن/مغادرة مبكرة — نموذج عام
    "REQCERT",    # شهادات — الحمولة الفعلية تطابق (purpose/language)
    "REQOT",      # عمل إضافي — الحمولة الفعلية تطابق الخمسة كلها
    "REQUPD",     # تعديل بيانات شخصية — نموذج عام
    "REQRESIGN",  # استقالة — نموذج عام
    "REQREN",     # تجديد إقامة — نموذج عام
    "REQPASS",    # تحديث جواز — نموذج عام
    "REQCIVIL",   # تحديث بطاقة مدنية — نموذج عام
    "REQGRV",     # تظلّم — نموذج عام (category حقل حقيقي يعرضه النموذج)
    "REQPAY",     # اعتراض رواتب — نموذج عام (اسم الحقل payroll_period)
    "REQDED",     # اعتراض خصم — نموذج عام
    "REQTRAIN",   # تدريب — نموذج عام
    "REQTRANS",   # نقل داخلي — نموذج عام
    "REQPROM",    # ترقية — نموذج عام
    "REQGOV",     # معاملة حكومية — نموذج عام
    "REQDOC",     # مستندات — نموذج عام
    # النماذج الـ13 المؤلَّفة حديثًا — حقولها وقيودها صُمِّمت معًا فهي متسقة
    # بالبناء، وكلها بنموذج عام يُبنى من الـschema.
    "REQLATE", "REQSHIFT", "REQWLOC", "REQMIS", "REQWP", "REQTRFLIC",
    "REQCONTACT", "REQFILE", "REQALLOW", "REQVIO", "REQWARN", "REQGEN", "REQCON",
    # الأربعة الأخيرة: كانت أنواعها تُعرض بنماذج مبرمجة في الواجهة بمفردات خاصة
    # (addressed_to بدل purpose، subtype بدل loan_type، description بدل reason)
    # فأُعفيت من التحقق. بعد أن صارت كل الأنواع تُبنى من الـschema لم يبقَ استثناء.
    "REQLV", "REQADV", "REQEXP", "REQBANK",
)

for _code in _VERIFIED_ENFORCE_REQUIRED:
    _meta = SCHEMAS[_code].setdefault("meta", {})
    _meta["enforce_required"] = True
    # التحقق الحقلي الصارم: حدود الأرقام، أطوال النصوص، عضوية قيم select،
    # وترتيب التواريخ (end_gte_start). يُفعَّل مع نفس المجموعة المراجَعة لأن
    # النموذج هو مصدر حقول هذه الأنواع، فقيوده تصف ما ترسله الواجهة فعلًا.
    #
    # الأكواد ذات النموذج المبرمج (المسجّلة في REQUIRED_PAYLOAD_FIELDS) تمرّر
    # strict=False من submit_request: مفرداتها تخص واجهتها لا الـschema.
    _meta["strict_validation"] = True
del _code, _meta


def conditional_requirements(schema: dict, payload: dict) -> tuple[set[str], set[str]]:
    """يقيّم قواعد conditional مقابل حمولة، ويعيد (حقول صارت إلزامية، حقول مخفية).

    مصدر واحد لمطابقة الشروط يستخدمه validate_payload و_missing_required_fields
    معًا — الاستنساخ في موضعين هو ما جعل كتالوج الإنشاء يختلف عمّا يقبله POST.
    """
    add: set[str] = set()
    hidden: set[str] = set()
    for cond in schema.get("conditional") or []:
        when = cond.get("when") or {}
        if all((payload or {}).get(k) == v for k, v in when.items()):
            add.update(cond.get("require") or [])
            hidden.update(cond.get("hide") or [])
    return add, hidden


def get_schema(code: str) -> dict | None:
    """يعيد schema بالكود الـcanonical أو عبر legacy alias أو خريطة أكواد V1.3."""
    if code in SCHEMAS:
        return SCHEMAS[code]
    mapped = REQUEST_TYPE_SCHEMA_MAP.get(code)
    if mapped and mapped in SCHEMAS:
        return SCHEMAS[mapped]
    for canonical, s in SCHEMAS.items():
        if code in (s.get("meta") or {}).get("legacy_aliases", []):
            return s
    return None


def validate_payload(code: str, payload: dict, strict: bool | None = None) -> list[str]:
    """يتحقق من الـpayload وفق الـschema — يعيد قائمة أخطاء (فارغة = نجاح).
    الأخطاء بصيغة "{field}: {message}" للعرض بجانب الحقل الصحيح في الواجهة.

    قاعدتان مستقلّتان:
    - التحقق الحقلي الصارم (fields required + types + limits) يتم فقط عند
      meta.strict_validation=True (للتوافق الخلفي مع الاختبارات القديمة).
    - التحقق من المرفقات المطلوبة (§5) يتم دائمًا لأي schema يعرّف
      attachments.required أو conditional.require_attachments — بصرف النظر عن
      strict_validation، لأن رفض طلب بلا مرفق إلزامي ليس اختياريًا.
    """
    s = get_schema(code)
    if not s:
        return []
    # strict=None → القرار للـschema. المُستدعي يمرّر False صراحةً للأكواد التي
    # يبني نموذجها الواجهة بأسماء حقول خاصة بها (مفردات مختلفة عن الـschema)،
    # فالتحقق الحقلي بمفردات الـschema لا ينطبق عليها.
    if strict is None:
        strict = bool((s.get("meta") or {}).get("strict_validation"))
    errors: list[str] = []
    payload = payload or {}

    # القيود الشرطية: يُضاف "مطلوب" لحقول conditional.require
    # نفس دالة المطابقة التي يستخدمها _missing_required_fields — لا استنساخ.
    dynamic_required, hidden = conditional_requirements(s, payload)
    dynamic_required_attachments: set[str] = set()
    for cond in s.get("conditional") or []:
        when = cond.get("when") or {}
        if all(payload.get(k) == v for k, v in when.items()):
            # R7-E — مرفقات مطلوبة شرطيًا (مثلاً "leave sick" → medical_report)
            for att in cond.get("require_attachments") or []:
                dynamic_required_attachments.add(att)

    # التحقق من المرفقات دائمًا — لا يعتمد على strict_validation
    required_atts = set((s.get("attachments") or {}).get("required") or []) \
                   | dynamic_required_attachments
    if required_atts:
        uploaded = set(payload.get("_attachments") or [])
        missing_atts = required_atts - uploaded
        if missing_atts:
            errors.append(
                f"_attachments: مرفقات مطلوبة مفقودة — {', '.join(sorted(missing_atts))}"
            )

    # التحقق الحقلي الصارم فقط لما strict_validation مُفعّلة
    if not strict:
        return errors

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
