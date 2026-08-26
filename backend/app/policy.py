# -*- coding: utf-8 -*-
"""V2.2 §7 (STR-05) — قراءة حدود السياسة من البيانات لا من الكود.

ROOT CAUSE: حدود القرار كانت في ثلاث حالات، كلها تمنع تغييرها بلا نشر:
1. مزروعة في الكود (مهلة الإنذار، مقسوم اليوم، رصيد الإجازة السنوي)
2. مكرّرة في مواضع (نافذة "قرب الانتهاء" 30/90 في أربعة ملفات مستقلة)
3. **غير موجودة أصًلا** — حدّ الاعتماد المالي. ولهذا كانت مرحلة "اعتماد فوق
   الحد" (RW-07) غائبة: لا لأن المحرك لا يدعمها بل لأن الحد نفسه لا وجود له.

التسلسل: قاعدة الشركة ← القاعدة العامة في القاعدة ← الافتراضي هنا. الافتراضي
ليس "قيمة صحيحة" بل شبكة أمان: النظام يعمل على قاعدة لم تُبذَر بعد، ويُعلن في
``source`` أن القيمة من الكود لا من سياسة معتمَدة.

كل قراءة تُعيد ``version`` و``source`` لتُحفظ في لقطة الطلب (AC-08، RW-18):
قرار قديم يبقى مفهوًما على ضوء القاعدة التي حكمته لا القاعدة الحالية.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .clock import today as kuwait_today

# المفاتيح المعروفة وقيمها الاحتياطية. القيم مأخوذة مما كان في الكود فعلًا،
# فالسلوك لا يتغيّر بمجرد إدخال الجدول — يتغيّر فقط حين تُعتمَد قاعدة جديدة.
DEFAULTS: dict[str, dict] = {
    # نهاية الخدمة وقانون العمل الكويتي
    "leave.annual_entitlement_days": {"days": 30},
    "eos.notice_days": {"days": 90},
    "eos.day_divisor": {"divisor": 26},

    # نوافذ التنبيه على انتهاء الوثائق — كانت مكرّرة في dashboard/operations/org/renewals
    "expiry.warning_days": {"days": 90},
    "expiry.critical_days": {"days": 30},

    # حدّ الاعتماد المالي — لم يكن له وجود. صفر يعني: لا مرحلة إضافية،
    # وهو السلوك القائم بالضبط، فلا ينكسر شيء قبل أن تُعتمَد قيمة.
    "finance.extra_approval_threshold": {"amount": 0.0, "currency": "KWD"},
    "loan.max_amount": {"amount": 0.0, "currency": "KWD"},
}


# مفاتيح لها عمود قائم في جدول الشركات — (اسم العمود، اسم الحقل في القيمة)
_COMPANY_COLUMN_FALLBACK: dict[str, tuple[str, str]] = {
    "leave.annual_entitlement_days": ("annual_leave_days", "days"),
    "eos.day_divisor": ("eos_day_divisor", "divisor"),
}


def get(db: Session, company_id: int | None, key: str,
        on_date: date | None = None) -> dict:
    """يعيد {value, version, source} للمفتاح — قاعدة الشركة ثم العامة ثم الافتراضي."""
    if key not in DEFAULTS:
        raise KeyError(f"مفتاح سياسة غير معروف: {key}")
    on_date = on_date or kuwait_today()

    for scope, cid in (("company", company_id), ("global", None)):
        if scope == "company" and company_id is None:
            continue
        q = select(models.PolicyRule).where(
            models.PolicyRule.key == key,
            models.PolicyRule.company_id.is_(None) if cid is None
            else models.PolicyRule.company_id == cid,
            models.PolicyRule.is_active == True,  # noqa: E712
        ).order_by(models.PolicyRule.version.desc())
        for row in db.scalars(q).all():
            if row.effective_from and row.effective_from > on_date:
                continue
            if row.effective_to and row.effective_to < on_date:
                continue
            return {"value": row.value_json or {}, "version": row.version,
                    "source": scope, "key": key}

    # قبل الافتراضي: أعمدة الشركة القائمة. قيم نهاية الخدمة والإجازة مضبوطة
    # فيها منذ البداية وتعمل؛ استبدالها بجدول جديد يهدم ما يشتغل بلا مكسب.
    # المكسب هنا مسار قراءة واحد: من يريد إصداًرا مؤرًخا يُنشئ صف policy_rule
    # فيتقدّم، ومن لا يريد يبقى على عموده.
    company_column = _COMPANY_COLUMN_FALLBACK.get(key)
    if company_column and company_id is not None:
        company = db.get(models.Company, company_id)
        raw = getattr(company, company_column[0], None) if company else None
        if raw is not None:
            return {"value": {company_column[1]: raw}, "version": 0,
                    "source": "company_column", "key": key}

    return {"value": DEFAULTS[key], "version": 0, "source": "code_default", "key": key}


def value(db: Session, company_id: int | None, key: str, field: str, default=None):
    """قيمة حقل واحد داخل القاعدة — للاستدعاءات التي لا تحتاج البيانات الوصفية."""
    return get(db, company_id, key).get("value", {}).get(field, default)


def snapshot(db: Session, company_id: int | None, keys: list[str]) -> dict:
    """لقطة القواعد الفاعلة لحظة الإرسال — تُحفظ في الطلب ولا تُحدَّث بعدها.

    RW-18: تعديل سياسة بعد الإرسال لا يغيّر طلًبا قائًما. وبلا اللقطة يستحيل
    بعد شهور تفسير لماذا مرّ هذا الطلب بمرحلتين وذاك بثلاث.
    """
    out = {}
    for k in keys:
        if k in DEFAULTS:
            r = get(db, company_id, k)
            out[k] = {"value": r["value"], "version": r["version"], "source": r["source"]}
    return out
