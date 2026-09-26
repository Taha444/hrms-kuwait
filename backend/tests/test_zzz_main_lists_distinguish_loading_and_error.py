# -*- coding: utf-8 -*-
"""M23 #4 / SW-032 — القائمةُ الرئيسية لا تقول «لا بيانات» أثناء التحميل ولا عند الفشل.

كانت شاشة الموظفين تعرض «لا بيانات» قبل أن يصل الرد، وعند فشله (لا ``catch``): فيُقرأ الانتظارُ أو العطلُ «لا موظفين».
الحارسُ يمسح الصفحات: كل ملفٍّ يعرض ``t("no_data")`` لقائمةٍ فارغة مع جلبٍ من الخادم يجب أن يحمل ما يفرّق **التحميلَ** و**الخطأ**
(``Skeleton``/``ErrorRetry``/حالة تحميل)، أو يكون في قائمة الاستثناءات المعلَّلة (الفراغ فيها وضعٌ عاديّ لا يُقرأ عطلًا).
"""
import re
from pathlib import Path

PAGES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"

#: صفحاتٌ لا يُقرأ فراغُها عطلًا (قائمةُ اختيارٍ فرعية داخل نموذج، أو بياناتٌ تأتي من الأب)
EXEMPT = {"EmployeeProfile.tsx", "EmployeeOnboarding.tsx"}

DISTINGUISHES = re.compile(r"Skeleton|ErrorRetry|ListState|setState\(\"(?:loading|error)\"\)|useState<\"loading\"")


def test_a_main_list_screen_tells_loading_from_empty_from_error():
    checked, offenders = 0, []
    for p in sorted(PAGES.glob("*.tsx")):
        if p.name in EXEMPT:
            continue
        text = p.read_text(encoding="utf-8")
        if not re.search(r"\!\w+\.length\s*&&[^\n]*t\(\"no_data\"\)", text):
            continue                       # لا تعرض «لا بيانات» لقائمةٍ فارغة
        if "api.get(" not in text:
            continue
        checked += 1
        if not DISTINGUISHES.search(text):
            offenders.append(p.name)
    assert checked >= 1, "الاستخراج معطوب"
    assert not offenders, f"شاشاتٌ تقول «لا بيانات» بلا تفريقٍ بين التحميل والخطأ: {offenders}"


def test_the_employees_list_has_the_three_states():
    src = (PAGES / "Employees.tsx").read_text(encoding="utf-8")
    assert 'listState === "loading"' in src and 'listState === "error"' in src and 'listState === "ok"' in src
    assert ".catch(() => setListState(\"error\"))" in src
