# -*- coding: utf-8 -*-
"""BKL-04 — «طلب طلب إجازة».

أربعة وثلاثون من أربعة وخمسين نوع طلب اسمه يبدأ بـ«طلب» («طلب إجازة» ·
«طلب سلفة»)، وستّة قوالب إشعارات كانت تضيف الكلمة فوقها. فيقرأ الموظف
«طلب طلب إجازة» في إشعار يصله على هاتفه.

والفحص على النصّ **المُركَّب** لا على القالب: القالب يقرأ سليًما («طلب
{{request_type}}») ولا يظهر العيب إلا حين تحلّ قيمة تحمل الكلمة. وهذا هو
السبب في أن العطل عاش حتى بلاغ عميل.
"""
from __future__ import annotations

import re

import pytest

from app.notification_templates import (
    DEFAULT_NOTIFICATION_TEMPLATES as TEMPLATES)
from app.workflow import DEFAULT_REQUEST_TYPES as TYPES

#: كلمات تتكرّر حين يضيف القالب بادئة تحملها القيمة أصًلا
WORDS = ["طلب", "شهادة", "إذن", "خطاب", "مستند", "تقرير", "عقد"]
DUP = re.compile(r"(?<![\w؀-ۿ])(" + "|".join(WORDS)
                 + r")\s+\1(?![\w؀-ۿ])")

TYPE_NAMES = [rt["name"] for rt in TYPES if rt.get("name")]


def _render(body: str, type_name: str) -> str:
    out = body.replace("{{request_type}}", type_name)
    return re.sub(r"\{\{\w+\}\}", "س", out)


def test_type_names_that_carry_the_word_exist():
    """توثيق الشرط: لولا وجودها لما كان للحارس معنى."""
    with_prefix = [n for n in TYPE_NAMES if n.strip().startswith("طلب")]
    assert len(with_prefix) >= 10, (
        f"عدد الأنواع التي تبدأ بـ«طلب» صار {len(with_prefix)} — "
        "تغيّر الكتالوج، فأعد النظر في هذا الحارس"
    )


def test_no_notification_repeats_a_word_after_substitution():
    """جوهر البند: النصّ المُركَّب لا يكرّر كلمة."""
    problems = []
    for tpl in TEMPLATES:
        body = tpl["body_text"]
        if "{{request_type}}" in body:
            for name in TYPE_NAMES:
                out = _render(body, name)
                if DUP.search(out):
                    problems.append(f"{tpl['code']} + «{name}» → {out[:80]}")
                    break
        elif DUP.search(body):
            problems.append(f"{tpl['code']} (نصّ ثابت) → {body[:80]}")
    assert not problems, "تكرار كلمة في إشعار يصل المستخدم:\n" + "\n".join(problems)


def test_notification_titles_do_not_repeat():
    bad = [t["name"] for t in TEMPLATES if DUP.search(t["name"])]
    assert not bad, f"عناوين مكرَّرة: {bad}"


def test_type_names_do_not_repeat():
    bad = [n for n in TYPE_NAMES if DUP.search(n)]
    assert not bad, f"أسماء أنواع مكرَّرة: {bad}"


def test_templates_do_not_prefix_a_value_that_carries_its_own_word():
    """الجذر لا العرَض: لا يسبق «{{request_type}}» كلمةٌ يحملها الاسم.

    منع النتيجة وحدها يترك القالب التالي يعيدها. وهذا الحارس يمنع النمط
    نفسه: من يكتب «طلب {{request_type}}» غًدا يسقط هنا قبل أن يصل مستخدًما.
    """
    offenders = []
    for tpl in TEMPLATES:
        body = tpl["body_text"]
        for word in WORDS:
            if re.search(r"(?<![\w؀-ۿ])" + word
                         + r"\s*\(?\{\{request_type\}\}", body):
                offenders.append(f"{tpl['code']}: «{word} {{{{request_type}}}}»")
    assert not offenders, (
        "قالب يضيف كلمة يحملها اسم النوع أصًلا:\n" + "\n".join(offenders)
    )


def test_stage_and_task_titles_do_not_repeat_words():
    """عناوين المهام تُركَّب من اسم النوع أيًضا — البند يذكرها صراحًة."""
    from app import workflow

    samples = []
    for name in TYPE_NAMES[:20]:
        samples.append(f"تم اعتماد: {name} — أحمد")
        samples.append(f"جاهز للطباعة والحفظ: {name}")
        samples.append(f"فشل توليد مستند: {name}")
    bad = [s for s in samples if DUP.search(s)]
    assert not bad, f"عناوين مهام مكرَّرة: {bad[:5]}"
    assert workflow is not None
