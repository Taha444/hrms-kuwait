# -*- coding: utf-8 -*-
"""
محرك حساب مكافأة نهاية الخدمة (End of Service / Indemnity)
وفقًا لقانون العمل الكويتي في القطاع الخاص رقم 6 لسنة 2010 (المواد 51 - 53).

ملخص القواعد المطبّقة:
- اليوم الواحد = الراتب الشهري ÷ 26 (المعتمد في أغلب حاسبات الهيئة العامة للقوى العاملة).
  (المُعامل قابل للتغيير لكل شركة: 26 أو 30 حسب سياستها / عقودها).
- أول 5 سنوات: 15 يومًا عن كل سنة.
- ما بعد 5 سنوات: 30 يومًا (شهر) عن كل سنة.
- الكسور (الأشهر والأيام) تُحسب بالتناسب.
- الحد الأقصى للمكافأة = راتب 18 شهرًا (سنة ونصف).
- نسبة الاستحقاق حسب سبب انتهاء الخدمة (للعقد غير محدد المدة):
    * فصل من صاحب العمل (لغير الأسباب التأديبية بالمادة 41) / انتهاء العقد دون تجديد
      / الوفاة / العجز / استقالة المرأة للزواج خلال سنة  →  استحقاق كامل (100%).
    * استقالة العامل (عقد غير محدد المدة):
        - أقل من 3 سنوات        →  لا يستحق (0%)
        - من 3 إلى أقل من 5     →  نصف المكافأة (50%)
        - من 5 إلى أقل من 10    →  ثلثا المكافأة (66.67%)
        - 10 سنوات فأكثر        →  المكافأة كاملة (100%)
    * فصل تأديبي (المادة 41)   →  لا يستحق (0%).
- يُضاف رصيد الإجازات غير المستخدمة = أجر اليوم × عدد أيام الإجازة المتبقية.

ملاحظة قانونية: هذه نتيجة تقديرية لأغراض النظام وليست استشارة قانونية. تُحسب المكافأة
على الراتب الأساسي ما لم ينص العقد على غير ذلك. يُرجى التحقق من الهيئة العامة للقوى
العاملة (PAM) عند وجود حالات خاصة.
"""

from datetime import date

# أسباب انتهاء الخدمة المدعومة
TERMINATION_REASONS = {
    "termination": "فصل من صاحب العمل (غير تأديبي)",
    "contract_expiry": "انتهاء العقد دون تجديد",
    "death": "الوفاة",
    "disability": "العجز عن العمل",
    "marriage": "استقالة المرأة للزواج (خلال سنة)",
    "resignation": "استقالة العامل",
    "misconduct": "فصل تأديبي (المادة 41)",
}

# الأسباب التي تمنح الاستحقاق الكامل مباشرةً (عقد غير محدد المدة)
FULL_ENTITLEMENT_REASONS = {"termination", "contract_expiry", "death", "disability", "marriage"}


def _parse_date(value):
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def service_breakdown(hire_date, end_date):
    """يرجع (سنوات، أشهر، أيام، إجمالي الأيام، سنوات عشرية)."""
    hire_date = _parse_date(hire_date)
    end_date = _parse_date(end_date)
    if end_date < hire_date:
        raise ValueError("تاريخ انتهاء الخدمة أقدم من تاريخ التعيين")

    total_days = (end_date - hire_date).days

    # حساب السنوات/الأشهر/الأيام بشكل تقويمي للعرض
    years = end_date.year - hire_date.year
    months = end_date.month - hire_date.month
    days = end_date.day - hire_date.day
    if days < 0:
        months -= 1
        # عدد أيام الشهر السابق لتاريخ الانتهاء
        prev_month = end_date.month - 1 or 12
        prev_year = end_date.year if end_date.month != 1 else end_date.year - 1
        days += _days_in_month(prev_year, prev_month)
    if months < 0:
        years -= 1
        months += 12

    decimal_years = total_days / 365.25  # متوسط طول السنة شاملًا الكبائس
    return years, months, days, total_days, decimal_years


