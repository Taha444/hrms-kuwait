# -*- coding: utf-8 -*-
"""V-C — إجازة السفر: عطلان مختلفان تماًما، فلا يُحكَم قبل التمييز.

يحذّر الكيت من الخلط:

- ``travel_required=true`` ولم تدخل مرحلة المندوب  ⇒ **عطل توجيه**
- ``false`` رغم وجود بيانات سفر                    ⇒ **عطل نموذج**

والدليل التاريخي كان من النوع الثاني، وموثَّق في الشيفرة (QA-09): دلالة
``show`` لم يكن لها مُقيِّم، فظهر حقل «الوجهة» دائًما فملأه المستخدم
ظاًنا أنه يعني السفر، ولم يؤشّر ``travel_required`` قط — فوصل الحقل
فارًغا في كل طلب.

وهذا الملف يقيس الشقّين على البناء الحالي: أن التأشير **يوجّه**، وأن
تركه لا يوجّه، وأن الحقل المشروط لا يظهر بلا شرطه.
"""
from __future__ import annotations

from app import form_schemas, workflow


def _leave_schema():
    return form_schemas.get_schema("REQLV")


def test_the_travel_flag_exists_and_gates_a_field():
    """الادّعاء الأول فارغ لو زال الحقل أو زال شرطه."""
    schema = _leave_schema()
    codes = {f["code"] for f in schema["fields"]}
    assert "travel_required" in codes, "لا حقل سفر — راجع الاختبار لا الشيفرة"

    gated = [c for c in (schema.get("conditional") or [])
             if c.get("when", {}).get("travel_required") is True]
    assert gated, "لا قاعدة مشروطة على السفر"


def test_the_conditional_field_is_hidden_until_travel_is_ticked():
    """**عطل النموذج التاريخي**: «الوجهة» كانت تظهر دائًما.

    فيملؤها المستخدم ظاًنا أنها تعني السفر، ولا يؤشّر الخانة — فيصل
    ``travel_required`` فارًغا مع بيانات سفر كاملة.
    """
    schema = _leave_schema()
    _add, hidden = form_schemas.conditional_requirements(schema, {})
    gated = set()
    for c in schema.get("conditional") or []:
        gated.update(c.get("show") or [])
    assert gated, "لا حقول محكومة بـshow — لا شيء يُقاس"
    assert gated <= set(hidden), (
        f"حقل مشروط يظهر بلا شرطه: {gated - set(hidden)}"
    )


def test_ticking_travel_reveals_the_field():
    """والعكس: التأشير يُظهرها — وإلا كان الإخفاء عطًلا جديًدا."""
    schema = _leave_schema()
    _add, hidden = form_schemas.conditional_requirements(schema, {"travel_required": True})
    gated = set()
    for c in schema.get("conditional") or []:
        if c.get("when", {}).get("travel_required") is True:
            gated.update(c.get("show") or [])
    assert gated and not (gated & set(hidden)), (
        f"التأشير لم يُظهر الحقول المشروطة: {gated & set(hidden)}"
    )


# ---------------------------------------------------------------------------
# الشقّ الثاني: هل التأشير يوجّه فعًلا؟
# ---------------------------------------------------------------------------
def _leave_type():
    """تعريف نوع «إجازة» من الكتالوج — يُقرأ ولا يُخمَّن اسمه."""
    for rt in workflow.DEFAULT_REQUEST_TYPES:
        chain = rt.get("approval_chain_json") or []
        if any(str(s.get("when", {}).get("field")) == "travel_required"
               for s in chain):
            return rt
    raise AssertionError("لا نوع طلب فيه مرحلة مشروطة بالسفر")


def _stage_labels(payload):
    """المراحل التي تنطبق فعًلا على هذه الحمولة."""
    rt = _leave_type()
    return [s.get("label") or s.get("role")
            for s in (rt.get("approval_chain_json") or [])
            if workflow._stage_applies(s, payload)]


def test_travel_true_adds_the_delegate_stage():
    """``true`` ⇒ تدخل مرحلة المندوب (إذن مغادرة البلاد)."""
    with_travel = _stage_labels({"travel_required": True})
    assert any("مندوب" in str(s) for s in with_travel), (
        f"السفر لم يُدخل مرحلة المندوب: {with_travel}"
    )


def test_travel_false_does_not_route_through_the_delegate():
    """و``false`` ⇒ إجازة داخل الكويت لا تمرّ بالمندوب.

    والحدّ المقابل مهمّ: توجيه يشمل الجميع ليس توجيًها.
    """
    without = _stage_labels({"travel_required": False})
    assert not any("مندوب" in str(s) for s in without), (
        f"إجازة بلا سفر مرّت بالمندوب: {without}"
    )
    assert without, "السلسلة فارغة — القياس بلا معنى"
