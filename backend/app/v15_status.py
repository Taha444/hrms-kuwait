# -*- coding: utf-8 -*-
"""V1.5 Phase 2 — Canonical Status Model + Step Types.

مصدر: V2.2 Business Workflow §3.3 و §3.2 + V1.5 §3 Status Model.

**قرار تصميمي (V1.5 ص 4):** حالتان مستقلتان — الطلب والمستند — لأن اكتمال قرار الاعتماد
لا يعني بالضرورة أن الوثيقة صدرت وأصبحت جاهزة. الحالة القديمة كانت تخلط الاثنين.

**تخطيط (V1.5 forward-compat):** الحقل `Request.status` الداخلي يبقى كما هو (pending,
awaiting_signature, completed, ...) — هذا الملف يضيف طبقة عرض canonical فوقه، لأن تغيير
عمود قاعدة البيانات محفوف بمخاطر ترحيل غير موثّق. القيم V1.5 canonical تُعرض في الـ API
عبر `STATUS_MAP` الموسّع في `workflow.py` وعبر `/api/requests/status-model`.
"""
from __future__ import annotations


# ==============================================================================
# 1) دورة حياة الطلب (V2.2 §3.3, V1.5 §3)
# DRAFT -> SUBMITTED -> IN_REVIEW -> NEEDS_INFO -> APPROVED -> IN_EXECUTION -> COMPLETED
# حالات نهاية بديلة: REJECTED, CANCELLED
# ==============================================================================
REQUEST_LIFECYCLE: dict[str, dict] = {
    "DRAFT": {
        "label_ar": "مسودة", "label_en": "Draft",
        "next": ["SUBMITTED", "CANCELLED"],
        "actor": "requester",
        "note": "لم يُرسَل بعد؛ يعدّل المقدّم كما يشاء.",
    },
    "SUBMITTED": {
        "label_ar": "مُرسَل", "label_en": "Submitted",
        "next": ["IN_REVIEW", "REJECTED", "CANCELLED"],
        "actor": "system",
        "note": "دخل الكتالوج وينتظر التوجيه لمرحلة أولى.",
    },
    "IN_REVIEW": {
        "label_ar": "قيد المراجعة", "label_en": "In Review",
        "next": ["APPROVED", "REJECTED", "NEEDS_INFO"],
        "actor": "approver_or_validator",
        "note": "خطوة قرار أو تحقق نشطة الآن.",
    },
    "NEEDS_INFO": {
        "label_ar": "بحاجة معلومات إضافية", "label_en": "Needs Info",
        "next": ["SUBMITTED", "CANCELLED"],
        "actor": "requester",
        "note": "أُعيد للمقدّم لاستكمال بيانات؛ يُعاد التقديم دون إنشاء طلب جديد.",
    },
    "APPROVED": {
        "label_ar": "معتمَد", "label_en": "Approved",
        "next": ["IN_EXECUTION", "COMPLETED"],
        "actor": "system",
        "note": "اكتمل القرار الإداري؛ إن كان يتطلب أثرًا تنفيذيًا يدخل IN_EXECUTION.",
    },
    "IN_EXECUTION": {
        "label_ar": "قيد التنفيذ", "label_en": "In Execution",
        "next": ["COMPLETED", "FAILED"],
        "actor": "executor",
        "note": "خطوة تنفيذ (Payroll / Delegate / Document Generation) نشطة.",
    },
    "COMPLETED": {
        "label_ar": "مكتمل", "label_en": "Completed",
        "next": [],
        "actor": "system",
        "note": "حالة نهائية — كل الخطوات تمّت والوثائق المطلوبة صدرت.",
        "terminal": True,
    },
    "REJECTED": {
        "label_ar": "مرفوض", "label_en": "Rejected",
        "next": [],
        "actor": "approver",
        "note": "حالة نهائية — رفض مسبَّب من صاحب القرار.",
        "terminal": True,
    },
    "CANCELLED": {
        "label_ar": "ملغى", "label_en": "Cancelled",
        "next": [],
        "actor": "requester_or_manager",
        "note": "حالة نهائية — إلغاء من المقدّم قبل القرار، أو من المدير في أي مرحلة.",
        "terminal": True,
    },
    "FAILED": {
        "label_ar": "فشل التنفيذ", "label_en": "Execution Failed",
        "next": ["IN_EXECUTION"],
        "actor": "system",
        "note": "توليد وثيقة/توقيع فشل تقنيًا؛ يبقى في IN_EXECUTION مع علامة خطأ لإعادة المحاولة.",
    },
}


