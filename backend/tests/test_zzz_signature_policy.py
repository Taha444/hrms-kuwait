# -*- coding: utf-8 -*-
"""P5-23 — سياسة التوقيع معلَنة ولا يقرؤها أحد.

**ما ظهر بالقياس:**

``requires_physical_signature`` راية على **كل** نوع طلب (54 نوًعا)،
ولها عمود في القاعدة — و**لا موضع واحد يقرؤها**: لا المحرّك، ولا
الواجهة، ولا تقرير. النمط نفسه الذي ظهر في ``detail`` بخطّ زمن
التجديد و``original_user_id`` في التدقيق: بيانات تُكتب ولا تُقرأ.

والسلوك يأتي من مكان آخر تماًما: ``decide`` يوقف الطلب على
``awaiting_signature`` حين يكون ``stage.kind == "hr_review"`` — أي أن
**بنية السلسلة** هي السياسة الفعلية، والراية زينة.

**والانحراف مقيس**: 14 نوًعا من 54 تُعلن «توقيع مادّي مطلوب» وليس في
سلسلتها مرحلة توقيع أصًلا. ومنها ما لا يُحتمل فيه ذلك:

* ``REQRESIGN`` — استقالة
* ``REQEOS`` — تسوية نهاية خدمة
* ``REQCLR`` — إخلاء طرف
* ``ADMWARN`` — إنذار
* ``REQPROMO`` — ترقية أو تعديل راتب
* ``REQCON`` — تجديد عقد

فيُصدر النظام تسوية نهاية خدمة ويُغلق الطلب «مكتمل» بلا أن يوقّع
الموظف شيًئا — بينما تعريف النوع يقول إن توقيعه مطلوب.

**وأي الطرفين يُصحَّح قرار عمل**: هل تُرفَع الراية عن الأربعة عشر (لا
توقيع مطلوب فعًلا)، أم تُضاف لها مرحلة توقيع (والراية محقّة)؟ لكلٍّ
أثر مختلف تماًما على إجراءات الشركة، ولا يُستنتج من الشيفرة.

**أما أن يتناقض المعلَن والواقع فليس سؤاًلا.** فيُقاس هنا ويُثبَّت عدده،
فلا ينمو صامًتا ولا يُنسى.
"""
from __future__ import annotations

import inspect

from app import workflow

#: الأنواع التي تُعلن توقيًعا ولا تطلبه — **حالة معلومة تنتظر قرار المالك**.
#:
#: تُثبَّت هنا بالاسم لا بالعدد وحده: نوع يُضاف غًدا بالعيب نفسه يسقط
#: الاختبار، ونوع يُصحَّح يسقطه أيًضا — وكلاهما وقت مراجعة صحيح.
KNOWN_DIVERGENT = {
    "REQWLOC", "REQMIS", "REQRESE", "REQRESN", "REQWP", "REQTRFLIC",
    "REQTRF", "REQPROMO", "REQCON", "REQRESIGN", "REQEOS", "REQCLR",
    "ADMWARN", "ADMLIC",
}


def _declares_signature(rt: dict) -> bool:
    return bool(rt.get("requires_physical_signature"))


def _has_signature_stage(rt: dict) -> bool:
    """السياسة الفعلية: مرحلة ``hr_review`` هي ما يوقف الطلب للتوقيع."""
    return any(s.get("kind") == "hr_review"
               for s in (rt.get("approval_chain_json") or []))


def test_the_stage_kind_is_what_actually_stops_for_a_signature():
    """خطّ الأساس: السلوك من بنية السلسلة لا من الراية."""
    src = inspect.getsource(workflow.decide)
    assert 'kind == "hr_review"' in src, "تغيّر ما يوقف الطلب — راجع القياس"
    assert "awaiting_signature" in src
    assert "requires_physical_signature" not in src, (
        "صارت الراية تُقرأ في القرار — أعد قياس الانحراف، فقد تغيّر أساسه"
    )


