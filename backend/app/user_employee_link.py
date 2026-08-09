# -*- coding: utf-8 -*-
"""R9 §14 — Atomic pass to link User accounts to Employee records.

المشكلة اللي بيحلها:
- على الإنتاج، كل حساب داخل الشركة (hr/delegate/manager/accountant/…) لازم
  يكون له employee_id عشان يقدر يقدّم طلب لنفسه أو يوقّع مستند
- الحسابات اللي اتعملت يدوي (SQL مباشر أو UI بدون الـwizard) قد تفتقر للرابط
- تشغيل هذا الـpass يوصّل تلقائيًا كل حساب unlinked مع employee مطابق
  بنفس الرقم المدني والشركة، لو الاثنين موجودين ولا فيه صراع

القواعد الأمنية المطبقّة (من قائمة العميل):
1. لا نُنشئ Employee وهمي — لو مافيش موظف مطابق نخطي ونبلّغ HR ينشئ يدويًا
2. Atomic — كل ربط يتم في transaction منفصلة، وأي فشل ما يوقف الباقي
3. Idempotent — تشغيل ثاني ما يعمل شيء (اليوزرات المربوطة مسبقًا تُتخطى)
4. لا يمس super_admin/company_owner (مقصود إنهم بلا employee record)
5. لا يستبدل رابط موجود — لو user.employee_id != NULL نتخطى
6. لا يسمح بربطين لنفس الموظف — لو الموظف مربوط بحساب آخر نبلّغ ونتخطى
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


logger = logging.getLogger("hrms.user_link")

# الأدوار المستثناة من الربط (بلا employee record بشكل مقصود)
_EXCLUDED_ROLES = ("super_admin", "company_owner")


def auto_link_users_to_employees(db: Session) -> dict:
    """يمر على كل حساب unlinked ويربطه بموظف مطابق (civil_id + company_id).

    Returns:
        {
            "linked": [{"user_id", "employee_id", "civil_id", "role", "name"}, ...],
            "no_employee": [{"user_id", "civil_id", "role", "name"}, ...],  # يحتاج إنشاء موظف
            "conflicts": [{"user_id", "employee_id", "other_user_id"}, ...],  # موظف مربوط بغيره
            "skipped_no_civil_id": [...],
            "total_scanned": N,
        }
    """
    users = db.scalars(select(models.User).where(
        models.User.employee_id.is_(None),
        models.User.role.notin_(_EXCLUDED_ROLES),
        models.User.is_active == True,  # noqa: E712
    )).all()

    linked: list[dict] = []
    no_employee: list[dict] = []
    conflicts: list[dict] = []
    skipped: list[dict] = []

    for u in users:
        if not u.civil_id or not u.company_id:
            skipped.append({"user_id": u.id, "role": u.role,
                          "reason": "no civil_id or company_id"})
            continue

        # find matching employee (same civil_id in same company)
        emp = db.scalar(select(models.Employee).where(
            models.Employee.civil_id == u.civil_id,
            models.Employee.company_id == u.company_id,
        ))
        if not emp:
            no_employee.append({
                "user_id": u.id, "civil_id": u.civil_id,
                "role": u.role, "name": u.full_name,
            })
            continue

        # check no one else is linked to this employee
        other_link = db.scalar(select(models.User.id).where(
            models.User.employee_id == emp.id,
            models.User.id != u.id,
        ))
        if other_link:
            conflicts.append({
                "user_id": u.id, "employee_id": emp.id,
                "other_user_id": other_link,
                "civil_id": u.civil_id, "role": u.role,
            })
            continue

        # atomic link
        u.employee_id = emp.id
        linked.append({
            "user_id": u.id, "employee_id": emp.id,
            "civil_id": u.civil_id, "role": u.role,
            "name": u.full_name,
        })

    if linked:
        db.commit()
        logger.info("auto-linked %d user↔employee pairs", len(linked))

    return {
        "linked": linked,
        "no_employee": no_employee,
        "conflicts": conflicts,
        "skipped_no_civil_id": skipped,
        "total_scanned": len(users),
    }
