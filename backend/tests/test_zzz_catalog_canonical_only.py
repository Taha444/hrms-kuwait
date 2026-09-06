# -*- coding: utf-8 -*-
"""البنود 10 و11 و16 — كتالوج الإنشاء يعرض ما يُقبل فقط.

**11 — أُغلق قبل هذه الجولة.** التقرير يقول إن HR يرى الخمسة
``ADMEMP · ADMLIC · ADMMISS · ADMSIGN · ADMTASK`` كأنها طلبات. والقياس:
كلّها موسومة ``internal_action`` في السجل ومحجوبة عن كتالوج الإنشاء.

**والظاهر أربعة غيرها** — ``ADMACTUAL · ADMDED · ADMVIO · ADMWARN`` —
وهي **طلبات حقيقية** بسلاسل اعتماد (2–3 مراحل) ومسارات قانونية: إصدار
إنذار، وتسجيل مخالفة، وخصم، وتعديل راتب فعلي. فحجبها إزالة ميزة لا
تنظيف كتالوج.

**16 — أُغلق كذلك.** ``REQSIG`` تملكها وحدة التوقيع، فتُحجب من الكتالوج
ويُرفض إنشاؤها برسالة تدلّ على مكانها الصحيح.

**10 — العطل الحقيقي الوحيد**: ``REQADV`` مظلّة قديمة «طلب سلفة أو
قرض» بلا نوع فرعي، بجانب ``advance`` و``loan`` اللذين هما تفصيلها. فيقف
المستخدم أمام ثلاثة خيارات لخدمتين. ودمج الهوية لا يمسكها لأن مفتاحها
``(WF-009, None)`` لا يساوي ``(WF-009, ADVANCE)``.
"""
from __future__ import annotations

from collections import defaultdict

from app import module_owned, v15_registry as R, workflow
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
EMP = ("100000000101", "emp12345")


def _catalog(client, acct) -> list[str]:
    r = client.get("/api/requests/types", headers=auth_headers(login(client, *acct)),
                   params={"creatable_only": True})
    assert r.status_code == 200, r.text[:200]
    return [x.get("code") for x in r.json()]


def test_the_legacy_umbrella_is_gone_and_its_parts_remain(client):
    """**جوهر البند 10**: خدمتان لا ثلاثة خيارات."""
    for acct in (HR, EMP):
        codes = _catalog(client, acct)
        assert "REQADV" not in codes, f"المظلّة ما زالت معروضة: {acct[0]}"
        assert "advance" in codes and "loan" in codes, (
            f"اختفى التفصيل مع المظلّة: {acct[0]}"
        )


def test_the_rule_is_derived_not_hardcoded():
    """**والقاعدة من السجلّ لا باسم كود**: مظلّة + أنواع فرعية ⇒ تُخفى المظلّة.

    فمظلّة تُتقاعَد غًدا تختفي يوم يُوسَم تفصيلها، لا يوم يتذكّرها أحد.
    """
    from app.routers import requests as req_router
    import inspect

    src = inspect.getsource(req_router.list_request_types)
    assert "_umbrella_hidden" in src
    # التعليق يشرح بالمثال، والمنطق لا يذكر كوًدا. فيُقرأ التنفيذ وحده —
    # أول كتابة قرأت المصدر كلّه فاتّهمت شرًحا سليًما.
    code_only = "\n".join(ln for ln in src.splitlines()
                          if not ln.strip().startswith("#"))
    assert "REQADV" not in code_only, "القاعدة كُتبت باسم كود بعينه"


def test_hiding_the_umbrella_touches_exactly_one_family():
    """وأثرها مقيس على الكتالوج كلّه: حالة واحدة، فلا تُخفي خدمًة قائمة.

    ولو صار لمسار آخر مظلّة وتفصيل، سقط هذا الحارس فيُراجَع القرار قبل
    أن يختفي شيء بصمت.
    """
    fam = defaultdict(lambda: {"umbrella": [], "subtyped": 0})
    for rt in workflow.DEFAULT_REQUEST_TYPES:
        info = R.resolve_request(rt["code"])
        canon = info.get("canonical")
        if not canon:
            continue
        if info.get("subtype"):
            fam[canon]["subtyped"] += 1
        else:
            fam[canon]["umbrella"].append(rt["code"])
    hit = {k: v for k, v in fam.items() if v["subtyped"] and v["umbrella"]}
    assert list(hit) == ["WF-009"], hit
    assert hit["WF-009"]["umbrella"] == ["REQADV"], hit


def test_the_five_internal_actions_stay_out(client):
    """**البند 11**: الخمسة المذكورة محجوبة — يُثبَّت لا يُعاد إصلاحه."""
    named = ("ADMEMP", "ADMLIC", "ADMMISS", "ADMSIGN", "ADMTASK")
    for code in named:
        assert R.LEGACY_REQUEST_ALIASES.get(code, {}).get("internal_action"), (
            f"{code} لم يعد موسوًما إجراًء داخلًيا"
        )
    codes = _catalog(client, HR)
    assert not (set(named) & set(codes)), set(named) & set(codes)


def test_the_remaining_adm_codes_are_real_requests():
    """**وما ظهر منها ليس عطًلا**: أربعة لها سلاسل اعتماد ومسارات.

    إصدار إنذار وتسجيل مخالفة وخصم وتعديل راتب فعلي — قرارات تمرّ
    باعتماد، لا أفعال تُنفَّذ من شاشة. وحجبها إزالة ميزة.
    """
    by_code = {rt["code"]: rt for rt in workflow.DEFAULT_REQUEST_TYPES}
    for code in ("ADMACTUAL", "ADMDED", "ADMVIO", "ADMWARN"):
        rt = by_code[code]
        assert len(rt.get("approval_chain_json") or []) >= 2, code
        assert R.resolve_request(code).get("canonical"), code


def test_the_signature_request_belongs_to_its_module(client):
    """**البند 16**: تغيير التوقيع من وحدته وحدها، والرسالة تدلّ عليها."""
    owned = module_owned.owning_module("REQSIG")
    assert owned and owned["module"] == "signatures", owned
    assert owned.get("where"), "الرفض بلا دلالة على المكان الصحيح"
    assert "REQSIG" not in _catalog(client, HR)
    assert "REQSIG" not in _catalog(client, EMP)


def test_the_catalogue_only_offers_what_submit_accepts(client):
    """**والقاعدة الجامعة**: ما يُعرَض يُقبَل.

    كتالوج يعرض نوًعا يرفضه الخادم يُعلّم المستخدم أن الشاشة تكذب. وهذا
    يقيس العينة الحسّاسة: كل ما حُجب لسبب، والمعروض يبقى معروًضا.
    """
    codes = set(_catalog(client, EMP))
    for hidden in ("REQSIG", "REQADV"):
        assert hidden not in codes
    # ولا يُفرَغ الكتالوج: التنظيف ليس حجًبا شامًلا.
    assert len(codes) > 15, len(codes)
