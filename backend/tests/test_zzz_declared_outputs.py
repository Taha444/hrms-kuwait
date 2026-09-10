# -*- coding: utf-8 -*-
"""البند 4 — مخرٌج يُعلَن ولا يُنتَج.

**العطل المقيس**: السجلّ يعلن لكل مسار مستنداته (``CANONICAL_WORKFLOWS[wf]
["od"]``)، و**تسعة عشر مستنًدا معلًنا لا يُنتَج**. والإعلان ليس توثيًقا
خامًلا: يُنشَر في ``/api/manifest`` وفي حزمة الأدلّة وفي كل ما يعرض المسار
القانوني. فيُقرأ وعًدا — «هذا المسار يُصدر هذه الورقة» — ولا ورقة.

وأثقلها وزًنا قانوًنيا:

- ``WF-009 → OD-022`` «اتفاقية سلفة/قرض». والسجلّ يقول «اتفاق وجدول سداد
  **موقّع**»، ونصّ الطلب الرسمي يقول «أتعهد بالالتزام بخطة السداد
  المعتمدة». فالتعهّد نٌصّ في الطلب، والأداة التي تُوقَّع لا وجود لها:
  يُعتمد القرض ويُجدوَل الاستقطاع من الأجر بلا سٍند موقّع.
- ``WF-013 → OD-008`` «قرار خصم» — والقالب قائم. خصٌم من الأجر بلا قرار.
- ``WF-008 → OD-021/BANK_ACCOUNT`` — تغيير حساب بنكي بلا إشعار يحمل
  القديم والجديد وشهر النفاذ.

**والبنود الخمسة المسمّاة في النطاق**: أربعٌة منها سليمة ومُنتَجة
(``WF-001→OD-011`` · ``WF-005→OD-001`` · ``WF-024→OD-015`` · وترقية
``WF-002`` بالحمولة قائمة)، والخامس ``WF-009→OD-022`` هو الثغرة.

**ولا تُختلَق ورقٌة رسمية**: تسعٌة من التسعة عشر بلا قالب في السجلّ
أصًلا، فتوليدها ليس إصلاح كود بل مستنٌد يُصاغ ويُعتمد — وادّعاء إنتاجه
أسوأ من غيابه. فالمُنجَز هنا **أن يُسمّى ما لا يُنتَج** بسببه وبما يلزم
لرفعه، ويُحرَس الطرفان: إعلاٌن جديد لا يُنتَج ولا يُسمّى، وسطٌر باٍق
لمستند صار يُنتَج فبطل عذره.
"""
from __future__ import annotations

from app import v15_registry as R


def test_every_unproduced_output_is_named():
    """**لا انحراف صامت**: كل معلٍَن لا يُنتَج له سطٌر بسببه.

    وهذا هو الحارس الذي يمنع تكرار العطل: من أضاف ``od`` إلى مسار ولم
    يُنتجه يجد الاختبار يسأله لماذا — لا يمرّ الوعد بلا وفاء ولا اعتذار.
    """
    unnamed = [k for k in R.output_gaps() if k not in R.OUTPUT_GAPS]
    assert not unnamed, (
        "مخرٌج معلٌن لا يُنتَج ولا سبَب مكتوًبا له — أضفه إلى OUTPUT_GAPS "
        f"أو أنتجه: {unnamed}")


def test_no_excuse_outlives_its_reason():
    """**والعذر يسقط بزوال سببه**: سطٌر لمستند صار يُنتَج يُحذَف.

    وسجٌل يحمل عيوًبا أُصلحت يُقرأ بعد شهور كأنها قائمة، فيُعاد إصلاح
    ما أُصلح ويُهمَل ما لم يُصلَح.
    """
    gaps = set(R.output_gaps())
    stale = [k for k in R.OUTPUT_GAPS if k not in gaps]
    assert not stale, f"سطٌر باقٍ وقد صار المستند يُنتَج — احذفه: {stale}"


def test_every_named_gap_says_what_it_needs():
    """ولكل سطر ما يلزم لرفعه: مستٌند يُعتمد، أو ربٌط يُكتب."""
    bad = [k for k, v in R.OUTPUT_GAPS.items()
           if v.get("needs") not in ("template", "wiring")
           or not (v.get("why") or "").strip()]
    assert not bad, f"سطٌر بلا تصنيف أو بلا سبب: {bad}"


