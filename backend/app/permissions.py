# -*- coding: utf-8 -*-
"""نظام الصلاحيات (Permission-based) — كل صلاحية تمثل فعلًا محددًا (Action).

الأدوار:
- super_admin    : الإدارة العليا — يتجاوز كل الصلاحيات ويشرف على كل الشركات.
- company_owner  : صاحب الشركات — عرض + موافقات عبر كل شركاته.
- company_manager: مدير شركة — صلاحيات واسعة داخل شركته.
- branch_supervisor: مسؤول فرع — أول معتمِد لطلبات موظفي فرعه.
- hr             : موارد بشرية — الاعتماد النهائي والطباعة والأرشفة.
- delegate       : المندوب / الشؤون القانونية — تجديدات وإذن المغادرة.
- employee       : خدمة ذاتية — لا يملك إلا ما يُسنَد إليه.
"""

# كتالوج الصلاحيات (الفعل: الوصف العربي)
PERMISSIONS: dict[str, str] = {
    "view_employee": "عرض الموظفين",
    "create_employee": "إضافة موظف",
    "edit_employee": "تعديل موظف",
    "delete_employee": "حذف موظف",
    "manage_branches": "إدارة الفروع والمواقع",
    "manage_departments": "إدارة الإدارات/الأقسام",
    "manage_licenses": "إدارة التراخيص",
    "manage_permits": "إدارة الإقامات وأذونات العمل",
    "upload_documents": "رفع المستندات",
    "view_documents": "عرض وتنزيل المستندات",
    "manage_deductions": "إدارة الخصومات",
    "manage_leaves": "إدارة الإجازات",
    "manage_attendance": "إدارة الحضور والانصراف",
    "view_attendance": "عرض الحضور",
    "record_attendance": "تسجيل الحضور (خدمة ذاتية)",
    "run_payroll": "تشغيل مسيّر الرواتب",
    "view_payroll": "عرض الرواتب",
    "calculate_eos": "حساب مكافأة نهاية الخدمة",
    "view_reports": "عرض التقارير",
    "export_reports": "تصدير التقارير",
    "view_audit": "عرض سجل التدقيق",
    "terminate_employee": "إنهاء خدمة موظف",
    "view_tasks": "عرض المهام والتنبيهات",
    "manage_tasks": "إدارة المهام",
    "submit_request": "تقديم الطلبات (خدمة ذاتية)",
    "approve_request": "اعتماد الطلبات",
    "manage_request_types": "إدارة أنواع الطلبات وسلاسل الموافقات",
    "manage_templates": "إدارة الصيغ والنماذج وطباعتها",
    "process_delegate_tasks": "إجراءات المندوب (تجديد/إذن مغادرة)",
    "manage_users": "إدارة المستخدمين والصلاحيات",
    "manage_company": "إدارة بيانات الشركة",
    "manage_companies": "إدارة جميع الشركات (إدارة عليا)",
    "transfer_employee": "نقل موظف بين الشركات",
    "view_actual_salary": "عرض الراتب الفعلي",
    "edit_actual_salary": "تعديل الراتب الفعلي",
}

# قوالب صلاحيات جاهزة
PERMISSION_TEMPLATES: dict[str, dict] = {
    "hr_officer": {
        "label": "موظف موارد بشرية",
        "perms": ["view_employee", "create_employee", "edit_employee", "manage_permits",
                  "manage_leaves", "upload_documents", "view_documents", "view_attendance",
                  "approve_request", "view_tasks", "view_reports", "submit_request"],
    },
    "branch_supervisor": {
        "label": "مسؤول فرع",
        "perms": ["view_employee", "view_attendance", "approve_request", "view_tasks",
                  "view_reports", "submit_request"],
    },
    "delegate": {
        "label": "مندوب / شؤون قانونية",
        "perms": ["view_employee", "view_documents", "upload_documents", "manage_permits",
                  "process_delegate_tasks", "view_tasks", "submit_request"],
    },
    "viewer": {
        "label": "مطّلع فقط",
        "perms": ["view_employee", "view_reports", "view_tasks", "view_documents"],
    },
    "payroll": {
        "label": "مسؤول رواتب",
        "perms": ["view_employee", "manage_deductions", "manage_attendance", "view_attendance",
                  "run_payroll", "view_payroll", "calculate_eos", "view_reports", "export_reports"],
    },
    "company_admin": {
        "label": "مدير شركة (كل الصلاحيات)",
        "perms": [p for p in PERMISSIONS if p != "manage_companies"],
    },
}

