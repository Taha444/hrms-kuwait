# -*- coding: utf-8 -*-
"""
نظام الصلاحيات (Permission-based) — كل صلاحية تمثل فعلًا محددًا (Action).
- Super Admin: يتجاوز كل الصلاحيات ويشرف على كل الشركات.
- Company Manager: مقيّد بشركته، وله مجموعة صلاحيات افتراضية واسعة.
- Employee: لا يملك إلا الصلاحيات المُسندة إليه صراحةً (داخل شركته فقط).
"""
from datetime import date
from functools import wraps

from flask import jsonify, session

import db

# كتالوج الصلاحيات (الفعل: الوصف العربي)
PERMISSIONS = {
    "view_employee":     "عرض الموظفين",
    "create_employee":   "إضافة موظف",
    "edit_employee":     "تعديل موظف",
    "delete_employee":   "حذف موظف",
    "manage_licenses":   "إدارة التراخيص",
    "manage_permits":    "إدارة الإقامات وأذونات العمل",
    "upload_documents":  "رفع المستندات",
    "manage_deductions": "إدارة الخصومات",
    "manage_leaves":     "إدارة الإجازات",
    "manage_attendance": "إدارة الحضور والانصراف",
    "manage_departments": "إدارة الأقسام",
    "manage_disciplinary": "إدارة الجزاءات التأديبية",
    "manage_assets":     "إدارة العُهد والأصول",
    "manage_performance": "إدارة تقييم الأداء",
    "run_payroll":       "تشغيل مسيّر الرواتب",
    "view_payroll":      "عرض الرواتب",
    "calculate_eos":     "حساب مكافأة نهاية الخدمة",
    "view_reports":      "عرض التقارير",
    "export_reports":    "تصدير التقارير",
    "view_alerts":       "عرض التنبيهات",
    "manage_users":      "إدارة المستخدمين والصلاحيات",
    "manage_company":    "إدارة بيانات الشركة",
    "manage_companies":  "إدارة جميع الشركات (إدارة عليا)",
}

# قوالب صلاحيات جاهزة
PERMISSION_TEMPLATES = {
    "hr_officer": {
        "label": "موظف موارد بشرية",
        "perms": ["view_employee", "create_employee", "edit_employee", "manage_permits",
                  "manage_leaves", "upload_documents", "view_alerts", "view_reports"],
    },
    "viewer": {
        "label": "مطّلع فقط",
        "perms": ["view_employee", "view_reports", "view_alerts"],
    },
    "payroll": {
        "label": "مسؤول رواتب",
        "perms": ["view_employee", "manage_deductions", "manage_attendance", "run_payroll",
                  "view_payroll", "calculate_eos", "view_reports", "export_reports"],
    },
    "company_admin": {
        "label": "مدير شركة (كل الصلاحيات)",
        "perms": list(PERMISSIONS.keys()),
    },
}

# صلاحيات Company Manager الافتراضية (كل شيء عدا إدارة كل الشركات)
COMPANY_MANAGER_DEFAULT = [p for p in PERMISSIONS if p != "manage_companies"]


def current_user():
    """يرجع بيانات المستخدم الحالي من الجلسة (أو None)."""
    uid = session.get("uid")
    if not uid:
        return None
    row = db.query("SELECT * FROM users WHERE id=? AND is_active=1", (uid,), one=True)
    return db.row_to_dict(row)


def get_user_permissions(user):
    """يرجع مجموعة الصلاحيات الفعّالة للمستخدم (مع استبعاد المنتهية)."""
    if not user:
        return set()
    role = user["role"]
    if role == "super_admin":
        return set(PERMISSIONS.keys()) | {"manage_companies"}
    if role == "company_manager":
        return set(COMPANY_MANAGER_DEFAULT)
    # موظف: الصلاحيات المسندة غير المنتهية
    rows = db.query("SELECT perm_code, expires_at FROM user_permissions WHERE user_id=?", (user["id"],))
    today = date.today().isoformat()
    perms = set()
    for r in rows:
        if r["expires_at"] and r["expires_at"] < today:
            continue
        perms.add(r["perm_code"])
    return perms


def has_permission(user, perm):
    if not user:
        return False
    if user["role"] == "super_admin":
        return True
    return perm in get_user_permissions(user)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"error": "يجب تسجيل الدخول"}), 401
        return fn(*args, **kwargs)
    return wrapper


def require_perm(perm):
    """مزخرف يتحقق من امتلاك المستخدم صلاحية معينة."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return jsonify({"error": "يجب تسجيل الدخول"}), 401
            if not has_permission(user, perm):
                return jsonify({"error": "ليس لديك صلاحية لهذا الإجراء", "missing_permission": perm}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def super_admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"error": "يجب تسجيل الدخول"}), 401
        if user["role"] != "super_admin":
            return jsonify({"error": "هذا الإجراء للإدارة العليا فقط"}), 403
        return fn(*args, **kwargs)
    return wrapper


def scope_company_id(user, requested_company_id=None):
    """
    يطبّق مبدأ العزل:
    - Super Admin: يستطيع تحديد company_id؛ وإن لم يحدد فالنطاق كل الشركات (None).
    - غير ذلك: يُجبر على company_id الخاص به بغض النظر عما طُلب.
    """
    if user["role"] == "super_admin":
        return int(requested_company_id) if requested_company_id else None
    return user["company_id"]
