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
    "company_owner": {"view_employee", "view_documents", "view_attendance", "approve_request",
                      "view_tasks", "view_reports", "export_reports", "view_payroll",
                      "calculate_eos", "manage_request_types", "view_audit"},
    "company_manager": _COMPANY_ALL,
    "branch_supervisor": set(PERMISSION_TEMPLATES["branch_supervisor"]["perms"]),
    "hr": set(PERMISSION_TEMPLATES["hr_officer"]["perms"]) | {"manage_attendance", "manage_tasks", "manage_templates"},
    "delegate": set(PERMISSION_TEMPLATES["delegate"]["perms"]),
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
    "delegate": 30,
    "employee": 10,
}

# الأدوار التي ترتبط بملف موظف وتبصم حضورًا (خدمة ذاتية)
ATTENDANCE_ROLES = {"employee"}

# الأدوار التي ترى كل الشركات (تختار بينها)
CROSS_COMPANY_ROLES = {"super_admin", "company_owner"}


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
