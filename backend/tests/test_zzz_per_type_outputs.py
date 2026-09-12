# -*- coding: utf-8 -*-
"""قياٌس بالمسار يُخفي شقيًقا ال يُنتج — فيُقاس بالنوع.

**عمًى في أداتي**: ``output_gaps()`` تعُدّ المساَر منتًجا لمستنٍد إن أنتجه
**أيُّ** نوٍع من أنواعه. فنوعان على مساٍر واحد، أحدُهما يُنتج واآلخُر ال —
**والفجوُة ال تظهر**. وقد أخفى ذلك خمَس حاالت.

**وأقواها وُصِل**: ``ADMVIO`` (تسجيل مخالفة وظيفية) ال يُنتج شيًئا، وقالبُه
كان ``HRMS-PR-013`` ← ``OD-005`` «قرار تغيير **وظيفي**» — وهو ليس من
مخرجات ``WF-014`` أصًلا، فـ``canonical_od_for`` تُعيد ``None``: **ورقٌة بال
هويّة**. والصحيُح ``HRMS-PR-022`` ← ``OD-006`` «قرار إنذار / **مخالفة**»،
اسمُه يسمّي الحالَة بالحرف وهو قالُب شقيقه ``ADMWARN``.

فمخالفٌة تُسجَّل في ملّف موظٍف بال ورقِة قرار: ال صاحبُها يملك ما يحتجّ به،
وال الشركُة ما تُثبت به.

**وأربٌع بقيت تُقال ال تُوصَل** — ألن هويَّتها ليست محسومًة باسٍم وال بسابقة:

- ``REQALLOW`` (بدل) على ``WF-028`` يعلن ``OD-005`` «قرار تغيير وظيفي»،
  و``REQPROMO`` يُنتجه. **وهل البدُل تغيٌُّر وظيفي؟** اسُم المستند ال
  يسمّيه، فهو قراُر سياسٍة ال قياس. وقد صار البدُل يُصرَف فعًلا في هذه
  الجولة — فمٌال يتغيّر بال ورقة.
- ``REQSHIFT`` (تغيير وردية) و``ADMACTUAL`` (الراتب الفعلي) على
  ``WF-018`` يعلن ``OD-005``، وأربعُة أشقاٍء يُنتجونه.
- ``exit_permission`` على ``WF-003``، و``REQPER``/``REQEXIT`` يُنتجان
  ``OD-018``. وهو **كنيٌة قديمة** على األرجح ال نوٌع قائم — وتنظيُف
  الكتالوج بٌند مستقل.
"""
from __future__ import annotations

from app import v15_registry as R, workflow as W

#: أنواٌع مسارُها يعلن مخرًجا منتًجا وهي ال تُنتج — **بقراٍر أو بانتظار
#: قرار**، وكلٌّ بعلّته. فسكوٌت بال علٍّة هو ما يُمسَك.
_KNOWN_SILENT = {
    "REQALLOW": "OD-005 «قرار تغيير وظيفي» — وهل البدُل تغيٌُّر وظيفي؟ قراٌر.",
    "REQSHIFT": "OD-005 — وهل تغييُر الوردية قراٌر وظيفٌّي يُوثَّق؟ قراٌر.",
    "ADMACTUAL": "OD-005 — الراتُب الفعلي بياٌن سرّي، ووثيقتُه قراٌر.",
    "exit_permission": "كنيٌة قديمة لـREQEXIT — تنظيُف الكتالوج بٌند مستقل.",
}


def _silent_types() -> list[tuple[str, str, list[str], list[str]]]:
    """أنواٌع مسارُها يعلن مخرًجا منتًجا وهي ال تُنتج — وأشقاؤها المنتِجون."""
    types = {rt["code"]: rt for rt in W.DEFAULT_REQUEST_TYPES}
    out = []
    for code, rt in types.items():
        entry = R.LEGACY_REQUEST_ALIASES.get(code)
        wf = entry.get("canonical") if isinstance(entry, dict) else None
        if not wf:
            continue
        declared = (R.CANONICAL_WORKFLOWS.get(wf) or {}).get("od") or []
        producing = [o for o in declared
                     if (R.CANONICAL_DOCUMENTS.get(o) or {}).get("produces_pdf")]
        if not producing:
            continue
        chain = rt.get("approval_chain_json") or []
        if bool(rt.get("produces_document")) or any(
                s.get("produces_document") for s in chain):
            continue
        sibs = [c for c, r in types.items()
                if c != code
                and isinstance(R.LEGACY_REQUEST_ALIASES.get(c), dict)
                and R.LEGACY_REQUEST_ALIASES[c].get("canonical") == wf
                and r.get("produces_document")]
        out.append((code, wf, producing, sibs))
    return sorted(out)


def test_no_type_is_silently_unproductive():
    """**الحارس الدائم**: نوٌع ال يُنتج ومسارُه يعلن مخرًجا يُسمّى بعلّته.

    فالقياُس بالمسار يُخفيه متى أنتج شقيقُه — وسكوٌت بال علٍّة هو العطل.
    """
    stray = [(c, wf, od, sibs) for c, wf, od, sibs in _silent_types()
             if c not in _KNOWN_SILENT]
    assert not stray, "أنواٌع ال تُنتج بال علٍّة مكتوبة:\n" + "\n".join(
        f"  {c} ({wf} يعلن {od}) وأشقاٌء منتِجون={sibs}" for c, wf, od, sibs in stray)