# صلاحيات افتراضية لكل دور (يُمنحها النظام تلقائيًا دون الحاجة لإسناد فردي)
_ALL = set(PERMISSIONS.keys())
_COMPANY_ALL = {p for p in PERMISSIONS if p != "manage_companies"}

ROLE_DEFAULT_PERMS: dict[str, set[str]] = {
    "super_admin": _ALL | {"manage_companies"},
    # المالك: دور رقابي للاطلاع فقط (متابعة الشركات/الفروع/الأداء/التقارير) — لا أعمال تشغيلية.
    # يشمل الاطلاع على سجل التدقيق والرواتب (رقابة/حوكمة) دون أي صلاحية تنفيذ (FIX-010).
    "company_owner": {"view_employee", "view_reports", "export_reports", "view_tasks",
                      "view_actual_salary", "view_audit", "view_payroll", "view_documents",
                      "view_attendance"},
    # مدير الشركة: التشغيل اليومي فقط — موظفون/فروع/إدارات/إجازات/طلبات/تقارير/مستخدمو شركته.
    # لا رواتب/خصومات (المحاسب)، لا EOS/إنهاء خدمة (HR)، لا إقامات/تراخيص (PRO)،
    # لا إعدادات نظام/شركات/قوالب/تدقيق/نقل بين الشركات (الإدارة العليا).
    # submit_request إلزامي (P0-05): مدير الشركة يبدأ نيابًة عن الموظف طلبات إدارية/داخلية
    # كثيرة (ترقية، نقل، تجديد عقد...)، وبدونها كان /requests (POST) يرفضه بـ403.
    "company_manager": {"view_employee", "create_employee", "edit_employee", "delete_employee",
                        "view_documents", "upload_documents", "manage_leaves", "view_attendance",
                        "manage_branches", "manage_departments", "approve_request",
                        "view_reports", "export_reports", "view_tasks", "manage_tasks",
                        "manage_users", "submit_request"},
    # محاسب الشركة: الرواتب والخصومات + الراتب الفعلي (مالي)، وهو أيًضا موظف له ملف
    # وحضور خاص به (submit_request/record_attendance) مثل أي موظف آخر بالشركة.
    # approve_request إلزامي (P0-01): المحاسب معتمِد فعلي في مراحل كثيرة (السلف/القروض
    # والاعتماد المالي في REQOT/REQBANK/REQADV/REQEXP/REQPAY/REQDED/ADMDED/REQCLR/REQEOS)،
    # وبدونها كان /decide و/received يرفضانه بـ403 فتتوقف الطلبات المالية عنده للأبد رغم
    # أن can_decide يتحقق أصًلا من كونه معتمِد المرحلة الفعلي.
    "accountant": {"view_employee", "view_payroll", "run_payroll", "manage_deductions",
                   "view_actual_salary", "edit_actual_salary",
                   "view_reports", "export_reports", "view_tasks",
                   "submit_request", "record_attendance", "approve_request"},
    # مسؤول الفرع: إدارة فرعه فقط — متابعة موظفيه، مراجعة الطلبات، رفع التقارير.
    # النطاق مقيّد بفروعه (resolve_scope=multi) فلا يرى بيانات الفروع الأخرى.
    # submit_request (P0-05): يبدأ طلبات تشغيلية عن موظفيه (تغيير وردية، مهمة خارجية...).
    "branch_supervisor": {"view_employee", "view_attendance", "approve_request",
                          "view_tasks", "view_reports", "export_reports", "submit_request"},
    # الشؤون القانونية/HR: مسؤول عن الموظفين فقط (لا حكومة/إقامات/تراخيص).
    # دورة حياة الموظف: إضافة/تعديل/عقود (مستندات)/إجازات/إنذارات/خصومات/EOS + خطابات الإنذار (قوالب).
    # approve_request مطلوب لأن HR مرحلة في سلسلة طلبات الموظفين (مراجعة/توقيع/استلام).
    # submit_request إلزامي (P0-05): HR هو من يبدأ فعليًا معظم الإجراءات الداخلية (REQEOS،
    # REQCLR، ADMEMP/ADMACTUAL/ADMDED/ADMVIO/ADMWARN/ADMTASK/ADMMISS/ADMSIGN) نيابًة عن
    # الموظف؛ بدونها لم يكن أي منها قابًلا للإنشاء أصًلا (لا HR ولا company_manager كان
    # يملك submit_request)، وهو السبب الحقيقي وراء توقّف REQEOS/REQCLR (P0-05).
    "hr": {"view_employee", "create_employee", "edit_employee",
           "view_documents", "upload_documents",
           "manage_leaves", "manage_deductions",
           "approve_request", "calculate_eos", "terminate_employee",
           "manage_templates", "view_tasks",
           "view_attendance", "manage_attendance",  # تصحيح واعتماد سجلات الحضور (FIX-015)
           "submit_request"},
    # PRO / المندوب: كل المعاملات الحكومية فقط (إقامات/أذونات/تراخيص/جهات/تجديدات/ملاحظات/مواعيد).
    # لا رواتب/عقود/EOS/إجازات/خصومات/تقارير HR. submit_request (P0-05): يبدأ معاملات
    # حكومية (ADMLIC، REQWP...) نيابًة عن الموظف.
    "delegate": {"view_employee", "create_employee", "view_documents", "upload_documents",
                 "manage_permits", "manage_licenses", "process_delegate_tasks", "submit_request",
                 "view_tasks", "manage_tasks"},
    # موظف إداري مرن: بلا صلاحيات افتراضية — تُمنح بالكامل عبر مصفوفة الأذونات
    "admin_employee": set(),
    # الموظف: خدمة ذاتية فقط (لا إحصائيات شركة)
    "employee": {"submit_request", "record_attendance", "view_tasks"},
}