def test_the_declared_flag_is_read_nowhere():
    """**جوهر البند**: سياسة معلَنة على 54 نوًعا ولا قارئ لها.

    ولو كانت تُقرأ لَظهر الانحراف عند أول استعمال. وهي لا تُقرأ، فبقي
    التناقض صامًتا: التعريف يقول شيًئا والنظام يفعل غيره.
    """
    from pathlib import Path

    root = Path(workflow.__file__).resolve().parent
    readers = []
    for path in root.rglob("*.py"):
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "requires_physical_signature" not in line:
                continue
            # التعريف والإعلان ليسا قراءة
            if any(tok in line for tok in ("requires_physical_signature=",
                                           '"requires_physical_signature":',
                                           "requires_physical_signature: ")):
                continue
            readers.append(f"{path.name}:{i}")
    assert not readers, (
        "صارت الراية تُقرأ — احذف هذا الاختبار وأعد قياس الانحراف: "
        + ", ".join(readers)
    )


def test_the_divergence_is_exactly_the_known_set():
    """والانحراف مثبَّت بالاسم: لا ينمو صامًتا ولا يُنسى.

    نوع يُضاف غًدا يُعلن توقيًعا بلا مرحلة يسقط هنا؛ ونوع يُصحَّح يسقط
    هنا أيًضا. وكلاهما وقت مراجعة صحيح — بخلاف عدٍّ يُحدَّث بلا قراءة.
    """
    divergent = {rt["code"] for rt in workflow.DEFAULT_REQUEST_TYPES
                 if _declares_signature(rt) and not _has_signature_stage(rt)}
    added = divergent - KNOWN_DIVERGENT
    fixed = KNOWN_DIVERGENT - divergent
    assert not added, (
        f"أنواع جديدة تُعلن توقيًعا ولا تطلبه: {sorted(added)}"
    )
    assert not fixed, (
        f"صُحّحت أنواع — احذفها من KNOWN_DIVERGENT: {sorted(fixed)}"
    )


def test_no_type_stops_for_a_signature_it_never_declared():
    """والاتّجاه الآخر نظيف — وهو ما يجعل الأول انحراًفا لا فوضى.

    لا نوع يوقف الطلب للتوقيع بينما تعريفه يقول إنه لا يحتاجه. فالعيب
    في اتّجاه واحد: إعلان بلا تنفيذ، لا تنفيذ بلا إعلان.
    """
    rogue = {rt["code"] for rt in workflow.DEFAULT_REQUEST_TYPES
             if _has_signature_stage(rt) and not _declares_signature(rt)}
    assert not rogue, (
        f"يوقف الطلب للتوقيع بلا إعلان: {sorted(rogue)}"
    )


def test_the_most_consequential_documents_are_in_the_gap():
    """وليس الانحراف في هوامش الكتالوج.

    استقالة، وتسوية نهاية خدمة، وإخلاء طرف، وإنذار — أربعة يُحتجّ بها
    على الطرفين، وتُصدَر بلا توقيع الموظف بينما تعريفها يشترطه.
    """
    heavy = {"REQRESIGN", "REQEOS", "REQCLR", "ADMWARN"}
    assert heavy <= KNOWN_DIVERGENT, sorted(heavy - KNOWN_DIVERGENT)


def test_a_type_that_needs_a_signature_has_something_to_sign():
    """**وفجوة ثانية مستقلّة**: توقيع على مستند لا وجود له.

    ``REQWLOC`` يُعلن توقيًعا مطلوًبا و``default_template_code`` فيه
    ``None`` — فحتى لو قرّر المالك أن التوقيع مطلوب، لا ورقة تُوقَّع.
    والقرار في مسار واحد لا يُغني عن الآخر.
    """
    naked = [rt["code"] for rt in workflow.DEFAULT_REQUEST_TYPES
             if _declares_signature(rt) and rt.get("produces_document")
             and not rt.get("default_template_code")]
    assert naked == ["REQWLOC"], (
        f"تغيّرت الفجوة: {naked} — راجعها بدل تحديث الرقم"
    )
