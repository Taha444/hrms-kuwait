# -*- coding: utf-8 -*-
"""اختبارات محرّك مكافأة نهاية الخدمة — تطابق الأمثلة في التكليف (القسم 6)."""
from app.eos import calculate_eos


def approx(a, b, tol=60.0):
    return abs(a - b) <= tol


def test_termination_7_5_years_daily_40():
    # فصل بعد ~7.5 سنة، أجر يومي 40 (راتب=1040) → ≈ 6000 د.ك
    r = calculate_eos(basic_salary=40 * 26, hire_date="2010-01-01", end_date="2017-07-01",
                      reason="termination", day_divisor=26)
    assert approx(r["indemnity"], 6000, 60), r["indemnity"]


def test_resignation_4_years_half():
    r = calculate_eos(basic_salary=500, hire_date="2018-01-01", end_date="2022-01-01",
                      reason="resignation", contract_type="indefinite", day_divisor=26)
    assert r["entitlement_factor"] == 0.5


def test_cap_18_months():
    r = calculate_eos(basic_salary=1000, hire_date="1990-01-01", end_date="2020-01-01",
                      reason="termination")
    assert r["cap_applied"] is True
    assert approx(r["indemnity"], 18000, 1), r["indemnity"]


def test_misconduct_zero():
    r = calculate_eos(basic_salary=600, hire_date="2015-01-01", end_date="2020-01-01",
                      reason="misconduct")
    assert r["indemnity"] == 0.0


def test_resignation_under_3_years_zero():
    r = calculate_eos(basic_salary=600, hire_date="2020-01-01", end_date="2022-06-01",
                      reason="resignation", contract_type="indefinite")
    assert r["entitlement_factor"] == 0.0


def test_leave_accrued_auto_and_payout():
    # 5 سنوات خدمة × 30 يومًا سنويًا ⇒ مستحق ≈ 150 يومًا (يُحسب آليًا)
    r = calculate_eos(basic_salary=520, hire_date="2015-01-01", end_date="2020-01-01",
                      reason="termination", used_leave_days=140, annual_leave_days=30,
                      day_divisor=26)
    assert approx(r["leave"]["accrued_days"], 150, 0.5)
    assert approx(r["leave"]["remaining_days"], 10, 0.5)   # 150 مستحق − 140 مستهلَك
    # أجر اليوم = 20، المتبقّي ≈ 10 ⇒ بدل الإجازة ≈ 200
    assert approx(r["leave_payout"], 200, 1.0)


def test_over_consumed_leave_floors_payout():
    # استهلاك أكثر من المستحق ⇒ لا بدل سالب (يُصفّر)، مع عرض المتبقّي الحقيقي
    r = calculate_eos(basic_salary=520, hire_date="2018-01-01", end_date="2020-01-01",
                      reason="termination", used_leave_days=200, annual_leave_days=30,
                      day_divisor=26)
    assert r["leave_payout"] == 0.0
    assert r["leave"]["remaining_days"] < 0
