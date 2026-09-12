# -*- coding: utf-8 -*-
"""حقٌل إلزامٌي ال يقرؤه شيء — والسؤاُل يتغيّر بالقياس.

**القراُر المعلَّق كما وُضع**: «مهلُة الردّ على الإنذار — كم يوًما
افتراًضا؟». والقياُس يُحوِّله إلى سؤاٍل أدقّ.

**ما قيس:**

- ``ADMWARN`` (إصدار إنذار) يجمع ``response_deadline`` = «آخر موعد لردّ
  الموظف»، **وهو حقٌل إلزامي** (``required=True``).
- **وال يقرؤه شيٌء في النظام كلّه**: ال تذكير، ال تصعيد، ال انقضاء. الموضُع
  الوحيُد الذي يذكره هو ``form_schemas.py`` الذي يعلنه.
- والموظُف يُخطَر بالإنذار (``NTF-071`` عبر ``_DISCIPLINARY_NOTICE``)،
  و``REQWARN`` (الردّ) ``visible_to_employee=True`` — **فالردُّ في
  متناوله**. أي أن الطرَف القادر على الردّ موجوٌد ويعلم، والمهلُة وحدها
  صامتة.

**فالسؤاُل لم يبقَ «كم يوًما»**: موظُف الشؤون **يُلزَم** بإدخال تاريخ لا
يفعل شيًئا. وهو اجتماُع نمطين مّما تُكنَس هذه الجولُة لأجلهما: **حقٌل
يُدخَله المستخدم وال يقرؤه أحد**، و**بوّابٌة بال مخرج** (مهلٌة ال تنقضي).

**ولم يوصَل بقصد**: الإنذاُر مساٌر تأديبٌّي قانونّي، ومهلُة الردّ حٌق
إجرائي. ووصُل تذكيٍر أو انقضاٍء يُنشئ سلوًكا قانونًيا لم يُعتمَد — والقاعدُة
المتّفَقة تمنع تغييَر ما ذُكر كقرار بال إذن صاحبه. فيُقاس ويُقال، وال
يُبَتّ.

**والخياراُت الثالثة، مقيسًة ال مقترحًة:**

1. **يُوصَل**: المهلُة تُنتج تذكيًرا للموظف قبل انقضائها، وإخطاًرا للشؤون
   عند انقضائها بال ردّ. (سلوٌك جديد — يحتاج إذًنا.)
2. **يُرفَع اإللزام**: يبقى حقًال اختيارًيا يُطبَع على الورقة وال يعِد بشيء.
3. **يبقى كما هو**: إلزاٌم ورقّي — ويُعرَف أنه ورقّي فال يُنتظَر منه تذكير.

وهذا الحارس يُثبِّت **الحالَة المقيسة** ال الخيار: فإن وُصِل غًدا سقط
معلًنا أن هذه الوثيقَة تُحدَّث.
"""
from __future__ import annotations

import pathlib
import re


def test_the_deadline_is_required_on_issuing_a_warning():
    """**افتراُض القياس األول**: الحقُل إلزامي."""
    from app import form_schemas

    sch = form_schemas.get_schema("ADMWARN")
    assert sch is not None, "ذهب نوُع إصدار الإنذار"
    field = next((f for f in sch["fields"]
                  if f["code"] == "response_deadline"), None)
    assert field is not None, "ذهب حقُل مهلة الردّ"
    assert field.get("required") is True, field


def test_nothing_reads_the_deadline_yet():
    """**وجوهُر القياس**: ال يقرؤه شيٌء خارج موضع إعالنه.

    فلو صار يُقرأ — تذكيًرا أو انقضاًء — سقط هذا الحارُس معلًنا أن القراَر
    حُسم وأن شرَح هذا الملف يُحدَّث. **وحاٌرس يُثبِّت حالًة مقيسة ال خياًرا
    مفروًضا.**
    """
    app = pathlib.Path(__file__).resolve().parents[1] / "app"
    readers = []
    for p in app.rglob("*.py"):
        if p.name == "form_schemas.py":
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if s.startswith("#"):
                continue
            if "response_deadline" in s:
                readers.append(f"{p.name}:{i}")
    assert not readers, (
        "صار يُقرأ — يُحدَّث شرُح هذا الملف ويُرفَع البنُد من القرارات "
        f"المعلَّقة: {readers}")


def test_the_employee_can_actually_reply():
    """**والطرُف القادر على الردّ موجوٌد ويعلم** — فالنقُص في المهلة ال فيه.

    فلو كان الردُّ محجوًبا عن الموظف لكان العطُل أوسَع من مهلٍة صامتة.
    """
    from app import workflow

    types = {rt["code"]: rt for rt in workflow.DEFAULT_REQUEST_TYPES}
    assert types["REQWARN"].get("visible_to_employee") is True, \
        "الردُّ محجوٌب عن الموظف — العطُل أوسع"
    assert "ADMWARN" in workflow._DISCIPLINARY_NOTICE, \
        "الموظُف ال يُخطَر بالإنذار أصًلا"


def test_the_open_decision_is_recorded_where_the_field_lives():
    """**وقراٌر معلٌَّق في محضٍر وحده يُنسى** — فيُكتَب عند الحقل.

    فمن يقرأ ``form_schemas`` يرى أن الحقَل إلزاٌم ورقّي حتى يُبَتّ، ولا
    يبني عليه تذكيًرا يظنّه قائًما.
    """
    src = (pathlib.Path(__file__).resolve().parents[1]
           / "app" / "form_schemas.py").read_text(encoding="utf-8")
    i = src.index("response_deadline")
    around = src[max(0, i - 1200):i + 400]
    assert re.search(r"ال يقرؤه|لا يقرؤه|قراٌر معلَّق|قرار معلَّق", around), \
        "الحقُل بال ملاحظٍة تقول إنه ال يُقرأ بعد"