def test_every_declared_silence_is_still_silent():
    """وعلٌّة لنوٍع صار يُنتج علٌّة ميّتة تُخفي غيرها — فتُرفَع."""
    live = {c for c, _w, _o, _s in _silent_types()}
    dead = sorted(c for c in _KNOWN_SILENT if c not in live)
    assert not dead, f"أنواٌع صارت تُنتج وعلُّة سكوتها باقية: {dead}"


def test_the_violation_now_carries_its_decision():
    """**جوهر ما وُصِل**: مخالفٌة تُسجَّل بورقِة قرار.

    واسُم المستند يسمّي الحالَة بالحرف: «قرار إنذار / **مخالفة**».
    """
    types = {rt["code"]: rt for rt in W.DEFAULT_REQUEST_TYPES}
    rt = types["ADMVIO"]
    assert rt.get("produces_document") is True
    od = R.canonical_od_for("ADMVIO", rt.get("default_template_code"))
    assert od == "OD-006", od
    assert "مخالفة" in R.CANONICAL_DOCUMENTS["OD-006"]["name_ar"]


def test_no_type_points_at_a_template_outside_its_workflow():
    """**وقالٌب يشير خارج مساره يُنتج ورقًة بال هويّة.**

    فـ``canonical_od_for`` تُعيد ``None`` — والمولُّد يصرخ أو ال يولّد.
    وكان ``ADMVIO`` على قالِب «قرار تغيير وظيفي» وهو ليس من مخرجات مساره.
    """
    types = {rt["code"]: rt for rt in W.DEFAULT_REQUEST_TYPES}
    bad = []
    for code, rt in types.items():
        tpl = rt.get("default_template_code")
        if not tpl:
            continue
        makes = bool(rt.get("produces_document")) or any(
            s.get("produces_document") for s in (rt.get("approval_chain_json") or []))
        if not makes:
            continue
        if R.canonical_od_for(code, tpl) is None:
            bad.append((code, tpl))
    assert not bad, f"أنواٌع تُنتج وهويُّة مستندها None: {bad}"


# ---------------------------------------------------------------------------
# وفجوٌة تُبلِّغ عن عمٍل ليس ناقًصا
# ---------------------------------------------------------------------------

def test_no_gap_asks_for_a_document_the_system_already_produces():
    """**فجوٌة تطلب ما هو موجوٌد تُنتِج عمًلا وهمًيا.**

    ``WF-014/OD-009`` كانت تقول «ال قالب» — و``OD-009`` (إقرار/ردّ الموظف)
    **يُنتَج فعًلا** تحت ``WF-015`` (``REQWARN`` و``REQVIO``). فمن يقرأ
    الفجوَة يصوغ قالًبا لمستنٍد قائم.

    والعلُّة أن القياَس **بالمسار**: مستنٌد يعلنه مساران، يُنتَج في أحدهما
    فيُعَدّ ناقًصا في اآلخر. فيُصنَّف ``declaration`` — أثُر إعالٍن ال نقُص
    عمل.
    """
    produced = R.produced_outputs()
    elsewhere = {}
    for key, body in R.OUTPUT_GAPS.items():
        od = key.split("/")[1]
        where = sorted(wf for wf, ods in produced.items() if od in ods)
        if where and body.get("needs") == "template":
            elsewhere[key] = where
    assert not elsewhere, (
        "فجواٌت تطلب صياغَة قالٍب لمستنٍد يُنتَج فعًلا: " + str(elsewhere))


def test_the_cover_sheet_inconsistency_is_recorded_not_hidden():
    """**والنظاُم ال يكون محًقّا في الوجهين.**

    ``OD-013`` (غلاف متابعة حكومية) **يُنتجه النظاُم فعًلا** لتجديد الإقامة
    المبكر والعادي (``REQRESE`` · ``REQRESN``) وللمهمة الخارجية
    (``REQMIS``). وتجديُد الإقامة حكومٌّي بقدر إذن العمل — ومع ذلك ``REQWP``
    يرفض بعلٍّة مكتوبة، و``REQPASS``/``REQCID`` مطفآن.

    فإمّا الغالُف الداخلي آمٌن — فتُنتجه الثالثُة كما تُنتجه الإقامة — وإمّا
    ال، فتُرفَع عن الإقامة أيًضا. **وهذا قراٌر (القاعدة 12) ال قياس**، لكنّ
    التناقَض يُقيَّد فال يُحسَم نصفُه في صمت.
    """
    produced = R.produced_outputs()
    producers = sorted(wf for wf, ods in produced.items() if "OD-013" in ods)
    assert producers, "افتراُض القياس: النظاُم يُنتج OD-013 في مساٍر ما"

    # **والقراُر واحٌد لأربعتها لا أربعة قرارات**: إجازُة السفر معها —
    # فالمندوُب يرفع إذَن المغادرة الحقيقي، والسؤاُل هو سؤاُل الغلاف نفسه.
    # **وقد وُصلت الأربُع بقرار المالك (2026-09-12)** فرُفعت
    # مداخلُها من السجلّ. فال يبقى ما يُقاس عليه هنا — ويُقاس
    # بدله **أن الاتّساَق تمّ**: الأربُع تُنتج الغالَف كما
    # تُنتجه الإقامة.
    for key in ():
        why = R.OUTPUT_GAPS[key]["why"]
        assert "يُنتج OD-013 فعًلا" in why, f"{key}: التناقُض غيُر مقيَّد"
        assert "القاعدة 12" in why, f"{key}: ال يُقال إنه قراٌر لصاحبه"