ROLES = list(ROLE_DEFAULT_PERMS.keys())

# المستوى الهرمي لكل دور (الأعلى يدير الأدنى فقط)
ROLE_LEVEL: dict[str, int] = {
    "super_admin": 100,
    "company_owner": 80,
    "company_manager": 60,
    "hr": 40,
    "branch_supervisor": 40,
    "accountant": 35,
    "delegate": 30,
    "admin_employee": 20,
    "employee": 10,
}

# الأدوار التي ترتبط بملف موظف وتبصم حضورًا (خدمة ذاتية)
ATTENDANCE_ROLES = {"employee"}

# الأدوار التي ترى كل الشركات (تختار بينها)
CROSS_COMPANY_ROLES = {"super_admin", "company_owner"}

# تسمية عربية لكل دور — تُستخدم لعرض سلسلة الاعتماد في المستندات المطبوعة (PDF/HTML) بدل
# رمز الدور التقني الخام (P0-04: لا يظهر company_manager/hr/branch_supervisor في مستند رسمي).
ROLE_LABEL_AR: dict[str, str] = {
    "branch_supervisor": "المسؤول المباشر", "company_manager": "المدير العام",
    "hr": "شؤون الموظفين/القانونية", "delegate": "المندوب", "accountant": "المحاسب",
    "company_owner": "صاحب الشركة", "super_admin": "الإدارة العليا", "employee": "الموظف",
}


def role_level(role: str) -> int:
    return ROLE_LEVEL.get(role, 0)


def can_manage_role(actor_role: str, target_role: str) -> bool:
    """يحق للمستخدم إدارة من هم أدنى منه مستوى فقط (والإدارة العليا تدير الجميع)."""
    if actor_role == "super_admin":
        return True
    return role_level(actor_role) > role_level(target_role)


def effective_permissions(role: str, assigned: set[str]) -> set[str]:
    """الصلاحيات الفعّالة = الافتراضية للدور + المُسندة صراحةً (غير المنتهية)."""
    if role == "super_admin":
        return _ALL | {"manage_companies"}
    return ROLE_DEFAULT_PERMS.get(role, set()) | (assigned or set())


def has_permission(role: str, assigned: set[str], perm: str) -> bool:
    if role == "super_admin":
        return True
    return perm in effective_permissions(role, assigned)


# ===========================================================================
# نظام الأذونات الدقيق: مصفوفة (صفحة × فعل) لكل مستخدم — متوافق خلفيًا.
# من ليس له منح دقيقة لصفحة معيّنة يبقى على صلاحيات دوره الافتراضية.
# ===========================================================================
ACTIONS_AR = {
    "read": "قراءة", "add": "إضافة", "edit": "تعديل", "delete": "حذف",
    "print": "طباعة", "export": "تصدير", "approve": "اعتماد",
}

