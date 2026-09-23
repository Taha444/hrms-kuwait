# -*- coding: utf-8 -*-
"""التحقق الثنائي الإلزامي **يُفرَض** لا يُعلَن فقط (SW-001، 2026-09-23).

قيس على الإنتاج: دخل صاحبُ الشركات بكلمة السر وحدها والردُّ يحمل ``must_enroll_2fa`` —
والواجهة لا تقرأه، فمضى إلى النظام بلا تفعيل. الخادم يحسب ``twofa_required`` في
``/auth/me`` ولا يمنع الدخول (وإلا تعذّر التفعيل نفسه)، فالحارس في الواجهة.
"""
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"


def test_protected_routes_send_an_unenrolled_required_role_to_setup():
    app = (SRC / "App.tsx").read_text(encoding="utf-8")
    guard = app.split("function Protected(", 1)[1].split("\n}\n", 1)[0]
    assert "twofa_required" in guard and "twofa_enabled" in guard, "الحارس لا يقرأ حالة 2FA"
    assert '<Navigate to="/two-factor"' in guard
    # وصفحةُ التفعيل وتغييرُ كلمة السر يبقيان مفتوحتين، وإلا تعذّر التفعيل نفسه.
    assert '"/two-factor"' in guard and '"/change-password"' in guard
    # وجلسةُ الانتحال لا تُحصَر — التفعيل شأنُ صاحب الحساب.
    assert "impersonatingName" in guard


def test_the_setup_page_refreshes_the_session_after_enabling_and_says_it_is_required():
    page = (SRC / "pages" / "TwoFactor.tsx").read_text(encoding="utf-8")
    assert page.count("await refreshUser()") >= 2, "بعد التفعيل/التعطيل يبقى الحارس على حالٍ قديمة"
    assert "twofa_required" in page and "إلزامي" in page, "الصفحة تقول «يوصى» لدورٍ إلزامي"