def _days_in_month(year, month):
    if month == 12:
        nxt = date(year + 1, 1, 1)
    else:
        nxt = date(year, month + 1, 1)
    return (nxt - date(year, month, 1)).days


def resignation_factor(decimal_years):
    """نسبة الاستحقاق عند الاستقالة (عقد غير محدد المدة)."""
    if decimal_years < 3:
        return 0.0
    if decimal_years < 5:
        return 0.5
    if decimal_years < 10:
        return 2.0 / 3.0
    return 1.0


def calculate_eos(
    basic_salary,
    hire_date,
    end_date,
    reason="termination",
    contract_type="indefinite",
    unused_leave_days=0,
    day_divisor=26,
    max_months=18,
):
    """
    يحسب مكافأة نهاية الخدمة ويُرجع قاموسًا تفصيليًا.

    basic_salary : الراتب الأساسي الشهري (دينار كويتي)
    hire_date    : تاريخ التعيين  (YYYY-MM-DD)
    end_date     : تاريخ انتهاء الخدمة (YYYY-MM-DD)
    reason       : أحد مفاتيح TERMINATION_REASONS
    contract_type: 'indefinite' (غير محدد) أو 'definite' (محدد المدة)
    unused_leave_days: رصيد الإجازات غير المستخدمة
    day_divisor  : مقسوم اليوم (26 افتراضيًا، أو 30)
    max_months   : الحد الأقصى بالأشهر (18 افتراضيًا)
    """
    basic_salary = float(basic_salary or 0)
    unused_leave_days = float(unused_leave_days or 0)
    day_divisor = int(day_divisor or 26)
    max_months = float(max_months or 18)

    years, months, days, total_days, decimal_years = service_breakdown(hire_date, end_date)

    daily_wage = basic_salary / day_divisor if day_divisor else 0.0

    # المكافأة الكاملة (قبل تطبيق نسبة السبب) بالأيام
    first_period_years = min(decimal_years, 5.0)
    after_period_years = max(decimal_years - 5.0, 0.0)

    first_period_amount = daily_wage * 15 * first_period_years
    after_period_amount = daily_wage * 30 * after_period_years
    full_indemnity = first_period_amount + after_period_amount

    # تطبيق الحد الأقصى (18 شهرًا) على المكافأة الكاملة
    cap_amount = basic_salary * max_months
    capped = False
    if full_indemnity > cap_amount:
        full_indemnity = cap_amount
        capped = True

    # نسبة الاستحقاق حسب السبب ونوع العقد
    if reason == "misconduct":
        factor = 0.0
        factor_note = "فصل تأديبي (المادة 41): لا تُستحق المكافأة."
    elif reason in FULL_ENTITLEMENT_REASONS:
        factor = 1.0
        factor_note = "استحقاق كامل (%100)."
    elif reason == "resignation":
        if contract_type == "definite":
            factor = 1.0
            factor_note = "عقد محدد المدة مكتمل: استحقاق كامل (%100). راجع المادة 52 للإنهاء المبكر."
        else:
            factor = resignation_factor(decimal_years)
            pct = round(factor * 100)
            factor_note = f"استقالة (عقد غير محدد المدة): الاستحقاق %{pct} حسب مدة الخدمة."
    else:
        factor = 1.0
        factor_note = "استحقاق كامل (%100)."

    indemnity = full_indemnity * factor

    # رصيد الإجازات غير المستخدمة
    leave_payout = daily_wage * unused_leave_days

    total_settlement = indemnity + leave_payout

    return {
        "inputs": {
            "basic_salary": round(basic_salary, 3),
            "hire_date": str(_parse_date(hire_date)),
            "end_date": str(_parse_date(end_date)),
            "reason": reason,
            "reason_label": TERMINATION_REASONS.get(reason, reason),
            "contract_type": contract_type,
            "unused_leave_days": unused_leave_days,
            "day_divisor": day_divisor,
            "max_months": max_months,
        },
        "service": {
            "years": years,
            "months": months,
            "days": days,
            "total_days": total_days,
            "decimal_years": round(decimal_years, 4),
            "text": f"{years} سنة و {months} شهر و {days} يوم",
        },
        "daily_wage": round(daily_wage, 3),
        "first_period_amount": round(first_period_amount, 3),
        "after_period_amount": round(after_period_amount, 3),
        "full_indemnity": round(full_indemnity, 3),
        "cap_amount": round(cap_amount, 3),
        "cap_applied": capped,
        "entitlement_factor": round(factor, 4),
        "factor_note": factor_note,
        "indemnity": round(indemnity, 3),
        "leave_payout": round(leave_payout, 3),
        "total_settlement": round(total_settlement, 3),
        "currency": "KWD",
        "disclaimer": (
            "نتيجة تقديرية وفق قانون العمل الكويتي 6/2010 (القطاع الخاص). ليست استشارة "
            "قانونية. تُحسب على الراتب الأساسي ما لم ينص العقد على غير ذلك. للحالات الخاصة "
            "يُرجى مراجعة الهيئة العامة للقوى العاملة."
        ),
    }


