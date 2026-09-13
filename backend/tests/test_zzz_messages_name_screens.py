# -*- coding: utf-8 -*-
"""رسالٌة تأمر بما لا تفعله الشاشة — والنصُّ الداخلي لا يتسرَّب.

**الصنف**: ردُّ الخادم يقول «افعل كذا عبر ``/x/y``» — ومساُر الـAPI ليس
باًبا يفتحه مستخدم. فمن يقرؤه يقف: إما يظنُّ الخلَل في نفسه، وإما يبحث عن
شاشٍة بهذا الاسم ولا يجدها. **وأمٌر بلا باٍب أسوأ من منٍع بلا سبب**: المنُع
يُفهَم، والأمُر المستحيُل يُقرأ عيًبا في القارئ.

وقد أُصلح مرًة في ``payroll.py`` («كانت الرسالة تسمّي مساًرا خاًما لا شاشة
له… صارت تسمّي الشاشة التي تفعله فعًلا») ولم تُطبَّق القاعدُة على البقية.
والقياُس وجد ثلاًثا:

- ``attendance`` «أعد فتحه عبر ``/attendance/reopen-month``» — **والشاشُة
  تفعله فعًلا** (زرُّ إعادة الفتح في «مراجعة الحضور»)، فسُمّيت.
- ``archive`` «استخدم ``/documents/upload``» — وله ثالُث شاشات، فسُمّيت.
- ``users`` «فعّل ``is_cross_company`` عبر ``/enable-cross-company``» —
  **ولا شاشَة له أصًلا**: لا موضَع في ``frontend/src`` يناديه. فقيلت
  الحقيقة: من يفعله، وأنه إجراٌء إداريٌّ بلا شاشة. وأما بناُء الشاشة فمنُح
  وصوٍل عابٍر للشركات — قراُر مالك لا استنباُط شيفرة.

**والحارُس يقيس النصَّ بحقّ**: المقيُس **غياُب** مساٍر خام في رسالٍة
تُعرَض — ولا أثَر له في قاعدة بيانات يُقاس.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
BE = ROOT / "backend" / "app"
APP_TSX = ROOT / "frontend" / "src" / "App.tsx"

#: حقوٌل يراها المستخدم في الردّ أو في مهمٍة أو إشعار.
_USER_FACING = re.compile(r'(detail|title|message|warning|hint|notice_ar|notice_en)\s*=')

#: مساراٌت يجوز ذكرُها بنصّها — **لكلٍّ سبٌب مكتوب**.
_ALLOWED: dict[str, str] = {}


def _frontend_routes() -> set[str]:
    if not APP_TSX.exists():
        return set()
    src = APP_TSX.read_text(encoding="utf-8", errors="ignore")
    out = set()
    for pat in (r'path="(/[^"]*)"', r'to="(/[^"]*)"'):
        for m in re.finditer(pat, src):
            out.add(m.group(1).rstrip("/") or "/")
    return out


def _paths_in_messages() -> list[tuple[str, str]]:
    hits: list[tuple[str, str]] = []
    for p in sorted(BE.rglob("*.py")):
        for i, ln in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if re.match(r"\s*#", ln) or not _USER_FACING.search(ln):
                continue
            for m in re.finditer(r'[«"\'\s](/[a-z][a-z0-9\-/_{}]{2,})', ln):
                hits.append((f"{p.relative_to(BE.parent)}:{i}",
                             m.group(1).rstrip('."»\'')))
    return hits


def test_no_user_facing_message_names_a_raw_api_path():
    """**الحارس الدائم**: الرسالُة تسمّي شاشًة أو فاعًلا، لا مساَر API.

    ومن أراد ذكَر مساٍر سمّاه في ``_ALLOWED`` بسببه — فقراٌر مكتوٌب
    يُراجَع، ونٌصّ داخليٌّ متسرٌِّب لا.
    """
    routes = _frontend_routes()
    stray = []
    for where, path in _paths_in_messages():
        if path in _ALLOWED:
            continue
        base = "/" + path.strip("/").split("/")[0]
        # مساٌر مطابٌق لمسار شاشٍة يُحتمَل أن يكون إحالًة صحيحة — لكنّ
        # المستخدَم ال يقرأ مساًرا على أي حال، فيُنذَر عليه أيًضا.
        stray.append((where, path, base in {r[:len(base)] for r in routes}))
    assert not stray, ("رسائٌل تُعرَض للمستخدم وتسمّي مساَر API:\n" + "\n".join(
        f"  {w}  →  {p}" + ("  (له شاشٌة بمسارٍ مشابه — سمِّ الشاشَة)" if ok else
                            "  (بال شاشة)")
        for w, p, ok in stray))


def test_the_measurement_is_not_blind():
    """**وقياٌس ال يرى شيًئا يمرُّ أخضَر دائًما.**

    لو تغيَّر شكُل الرسائل (مثًال إلى ثوابٍت في وحدٍة أخرى) لصار الاستخراُج
    فارًغا والحارُس ال يحرس شيًئا. فيُشترَط أن يرى رسائَل تُعرَض أصًلا.
    """
    count = sum(1 for p in BE.rglob("*.py")
                for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines()
                if _USER_FACING.search(ln) and not re.match(r"\s*#", ln))
    assert count >= 200, f"القياُس يرى {count} رسالًة فقط — تغيَّر شكلُها فصار أعمى"


def test_the_screen_that_reopens_a_month_exists():
    """**والرسالُة التي تسمّي شاشًة تسمّي شاشًة قائمة.**

    وإال صار العالُج عطًلا آخَر: إحالٌة إلى ما ال وجود له.
    """
    page = ROOT / "frontend" / "src" / "pages" / "AttendanceReview.tsx"
    if not page.exists():
        import pytest
        pytest.skip("ال واجهَة في هذا المسار")
    src = page.read_text(encoding="utf-8", errors="ignore")
    assert "/attendance/reopen-month" in src, "الشاشُة ال تُعيد فتَح الشهر"


def test_the_cross_company_toggle_still_has_no_screen():
    """**وما قيل عنه «بال شاشة» يُحرَس أنه كذلك.**

    فإن بُنيت الشاشُة سقط هذا الحارس — فتُصحَّح الرسالُة لتسمّيها، وال يبقى
    نٌصّ يقول «بال شاشة» وللشاشة وجود.
    """
    fe = ROOT / "frontend" / "src"
    if not fe.exists():
        import pytest
        pytest.skip("ال واجهَة في هذا المسار")
    callers = [str(p.relative_to(fe)) for p in fe.rglob("*.ts*")
               if "enable-cross-company" in p.read_text(encoding="utf-8", errors="ignore")]
    assert not callers, ("صارت للتهيئة شاشٌة — فتُسمَّ في الرسالة بدل "
                         f"«بلا شاشة»: {callers}")