# ==============================================================================
# 2) دورة حياة المستند (V2.2 §3.3, V1.5 §28)
# NOT_REQUIRED -> QUEUED -> GENERATING -> GENERATED -> SIGNED -> DELIVERED -> ARCHIVED
# فرع بديل: GENERATION_FAILED
# ==============================================================================
DOCUMENT_LIFECYCLE: dict[str, dict] = {
    "NOT_REQUIRED": {
        "label_ar": "لا يتطلب مستند", "label_en": "Not Required",
        "next": [],
        "note": "الطلب لا يُنتج مستندًا رسميًا (مثل استئذان أثناء الدوام).",
        "terminal": True,
    },
    "QUEUED": {
        "label_ar": "بانتظار التوليد", "label_en": "Queued",
        "next": ["GENERATING", "GENERATION_FAILED"],
        "note": "قرار الاعتماد اكتمل؛ المستند في طابور التوليد.",
    },
    "GENERATING": {
        "label_ar": "يجري التوليد", "label_en": "Generating",
        "next": ["GENERATED", "GENERATION_FAILED"],
        "note": "محرك القوالب يعالج البيانات وينتج PDF.",
    },
    "GENERATED": {
        "label_ar": "تم التوليد", "label_en": "Generated",
        "next": ["SIGNED", "DELIVERED", "ARCHIVED"],
        "note": "PDF جاهز؛ ينتظر توقيع إلكتروني أو تسليم مباشر.",
    },
    "SIGNED": {
        "label_ar": "موقّع إلكترونيًا", "label_en": "Electronically Signed",
        "next": ["DELIVERED", "ARCHIVED"],
        "note": "تم توثيق التوقيع في SYS-001 Signature Evidence Record.",
    },
    "DELIVERED": {
        "label_ar": "تم التسليم", "label_en": "Delivered",
        "next": ["ARCHIVED"],
        "note": "استُلم من المقدّم/الجهة الخارجية عبر تنزيل موثّق.",
    },
    "ARCHIVED": {
        "label_ar": "مؤرشف", "label_en": "Archived",
        "next": [],
        "note": "الحالة النهائية — محفوظ في أرشيف الشركة/الموظف.",
        "terminal": True,
    },
    "GENERATION_FAILED": {
        "label_ar": "فشل التوليد", "label_en": "Generation Failed",
        "next": ["QUEUED"],
        "note": "خطأ تقني عند التوليد؛ يُعاد للطابور للمعالجة.",
    },
}


# ==============================================================================
# 3) Step Types (V2.2 §3.2) — أنواع الخطوات في المسار
# كل خطوة في approval_chain_json تحمل step_type يحدد طبيعتها ومَن يراها
# ==============================================================================
STEP_TYPES: dict[str, dict] = {
    "DECISION": {
        "label_ar": "قرار",
        "label_en": "Decision",
        "who_acts": "approver",
        "actions": ["approve", "reject", "needs_info"],
        "note": "خطوة قرار إداري أو مالي يتحمل صاحبها المسؤولية.",
        "example": "المدير يعتمد إجازة أو تكلفة تدريب.",
    },
    "VALIDATION": {
        "label_ar": "تحقق",
        "label_en": "Validation",
        "who_acts": "validator",
        "actions": ["valid", "invalid", "return_for_correction"],
        "note": "فحص حقيقة أو سياسة أو مستند دون قرار إداري.",
        "example": "HR يتحقق من رصيد الإجازة قبل الاعتماد.",
    },
    "EXECUTION": {
        "label_ar": "تنفيذ",
        "label_en": "Execution",
        "who_acts": "executor",
        "actions": ["executed", "execution_failed"],
        "note": "ينفّذ الأثر بعد اكتمال القرار (Payroll / PRO / Document generation).",
        "example": "المحاسب يجدول السلفة في Payroll.",
    },
    "ACKNOWLEDGEMENT": {
        "label_ar": "إقرار استلام",
        "label_en": "Acknowledgement",
        "who_acts": "acknowledger",
        "actions": ["acknowledged", "objection_recorded"],
        "note": "إثبات علم أو استلام، وليس حق تعطيل القرار.",
        "example": "الموظف يقرّ باستلام إنذار أو تسوية.",
    },
    "NOTIFICATION": {
        "label_ar": "إشعار",
        "label_en": "Notification",
        "who_acts": "system",
        "actions": ["delivered", "read"],
        "note": "إبلاغ بلا مهمة قرار — يتم تلقائيًا.",
        "example": "إخطار الموظف باكتمال إصدار الشهادة.",
    },
    "AUTOMATION": {
        "label_ar": "أتمتة",
        "label_en": "Automation",
        "who_acts": "system",
        "actions": ["auto_completed", "auto_failed"],
        "note": "قاعدة حتمية لا تحتاج تدخلًا بشريًا.",
        "example": "توليد شهادة من بيانات معتمدة أو تحديث رصيد.",
    },
}


# ==============================================================================
# 4) خريطة الحالات الداخلية القديمة → V1.5 canonical
# يستخدمها STATUS_MAP في workflow.py ليعرض V1.5 label بجانب الاسم التقني الداخلي
# ==============================================================================
INTERNAL_TO_V15: dict[str, str] = {
    "pending": "IN_REVIEW",
    "awaiting_signature": "IN_EXECUTION",  # المستند في مرحلة توقيع
    "awaiting_delegate": "IN_EXECUTION",   # المندوب ينفّذ إجراءً حكوميًا
    "ready_for_pickup": "IN_EXECUTION",    # جاهز للتسليم النهائي
    "completed": "COMPLETED",
    "rejected": "REJECTED",
    "cancelled": "CANCELLED",
    "returned": "NEEDS_INFO",
}


def request_v15_status(internal_status: str) -> str:
    """يرجّع V1.5 canonical status من internal status. يعيد الكود القديم إن لم يوجد ربط."""
    return INTERNAL_TO_V15.get(internal_status, internal_status.upper())


def as_dict() -> dict:
    """كامل المخطط للـ /api/requests/status-model."""
    return {
        "request_lifecycle": REQUEST_LIFECYCLE,
        "document_lifecycle": DOCUMENT_LIFECYCLE,
        "step_types": STEP_TYPES,
        "internal_to_v15": INTERNAL_TO_V15,
        "spec_reference": "V1.5 Consolidated Revision 2, §3 (Status Model) + V2.2 §3.2-§3.3",
    }