# ربط الصلاحية القديمة بـ (الصفحة، الفعل) — فقط ما نريد التحكم الدقيق فيه
LEGACY_TO_PA: dict[str, tuple[str, str]] = {
    "view_employee": ("employees", "read"),
    "create_employee": ("employees", "add"),
    "edit_employee": ("employees", "edit"),
    "delete_employee": ("employees", "delete"),
    "view_reports": ("reports", "read"),
    "export_reports": ("reports", "export"),
    "approve_request": ("requests", "approve"),
    "submit_request": ("requests", "add"),
    "view_documents": ("documents", "read"),
    "upload_documents": ("documents", "add"),
    "view_attendance": ("attendance", "read"),
    "record_attendance": ("attendance", "add"),
    "manage_permits": ("permits", "edit"),
    "manage_licenses": ("licenses", "edit"),
    "view_payroll": ("payroll", "read"),
    "run_payroll": ("payroll", "add"),
    "manage_templates": ("templates", "edit"),
    "manage_users": ("users", "edit"),
    "view_audit": ("audit", "read"),
    "manage_branches": ("branches", "edit"),
    "calculate_eos": ("eos", "read"),
}
PA_TO_LEGACY: dict[tuple[str, str], str] = {v: k for k, v in LEGACY_TO_PA.items()}

PAGE_LABELS = {
    "employees": "الموظفون", "reports": "التقارير", "requests": "الطلبات",
    "documents": "المستندات", "attendance": "الحضور", "permits": "الإقامات",
    "licenses": "التراخيص", "payroll": "الرواتب", "templates": "الصيغ",
    "users": "المستخدمون", "audit": "سجل التدقيق", "branches": "الفروع", "eos": "نهاية الخدمة",
}

# السطح الكامل للأفعال المتاحة لكل صفحة — المرجع الوحيد لبناء المصفوفة وفرضها.
# يشمل الأفعال السبعة [قراءة، إضافة، تعديل، حذف، طباعة، تصدير، اعتماد] حيثما تنطبق.
PAGE_ACTIONS: dict[str, list[str]] = {
    "employees":  ["read", "add", "edit", "delete", "print", "export"],
    "reports":    ["read", "export", "print"],
    "requests":   ["read", "add", "approve", "print"],
    "documents":  ["read", "add", "delete", "print"],
    "attendance": ["read", "add", "export"],
    "permits":    ["read", "edit", "print"],
    "licenses":   ["read", "edit", "print"],
    "payroll":    ["read", "add", "export", "print"],
    "templates":  ["read", "edit", "print"],
    "users":      ["read", "edit"],
    "audit":      ["read", "export"],
    "branches":   ["read", "edit"],
    "eos":        ["read", "print"],
}

# الأفعال المشتقّة: عند غياب منح مخصّصة، تَرِث افتراضيًا من فعل أساس بنفس الصفحة.
# (من يستطيع العرض يطبع/يصدّر افتراضيًا؛ من يستطيع التعديل يعتمد) — قابلة للإلغاء بالمصفوفة.
_DERIVED_ACTION_BASE = {"print": "read", "export": "read", "approve": "edit"}


def permission_matrix_catalog() -> list[dict]:
    """قائمة الصفحات وأفعالها المتاحة (لبناء واجهة المصفوفة)."""
    order = ["read", "add", "edit", "delete", "print", "export", "approve"]
    return [{"code": p, "label": PAGE_LABELS.get(p, p),
             "actions": [a for a in order if a in set(acts)]}
            for p, acts in sorted(PAGE_ACTIONS.items())]


def has_page_action(role: str, assigned: set[str], page: str, action: str) -> bool:
    """يتحقق من صلاحية (صفحة، فعل): المنح الدقيقة تتقدّم، وإلا دور المستخدم.

    ترتيب الحسم: super_admin ← منح المصفوفة المخصّصة ← الصلاحية القديمة المكافئة ←
    فعل مشتقّ يرث من فعل أساس (طباعة/تصدير←قراءة، اعتماد←تعديل).
    """
    if role == "super_admin":
        return True
    page_grants = {c.split(".", 1)[1] for c in assigned if c.startswith(page + ".")}
    if page_grants:  # للمستخدم مصفوفة مخصّصة لهذه الصفحة → تتحكّم وحدها
        return action in page_grants
    legacy = PA_TO_LEGACY.get((page, action))
    if legacy:
        return legacy in ROLE_DEFAULT_PERMS.get(role, set()) or legacy in assigned
    # فعل بلا صلاحية قديمة مكافئة (طباعة/تصدير/اعتماد) → يرث من فعل الأساس
    base = _DERIVED_ACTION_BASE.get(action)
    if base and base != action:
        return has_page_action(role, assigned, page, base)
    return False


def check_legacy(role: str, assigned: set[str], perm: str) -> bool:
    """نقطة التحقق الموحّدة: تحوّل الصلاحية القديمة لمصفوفة دقيقة إن أمكن."""
    pa = LEGACY_TO_PA.get(perm)
    if pa:
        return has_page_action(role, assigned, pa[0], pa[1])
    return has_permission(role, assigned, perm)
