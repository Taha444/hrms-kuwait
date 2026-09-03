# -*- coding: utf-8 -*-
"""V-A — هل ما زال المسار يُنسب مستنده إلى القالب الصحيح؟

**التحقيق**: سجلّ المراجعة يثبت اختلاًفا تاريخًيا بين المسار والمستند
الرسمي. والسؤال: هل البناء **الحالي** ما زال يُخطئ؟

**الجواب: نعم — أربعة عشر من ثمانية عشر.** أمثلة من القياس:

    طلب إجازة        →  HRMS-PR-015  «قرار إنهاء خدمة»
    طلب استقالة      →  HRMS-PR-025  «قرار إيقاف مؤقت لحين التحقيق»
    نهاية خدمة       →  HRMS-PR-028  «إشعار عودة من إجازة»
    إخلاء طرف        →  HRMS-PR-026  «تكليف واعتماد عمل إضافي»

**وحدّ الأثر بدقّة**: الورقة المطبوعة **صحيحة** — ``render_request_pdf``
يبني المستند من اسم نوع الطلب لا من نصّ القالب. لكن
``default_template_code`` يُختَم على صفّ المستند (``doc.template_code``
و``template_version``) بوصفه هويّته الرسمية، ويظهر في التحقّق العلني
``/api/verify/{code}``. فكل مستند يُحفَظ منسوًبا إلى قالب ليس قالبه —
ومن يفتّش بعد سنة يقرأ أن إجازة صدرت تحت «قرار إنهاء خدمة».

وهو أيًضا ما يمنع حذف قالب مربوط (``templates.py:242``): الروابط الخاطئة
تحمي الخطأ وتترك الصواب بلا حماية.

**ولماذا جدول مراجَع لا مطابقة أسماء**: جرّبت التشابه النصّي فاقترح
«خطاب تحويل راتب للبنك» لطلب **نقل** داخلي — طابقت «نقل» بـ«تحويل».
أداة ترشّح ولا تحكم. فالجدول أدناه **قرار مكتوب**، وما لم يُحسم يبقى
مرئًيا في :data:`UNDECIDED` لا مطموًسا.
"""
from __future__ import annotations

import re
from pathlib import Path

from app import v15_registry as R
from app import workflow

SEED = Path(__file__).resolve().parents[1] / "app" / "seed.py"


def _template_names() -> dict[str, str]:
    """كود القالب ← اسمه، من البذرة مباشرًة."""
    text = SEED.read_text(encoding="utf-8")
    return dict(re.findall(r'\("(HRMS-PR-\d+)", "([^"]+)"', text))


def _types_producing_documents():
    out = []
    for rt in workflow.DEFAULT_REQUEST_TYPES:
        chain = rt.get("approval_chain_json") or []
        if rt.get("produces_document") or any(
                s.get("produces_document") for s in chain):
            out.append(rt)
    return out


#: **الخريطة المراجَعة.** كل سطر قرار، لا استنتاج أداة.
REVIEWED = {
    # صُحّحت في هذه الجولة — اسم القالب يطابق نوع الطلب صراحًة
    "leave": "HRMS-PR-027",        # قرار اعتماد إجازة   (كان: قرار إنهاء خدمة)
    "REQRESIGN": "HRMS-PR-014",    # قبول استقالة        (كان: إيقاف لحين التحقيق)
    "REQEOS": "HRMS-PR-038",       # التسوية النهائية    (كان: إشعار عودة من إجازة)
    "ADMWARN": "HRMS-PR-022",      # إنذار موظف          (كان: خطاب لجهة رسمية)
    "REQCLR": "HRMS-PR-040",       # محضر تسليم عهدة     (كان: تكليف عمل إضافي)
    "REQTRF": "HRMS-PR-016",       # قرار نقل موظف       (كان: شهادة مدة خدمة)
    "REQTRFLIC": "HRMS-PR-016",    # قرار نقل موظف       (كان: شهادة مدة خدمة)
    # كانت صحيحة قبل الجولة
    "salary_certificate": "HRMS-PR-001",
    "REQCERTSAL": "HRMS-PR-001",
    "REQCERTEMP": "HRMS-PR-002",
    "REQCERTEXP": "HRMS-PR-003",
}

