# -*- coding: utf-8 -*-
"""M23 #4 — الفشلُ ليس فراغًا: قائمةٌ لا تظهر إلا إذا كان فيها شيء (فراغُها = «سليم») لا تبتلع خطأ تحميلها.

الحسابات اليتيمة، الإقامات المستحقة، فجوات الحضور، التعديلات المعلَّقة: كلُّها قوائمُ «لا شيء» فيها تطمين. فشلُ التحميل كان
يُعرض فراغًا — أي «كلُّه سليم» وهو غير معروف. الحارس يشتقّ هذه القوائم من الشيفرة (كل ``X.length > 0 &&`` لها ``.catch`` يصفّرها).
"""
import re
from pathlib import Path

PAGES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
B = chr(92)
#: ``.catch(() => setX([]))`` أو ``.catch(() => { setX([]); ... })`` — جسمُ الـcatch بأكمله
CATCH = re.compile("[.]catch[(][(][)]" + B + "s*=>" + B + "s*([{][^}]*[}]|set[A-Za-z]+[(][[][]][)])[)]")
SETTER = re.compile("(set[A-Za-z]+)[(][[][]][)]")


def test_a_swallowed_load_error_on_an_all_clear_list_is_recorded():
    checked, offenders = 0, []
    for p in sorted(PAGES.glob("*.tsx")):
        text = p.read_text(encoding="utf-8")
        for body in CATCH.findall(text):
            m = SETTER.search(body)
            if not m:
                continue
            setter = m.group(1)
            name = setter[3].lower() + setter[4:]
            if not re.search(re.escape(name) + r"[.]length > 0 &&", text):
                continue                                    # قائمةٌ رئيسيةٌ لها حالةُ فراغٍ صريحة، لا «قائمةُ سلامة»
            checked += 1
            if not re.search(r"set[A-Za-z]*Err[(]true[)]", body):
                offenders.append((p.name, setter))
    assert checked >= 4, f"الاستخراج معطوب ({checked})"
    assert not offenders, f"قوائمُ «سلامة» تبتلع الخطأ فراغًا: {offenders}"
