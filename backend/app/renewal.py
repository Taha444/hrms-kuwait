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
# R4 §7 — بين استلام الوثائق الحكومية وإغلاق المعاملة: HR يتحقق من التطابق
# (رقم الإقامة الجديد + التاريخ + الرسوم) قبل إغلاق التذكرة نهائيًا.
PENDING_HR_VERIFY = "pending_hr_verify"
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
    PENDING_HR_VERIFY: {"ar": "بانتظار تحقق شؤون الموظفين", "en": "Pending HR verification"},
    COMPLETED: {"ar": "مكتملة", "en": "Completed"},
}

# مستندات المعاملة ونوع كل منها
DOC_CONTRACT_GOV = "renewal_contract_gov"          # عقد العمل الحكومي (يرفعه المندوب)
DOC_CONTRACT_INTERNAL = "renewal_contract_internal"  # (اختياري R9) — تركة قديمة
DOC_SIGNED_GOV = "renewal_signed_gov"              # النسخة الموقّعة (الموظف)
DOC_SIGNED_INTERNAL = "renewal_signed_internal"    # (اختياري R9) — تركة قديمة
# RNW-09 — النسخة الثالثة: العقد بتوقيع الطرفين، يرفعها المندوب بعد أن يوقّع
# صاحب الشركة خارج النظام. الثلاث نسخ تبقى محفوظة: المولّدة لا تُستبدل بالموقّعة
# من الموظف، والموقّعة من الموظف ليست النهائية. دمجها في حقل واحد يفقد القدرة
# على إثبات أي نسخة قُدّمت للجهة الحكومية.
DOC_CONTRACT_FINAL = "renewal_contract_final"      # موقّع من الطرفين (المندوب)
DOC_WORK_PERMIT = "work_permit"                    # إذن العمل الجديد (ملف الموظف)
DOC_CIVIL_CARD = "civil_id"                        # البطاقة المدنية الجديدة (ملف الموظف)

# R9 §1 — تغيير جوهري في workflow:
# **التجديد يحتاج العقد الحكومي فقط**؛ عقد الشركة يُوقَّع مرة واحدة عند التعيين
# الأصلي ولا يُعاد كل مرة. الرفع اللاحق للعقد الداخلي مسموح (تركة قديمة) لكن
# ليس مطلوبًا لانتقال الحالة.
#
# REQUIRED_* = يجب رفعه للانتقال من AWAITING_CONTRACTS → AWAITING_SIGNATURE
# ACCEPTED_* = مسموح رفعه في المرحلة (يشمل الاختياري القديم)
REQUIRED_CONTRACT_DOCS = (DOC_CONTRACT_GOV,)
REQUIRED_SIGNED_DOCS = (DOC_SIGNED_GOV,)
ACCEPTED_CONTRACT_DOCS = (DOC_CONTRACT_GOV, DOC_CONTRACT_INTERNAL)
ACCEPTED_SIGNED_DOCS = (DOC_SIGNED_GOV, DOC_SIGNED_INTERNAL)

# aliases خلفية لكود قديم أو تنزيل مستندات موجودة سابقًا (السلوك السابق: يشمل الاثنين)
CONTRACT_DOCS = ACCEPTED_CONTRACT_DOCS
SIGNED_DOCS = ACCEPTED_SIGNED_DOCS

# RNW-09 — نسخ العقد الحكومي الثلاث في مجموعة واحدة. كل موضع يسأل "هل هذا
# مستند عقد؟" يسأل هنا؛ فإضافة نسخة رابعة يوًما لا تتطلب تتبّع قوائم متفرّقة
# — وهو ما كاد يحدث: التنزيل كان يجمع CONTRACT_DOCS + SIGNED_DOCS يدوًيا،
# فالنسخة النهائية ما كانت لتُنزَّل.
ALL_CONTRACT_DOCS = ACCEPTED_CONTRACT_DOCS + ACCEPTED_SIGNED_DOCS + (DOC_CONTRACT_FINAL,)


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


# RNW-06 — حقول لا يجوز أن يُولَّد العقد الحكومي بدونها. الناقص كان يُطبع
# "................" في المستند، أي عقد يُقدَّم لجهة رسمية بمربّعات فارغة —
# والموظف يوقّعه وهو ناقص. الرفض بذكر اسم الحقل أوضح من مستند معيب.
GOV_CONTRACT_REQUIRED_FIELDS = {
    "employee_name": "اسم الموظف",
    "civil_id": "الرقم المدني",
    "nationality": "الجنسية",
    "job_title": "المسمّى الوظيفي",
    "company_name": "اسم الشركة",
}