def test_a_gap_that_claims_no_template_really_has_none():
    """**والتصنيف يُقاس لا يُدَّعى.**

    ``needs="template"`` يعني «لا قالب في السجلّ» — وهو الفرق بين قرار
    مالٍك وقرار مهندس. فلو كان له قالٌب لكان التصنيف عذًرا يؤجّل عمًلا
    ممكًنا.
    """
    with_template = {od for tpl, od in R.LEGACY_PRN_ALIASES.items()
                     if tpl.startswith("HRMS-PR-")}
    wrong = [k for k, v in R.OUTPUT_GAPS.items()
             if v.get("needs") == "template" and k.split("/")[1] in with_template]
    assert not wrong, f"صُنّف «بلا قالب» وله قالب: {wrong}"


def test_a_gap_that_claims_wiring_actually_has_a_template():
    """وعكسه: ``wiring`` تعني أن القالب جاهز — وإلا فهو انتظاٌر لا ربط."""
    with_template = {od for tpl, od in R.LEGACY_PRN_ALIASES.items()
                     if tpl.startswith("HRMS-PR-")}
    wrong = [k for k, v in R.OUTPUT_GAPS.items()
             if v.get("needs") == "wiring" and k.split("/")[1] not in with_template]
    assert not wrong, f"صُنّف «يلزمه ربط» ولا قالب له: {wrong}"


# ---------------------------------------------------------------------------
# الخمسة المسمّاة في النطاق
# ---------------------------------------------------------------------------

def test_the_four_sound_mappings_are_produced_not_merely_declared():
    """أربعٌة من الخمسة تُنتَج فعًلا — لا يُعاد إصلاحها ولا تنكسر."""
    produced = R.produced_outputs()
    for wf, od in (("WF-001", "OD-011"), ("WF-005", "OD-001"),
                   ("WF-024", "OD-015")):
        assert od in R.CANONICAL_WORKFLOWS[wf]["od"], f"{wf} لم يعد يعلن {od}"
        assert od in produced.get(wf, set()), f"{wf} يعلن {od} ولا يُنتجه"


def test_the_travel_promotion_is_counted_as_the_same_path():
    """**وترقية السفر مسار الإجازة نفسه لا نوٌع آخر.**

    من قاس بالكود الساكن وحده قرأ ``WF-002`` بلا نوع طلب يُحَل إليه —
    وهو خطُأ القياس لا عطٌل: الكنية تعلن ``WF-001``، والترقية بالحمولة
    (``travel_required``). فأداُة القياس تحتسبها، وإلا أبلغت عن عطل لا
    وجود له. (وقع ذلك في أول قياس.)
    """
    produced = R.produced_outputs()
    assert "OD-011" in produced.get("WF-002", set()), \
        "لم تُحتسب ترقية الحمولة — فيُقرأ مسار السفر بلا مخرج"


def test_the_loan_agreement_is_named_as_the_gap_it_is():
    """والخامس ثغرٌة مسمّاة: سنُد الاستقطاع من الأجر لا وجود له."""
    entry = R.OUTPUT_GAPS.get("WF-009/OD-022")
    assert entry, "ثغرة القرض غير مسمّاة"
    assert entry["needs"] == "template"
    assert "الأجر" in entry["why"], entry["why"]


# ---------------------------------------------------------------------------
# والوعد يُنشَر، فيُنشَر معه ما لم يُوفَ به
# ---------------------------------------------------------------------------

def test_the_registry_endpoint_publishes_the_shortfall(client):
    """**ردٌّ يعلن ولا يقيّد يشهد بما لا يقع.**

    ``/requests/registry`` ينشر ``canonical_workflows`` بمستندات كل مسار،
    ومن يقرأه — واجهًة أو تدقيًقا أو حزمة أدلّة — يقرأ الإعلان وعًدا. فنشُر
    الوعد وحده يجعل السجلّ يشهد بورٍق لا يصدر.
    """
    from tests.conftest import auth_headers, login

    body = client.get("/api/requests/registry",
                      headers=auth_headers(login(client, "100000000002", "hr12345"))).json()
    gaps = body.get("output_gaps")
    assert gaps, "السجلّ يُنشَر بلا ما لم يُوفَ به"
    assert set(gaps) == set(R.output_gaps())
    assert gaps["WF-009/OD-022"]["needs"] == "template"


def test_the_summary_counts_what_is_missing(client):
    """ورقٌم لا يُنشَر لا يُلاحَظ نموّه."""
    from tests.conftest import auth_headers, login

    body = client.get("/api/requests/registry",
                      headers=auth_headers(login(client, "100000000002", "hr12345"))).json()
    assert body["summary"]["declared_outputs_not_produced"] == len(R.output_gaps())
