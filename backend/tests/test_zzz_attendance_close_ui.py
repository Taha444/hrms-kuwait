# -*- coding: utf-8 -*-
"""ATT-07 / DLV-01 — للبوابة مخرج: شاشة تُغلق فترة الحضور.

**العطل**: المنع كان مبنًيا ومقاًسا من طرف إلى طرف على الخادم
(``test_att07_payroll_requires_closed_attendance``)، ورسالته تقول
«أغلقها من مراجعة الحضور أوًلا» — **ولا شيء في مراجعة الحضور يُغلق**.
فالمسيّر يقف والمستخدم أمام جدار: منعٌ صحيح بلا طريق إلى الأمام، وهو
ما تحظره قاعدة المشروع نفسها (P4-20): «ممنوع انتقال يُدخل المعاملة
حالًة لا مخرج منها».

وهو نمط تكرّر في هذه الجولة: عمود بلا قارئ، وقالب بلا مسار، وشاشة بلا
رابط. وهنا: **بوابة بلا مخرج**.

والحارس على الواجهة لأن الخادم مقاس أصًلا: ما كان ناقًصا هو الطريق
إليه.
"""
from __future__ import annotations

from pathlib import Path

FRONT = Path(__file__).resolve().parents[2] / "frontend"
REVIEW = FRONT / "src" / "pages" / "AttendanceReview.tsx"
APP = FRONT / "src" / "App.tsx"
I18N = FRONT / "src" / "i18n.tsx"


def test_the_review_screen_can_close_the_period():
    """**جوهر الإصلاح**: المخرج في الشاشة التي تحيل إليها رسالة المنع."""
    src = REVIEW.read_text(encoding="utf-8")
    assert "/attendance/close-month" in src, "لا إغلاق من شاشة المراجعة"
    assert "/attendance/close-status" in src, "الحالة لا تُقرأ — الشاشة لا تعرف"


def test_reopening_asks_for_the_reason_the_server_requires():
    """والسبب إلزامي على الخادم — فيُطلَب في الشاشة لا يُردّ الطلب بخطأ.

    شاشة ترسل ما تعرف أنه سيُرفض تُعلّم المستخدم أن الأزرار تكذب.
    """
    src = REVIEW.read_text(encoding="utf-8")
    assert "/attendance/reopen-month" in src, "لا إعادة فتح — الإغلاق بلا رجعة"
    assert "att_reopen_reason" in src, "إعادة الفتح لا تطلب سبًبا"


def test_the_close_states_the_number_it_attests_to():
    """**الإقفال إقرار على رقم لا زرّ شكلي**.

    يوثّق من أقرّ ومتى و**على كم يوم بلا سجل** — فبعد شهور، حين يُسأل
    عن راتب، يوجد جواب مكتوب لا ذاكرة. وعرض الرقم في التأكيد نفسه هو
    ما يجعل الإقرار إقراًرا.
    """
    src = REVIEW.read_text(encoding="utf-8")
    assert "unrecorded_days" in src, "عدد الأيام بلا سجل غير معروض"
    assert "att_close_confirm" in src, "الإقفال بلا تأكيد يذكر ما يُقَرّ عليه"


def test_the_control_is_gated_by_the_permission_the_server_checks():
    """ولا زرّ يظهر لمن سيُرفض طلبه: نفس الصلاحية التي يفحصها الخادم."""
    src = REVIEW.read_text(encoding="utf-8")
    assert 'can("manage_attendance")' in src, (
        "الإغلاق غير محكوم بالصلاحية — يظهر لمن لا يملكه"
    )


def test_whoever_may_close_can_reach_the_screen():
    """**وزرّ خلف باب مغلق لا وجود له**.

    الشاشة محكومة بـ``view_attendance``، والإغلاق بـ``manage_attendance``.
    فلو ملك دوٌر الثانية دون الأولى لَمَا رأى الزرّ أصًلا.
    """
    from app.permissions import ROLE_DEFAULT_PERMS

    blind = [r for r, p in ROLE_DEFAULT_PERMS.items()
             if "manage_attendance" in p and "view_attendance" not in p]
    assert not blind, f"يملك الإغلاق ولا يصل إلى شاشته: {blind}"


def test_the_screen_has_a_way_in():
    """والشاشة مرتبطة في الشريط — لا تُبلَغ بكتابة المسار يًدا."""
    app = APP.read_text(encoding="utf-8")
    assert 'to="/attendance-review"' in app, "مراجعة الحضور بلا رابط"
    assert 'path="/attendance-review"' in app, "لا مسار للشاشة"


def test_every_new_label_exists_in_both_languages():
    """ونصٌّ ناقص في لغة يظهر مفتاًحا خاًما على الشاشة."""
    import re

    src = REVIEW.read_text(encoding="utf-8")
    i18n = I18N.read_text(encoding="utf-8")
    keys = set(re.findall(r't\("(att_[a-z_]+)"\)', src))
    assert keys, "لا مفاتيح نصّية — تحقّق من الشاشة"
    for k in sorted(keys):
        at = i18n.find(f"{k}: {{")
        assert at >= 0, f"المفتاح «{k}» غير معرَّف"
        # حتى بداية المفتاح التالي: النصّ نفسه قد يحوي ``{m}`` و``{n}``،
        # فمطابقة القوس المغلق الأول تقطع المدخل في منتصفه — أول كتابة
        # لهذا الحارس وقعت فيها واتّهمت ترجمًة سليمة.
        nxt = re.search(r"\n  [a-z_]+: ", i18n[at + len(k):])
        entry = i18n[at:at + len(k) + (nxt.start() if nxt else 400)]
        assert "ar:" in entry and "en:" in entry, (
            f"المفتاح «{k}» ناقص في إحدى اللغتين"
        )
