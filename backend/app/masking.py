# -*- coding: utf-8 -*-
"""إخفاء الحقول الحساسة (V1.4 RBAC.Field-Level Permissions).

كل حقل حساس (رقم مدني، جواز، IBAN، هاتف، سبب طبي/تظلم) يمر عبر دالة `mask_*` التي تُظهر
أول/آخر أحرف قليلة فقط ليمكن للأدوار التي ليس لها صلاحية `view_actual_*` أن تعرض السجل بلا
كشف القيمة الكاملة، مع تسجيل أي محاولة تنزيل/عرض حساسة في سجل التدقيق (Audit) عبر الطبقة
الاستدعائية. لا يُطبَّق المسك على من يملك الصلاحية أو الموظف نفسه.
"""
from __future__ import annotations


def mask_civil_id(v: str | None, unmasked: bool = False) -> str | None:
    """الرقم المدني (12 خانة): يُعرض أول 3 وآخر 3 فقط للأدوار غير المصرَّح لها."""
    if not v or unmasked:
        return v
    if len(v) <= 6:
        return "•" * len(v)
    return f"{v[:3]}{'•' * (len(v) - 6)}{v[-3:]}"


def mask_passport(v: str | None, unmasked: bool = False) -> str | None:
    if not v or unmasked:
        return v
    if len(v) <= 4:
        return "•" * len(v)
    return f"{v[:2]}{'•' * (len(v) - 4)}{v[-2:]}"


def mask_iban(v: str | None, unmasked: bool = False) -> str | None:
    """IBAN الكويتي (30 حرف): يُعرض أول 4 (كود الدولة والفحص) وآخر 4 فقط."""
    if not v or unmasked:
        return v
    s = v.replace(" ", "")
    if len(s) <= 8:
        return "•" * len(s)
    return f"{s[:4]}{'•' * (len(s) - 8)}{s[-4:]}"


def mask_phone(v: str | None, unmasked: bool = False) -> str | None:
    if not v or unmasked:
        return v
    if len(v) <= 4:
        return "•" * len(v)
    if len(v) <= 6:
        return f"{v[0]}{'•' * (len(v) - 4)}{v[-3:]}"
    return f"{v[:2]}{'•' * (len(v) - 6)}{v[-4:]}"


def mask_amount(v: float | None, unmasked: bool = False) -> float | str | None:
    if v is None or unmasked:
        return v
    return "***"
