# -*- coding: utf-8 -*-
"""من يرى أي حقل من بيانات الموظف — قاعدة واحدة لكل منفذ.

**العطل الذي أنتج هذه الوحدة**: السياسة كانت مكتوبة داخل مسار التفصيل
(``GET /api/employees/{id}``) وحده — يُقنَّع فيها الرقم المدني والجواز لمن
لا يملك الاطلاع، وتُمسح الحقول المالية عن المندوب والهوياتية عن المحاسب.

**وسرد الموظفين لم يمرّ بها إطلاًقا.** فكان ``GET /api/employees`` يعيد
الجواز والراتب لكل من يستطيع السرد — ومنهم **مسؤول الفرع**. أي أن الحماية
قائمة على الشاشة التي تعرض موظًفا واحًدا، وغائبة عن الشاشة التي تعرضهم
جميًعا. ومن أراد البيانات لا يفتح الملف بل يفتح القائمة.

وهذا نمط يتكرّر: قاعدة واحدة في موضعين — أحدهما يُصان والآخر يُنسى. فتُكتب
هنا مرة، ويناديها كل منفذ.

**القواعد، وسبب كلٍّ منها:**

- **الجواز** (``passport_number`` و``passport_expiry``) وثيقة هوية: يراها
  من يرى ملف الموظف (``view_documents``). ومسؤول الفرع يدير حضور فرعه
  وإجازاته ولا يقدّم معاملات حكومية، فلا يحتاجها. وكذلك المحاسب: الاسم
  والرقم الوظيفي يكفيان لتشغيل الرواتب.

- **الراتب الأساسي** بيان تعاقدي لا مالي بحت: يراه من يرى ملف الموظف
  (``view_documents``) أو من يعالج الرواتب (``view_payroll``). ومسؤول
  الفرع لا يملك أًيا منهما.

- **الرقم المدني** يبقى لمسؤول الفرع عمًدا: هو المعرّف الأول للشخص في
  الكويت، وبه يُبحث وتُطابَق السجلات. وحجبه عنه يمنعه من تمييز موظفَين
  متشابهَي الاسم في فرعه — ضررٌ بلا مقابل. ويُحذف عن **المحاسب** وحده،
  وهي سياسة قائمة من قبل في مسار الملف (:data:`ROLE_STRIPS`) امتدّت هنا
  إلى السرد: كانت مطبَّقة في موضع دون موضع.

- **صاحب الملف يرى ملفه كامًلا** أًيا كان دوره.
"""
from __future__ import annotations

#: الحقل ← الصلاحيات التي تفتحه (واحدة تكفي).
SENSITIVE_FIELDS: dict[str, tuple[str, ...]] = {
    "passport_number": ("view_documents",),
    "passport_expiry": ("view_documents",),
    "basic_salary": ("view_documents", "view_payroll"),
    "actual_salary": ("view_actual_salary",),
    "iban": ("view_payroll", "view_actual_salary"),
    "bank_account": ("view_payroll", "view_actual_salary"),
}

#: أدوار ترى كل شيء بحكم موقعها.
_UNRESTRICTED_ROLES = ("super_admin", "company_owner")


def visible_fields(user, perms) -> set[str]:
    """الحقول الحسّاسة التي يراها هذا المستخدم."""
    from .permissions import has_permission

    if user.role in _UNRESTRICTED_ROLES:
        return set(SENSITIVE_FIELDS)
    return {
        field
        for field, needed in SENSITIVE_FIELDS.items()
        if any(has_permission(user.role, perms, p) for p in needed)
    }


def redact_employee(data: dict, user, perms, *, employee_id=None) -> dict:
    """يحذف من بيانات الموظف ما لا يحقّ لهذا المستخدم رؤيته.

    **يُحذف الحقل ولا يُصفَّر**: قيمة ``None`` تُقرأ «لا جواز لهذا الموظف»
    وهو خبر خاطئ يقود إلى فتح معاملة ناقصة. وغياب المفتاح يُقرأ «لا تراه»،
    وهو الصدق.

    و``employee_id`` هو صاحب السجل: من يرى ملفه يراه كامًلا.
    """
    if employee_id is not None and user.employee_id == employee_id:
        return data

    allowed = visible_fields(user, perms)
    stripped = set(ROLE_STRIPS.get(user.role, ()))
    return {k: v for k, v in data.items()
            if k not in stripped
            and (k not in SENSITIVE_FIELDS or k in allowed)}


def redact_employees(rows: list[dict], user, perms) -> list[dict]:
    """نفس القاعدة على قائمة — وهي المنفذ الذي كان مكشوًفا."""
    return [redact_employee(r, user, perms, employee_id=r.get("id")) for r in rows]


#: حقول لا يحتاجها دور بعينه في سجلّ غيره — تُحذف مهما كانت صلاحياته.
#:
#: كانت هذه القوائم مكتوبة **ثلاث مرات**: في ``get_employee`` وفي
#: ``employee_profile``، ولا شيء منها في السرد. فأخذ مسؤول الفرع الجواز
#: صريًحا من المسار الذي لم يُذكر فيه. وتوحيدها هنا يجعل إضافة دور أو
#: حقل تسري على المنافذ الثلاثة معًا.
ROLE_STRIPS: dict[str, tuple[str, ...]] = {
    # المحاسب: الاسم والرقم الوظيفي يكفيان لتشغيل الرواتب.
    "accountant": (
        "civil_id", "passport_number", "passport_expiry", "date_of_birth",
        "address", "nationality", "gender", "marital_status", "email", "phone",
        "personal_photo_path", "health_insurance",
        "contract_type", "contract_start_date", "contract_end_date",
    ),
    # المندوب: يقدّم المعاملات الحكومية ولا شأن له بالمالي والتعاقدي.
    "delegate": (
        "basic_salary", "actual_salary", "hire_date", "job_title",
        "contract_type", "contract_start_date", "contract_end_date",
    ),
}