#: **لم تُحسم — قرار مالك لا هندسة.** أي ورقة رسمية يتسلّمها الموظف
#: سؤالٌ عن السياسة لا عن الشيفرة، فتبقى هنا مرئية حتى تُحسم.
UNDECIDED = {
    "REQPROMO": "«ترقية أو تعديل راتب» — PR-018 ترقية أم PR-019 تعديل راتب؟",
    "REQCON": "«تجديد عقد أو عدم تجديد» — PR-012 أم PR-013؟ الورقة تتبع النتيجة.",
    "REQRESE": "تجديد إقامة مبكر — PR-034 «تفويض تجديد إقامة» تفويض لا قرار.",
    "REQRESN": "تجديد إقامة عادي — نفس السؤال.",
    "REQMIS": "«مهمة عمل خارجية» — لا قالب مطابق بين الاثنين والأربعين.",
    "REQWLOC": "«تكليف مؤقت بموقع» — بلا قالب. PR-017 يطابق اسًما.",
    "ADMLIC": "«تجديد مستند شركة» — كيانه الشركة لا الموظف (internal_action).",
}


def test_the_measurement_is_possible():
    """أداة لا تقرأ شيًئا تُمرّر كل شيء."""
    names = _template_names()
    assert len(names) >= 40, f"لم تُقرأ القوالب: {len(names)}"
    assert _types_producing_documents(), "لا نوع يُنتج مستنًدا"


def test_every_reviewed_mapping_is_actually_in_place():
    """**جوهر V-A**: ما قرّرناه هو ما في الشيفرة."""
    actual = {rt["code"]: rt.get("default_template_code")
              for rt in _types_producing_documents()}
    wrong = {code: (actual.get(code), expected)
             for code, expected in REVIEWED.items()
             if actual.get(code) != expected}
    assert not wrong, f"خريطة انحرفت عن المراجَع (فعلي، متوقَّع): {wrong}"


def test_every_reviewed_template_exists():
    """قالب مقرَّر وغير موجود = خريطة تكذب بثقة."""
    names = _template_names()
    missing = [c for c in REVIEWED.values() if c not in names]
    assert not missing, f"قوالب مقرَّرة وغير معرَّفة: {missing}"


def test_no_document_producing_type_is_silently_unreviewed():
    """كل نوع يُنتج ورقة إمّا مقرَّر أو مُعلَن أنه لم يُحسم.

    والسكوت هو ما أنتج العطل: الخريطة تنحرف بلا أن يسأل أحد.
    """
    known = set(REVIEWED) | set(UNDECIDED)
    silent = [rt["code"] for rt in _types_producing_documents()
              if rt["code"] not in known]
    assert not silent, (
        f"أنواع تُنتج مستنًدا بلا قرار ولا إعلان: {silent}"
    )


def test_the_undecided_are_named_not_hidden():
    """والملتبس يبقى مقروًءا: من يفتح الملف يعرف ما ينتظر قراًرا."""
    assert UNDECIDED, "لا شيء معلَّق — احذف القائمة أو راجع الفحص"
    for code, why in UNDECIDED.items():
        assert len(why) > 20, f"«{code}» بلا سبب مفهوم"


def test_declared_workflow_documents_all_exist():
    """وسجلّ المسارات لا يعلن مستنًدا لا وجود له."""
    bad = [(wf, od) for wf, body in R.CANONICAL_WORKFLOWS.items()
           for od in (body.get("od") or []) if od not in R.CANONICAL_DOCUMENTS]
    assert not bad, f"مستندات معلَنة وغير معرَّفة: {bad}"
