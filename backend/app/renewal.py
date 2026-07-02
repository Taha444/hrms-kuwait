# -*- coding: utf-8 -*-
"""محرّك حالات تجديد الإقامة (DEMO-001/002).

نوعان:
- early  (تجديد مبكر): المتبقّي 31–90 يومًا. مسار: الموظف → المدير → الشؤون → المندوب.
- normal (تجديد عادي): المتبقّي ≤ 30 يومًا. مسار: الموظف → المندوب مباشرة.
- أكثر من 90 يومًا: لا يُسمح بالطلب.
"""

# ---------------- الحالات (11 حالة على الأقل) ----------------
NEW = "new"
PENDING_MANAGER = "pending_manager"
PENDING_HR = "pending_hr"
REJECTED = "rejected"
WITH_DELEGATE = "with_delegate"
AWAITING_CONTRACTS = "awaiting_contracts"
AWAITING_SIGNATURE = "awaiting_signature"
CONTRACTS_SIGNED = "contracts_signed"
RENEWING = "renewing"
AWAITING_CIVIL_CARD = "awaiting_civil_card"
COMPLETED = "completed"

STATUS_LABELS = {
    NEW: {"ar": "طلب جديد", "en": "New"},
    PENDING_MANAGER: {"ar": "بانتظار موافقة مدير الشركة", "en": "Pending manager approval"},
    PENDING_HR: {"ar": "بانتظار موافقة شؤون الموظفين", "en": "Pending HR approval"},
    REJECTED: {"ar": "مرفوض", "en": "Rejected"},
    WITH_DELEGATE: {"ar": "محوّل إلى المندوب", "en": "With delegate"},
    AWAITING_CONTRACTS: {"ar": "بانتظار رفع العقود", "en": "Awaiting contracts upload"},
    AWAITING_SIGNATURE: {"ar": "بانتظار توقيع الموظف", "en": "Awaiting employee signature"},
    CONTRACTS_SIGNED: {"ar": "تم رفع العقود الموقّعة", "en": "Signed contracts uploaded"},
    RENEWING: {"ar": "جاري التجديد", "en": "Renewing"},
    AWAITING_CIVIL_CARD: {"ar": "تم التجديد – بانتظار البطاقة المدنية", "en": "Renewed – awaiting civil card"},
    COMPLETED: {"ar": "مكتملة", "en": "Completed"},
}

# مستندات المعاملة ونوع كل منها
DOC_CONTRACT_GOV = "renewal_contract_gov"          # عقد العمل الحكومي (يرفعه المندوب)
DOC_CONTRACT_INTERNAL = "renewal_contract_internal"  # العقد الداخلي (يرفعه المندوب)
DOC_SIGNED_GOV = "renewal_signed_gov"              # النسخة الموقّعة (الموظف)
DOC_SIGNED_INTERNAL = "renewal_signed_internal"    # النسخة الموقّعة (الموظف)
DOC_WORK_PERMIT = "work_permit"                    # إذن العمل الجديد (ملف الموظف)
DOC_CIVIL_CARD = "civil_id"                        # البطاقة المدنية الجديدة (ملف الموظف)

CONTRACT_DOCS = (DOC_CONTRACT_GOV, DOC_CONTRACT_INTERNAL)
SIGNED_DOCS = (DOC_SIGNED_GOV, DOC_SIGNED_INTERNAL)


def classify(days_left: int) -> str | None:
    """يحدّد نوع التجديد من عدد الأيام المتبقّية (أو None إذا غير مسموح)."""
    if days_left is None:
        return None
    if days_left > 90:
        return None            # مبكر جدًا — غير مسموح
    if days_left <= 30:
        return "normal"
    return "early"             # 31–90 يومًا


def status_label(code: str, lang: str = "ar") -> str:
    return STATUS_LABELS.get(code, {}).get(lang, code)