def notice_pay(basic_salary, day_divisor=26, notice_days=90):
    """بدل الإشعار/الإنذار التقريبي (المادة 44): راتب فترة الإشعار.

    افتراضيًا 3 أشهر (≈90 يومًا) للعقد غير محدد المدة عند عدم الالتزام بالإشعار.
    """
    basic_salary = float(basic_salary or 0)
    daily = basic_salary / (int(day_divisor) or 26)
    return round(daily * float(notice_days or 0), 3)


# ----------------------------------------------------------------------------
# اختبارات ذاتية للتحقق من صحة الحسابات مقابل أمثلة منشورة
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    def approx(a, b, tol=1.0):
        return abs(a - b) <= tol

    # مثال 1: فصل (غير تأديبي) بعد 7 سنوات و6 أشهر، أجر يومي 40 د.ك → 6000 د.ك
    # daily=40 يعني راتب شهري = 40*26 = 1040
    r1 = calculate_eos(
        basic_salary=40 * 26,
        hire_date="2010-01-01",
        end_date="2017-07-01",  # 7.5 سنة تقريبًا
        reason="termination",
        day_divisor=26,
    )
    print("مثال 1 (متوقع ~6000):", r1["indemnity"], "| الخدمة:", r1["service"]["text"])

    # مثال 2: استقالة بعد 4 سنوات (عقد غير محدد) → نصف المكافأة
    r2 = calculate_eos(
        basic_salary=500,
        hire_date="2018-01-01",
        end_date="2022-01-01",
        reason="resignation",
        contract_type="indefinite",
        day_divisor=26,
    )
    print("مثال 2 (استقالة 4 سنوات، نصف):", r2["indemnity"], "| نسبة:", r2["entitlement_factor"])

    # مثال 3: تجاوز السقف (راتب 1000، خدمة 30 سنة) → 18000 كحد أقصى
    r3 = calculate_eos(
        basic_salary=1000,
        hire_date="1990-01-01",
        end_date="2020-01-01",
        reason="termination",
    )
    print("مثال 3 (سقف 18 شهر = 18000):", r3["indemnity"], "| طُبّق السقف:", r3["cap_applied"])

    # مثال 4: فصل تأديبي → صفر
    r4 = calculate_eos(basic_salary=600, hire_date="2015-01-01", end_date="2020-01-01", reason="misconduct")
    print("مثال 4 (فصل تأديبي = 0):", r4["indemnity"])

    assert approx(r1["indemnity"], 6000, 60), r1["indemnity"]
    assert r2["entitlement_factor"] == 0.5
    assert approx(r3["indemnity"], 18000, 1), r3["indemnity"]
    assert r4["indemnity"] == 0.0
    print("\n✓ كل اختبارات محرك نهاية الخدمة نجحت")
