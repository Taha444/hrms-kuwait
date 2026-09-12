# -*- coding: utf-8 -*-
"""فهرُس ما تكون فيه بيئُة االختبار أرحَم من اإلنتاج.

**سبعُة فروٍق قيست في جولٍة واحدة، ستٌَّة منها كانت أعطاًال حقيقية.** وما
يجمعها واحد: **السويُت الخضراُء ال تكفي** — ألن البيئَة التي تجري فيها
تُخفي ما يُظهره اإنتاج. فهذا امللُّف فهرُسها، ليُكنَس الصنُف بقصٍد ال
باملصادفة.

================  ==========================================  ============
الفرق             ما أخفاه                                    الحارس
================  ==========================================  ============
أصٌل واحد          ``expose_headers`` ناقصة ⇒ املرقُِّم ال       ``test_zzz_unbounded_lists``
                  يُرسَم (``25 > 25`` كاذب)
ساعُة املضيف       لحظٌة تُكتب بتوقيت املضيف وتُقرأ UTC          ``test_zzz_host_clock``
قاعدٌة تُبذَر       الكتالوُج في القاعدة هو الذي يعمل —           ``test_zzz_catalog_reconcile``
من جديد           35 نوًعا صامًتا
SQLite ال يميّز    ``LIKE`` حسّاٌس للحالة في Postgres ⇒          ``test_zzz_dialect_case``
حالَة الحروف        بحٌث ال يجد
SQLite يتجاهل      قيمٌة أطوُل من عمودها ⇒ 500 في اإنتاج        ``test_zzz_dialect_case``
طوَل العمود
فرٌع إنتاجّي        حاٌرس يقرأ الشيفرَة وال يُجرِّب املحو           ``test_zzz_production_only_branches``
================  ==========================================  ============

**ونتيجتان سالبتان تُقاالن فال يُعاد فحصُهما:**

- ``job_lock``: القفُل صٌّف على مفتاٍح مركّب، و``IntegrityError`` يتبعها
  ``db.rollback()`` فوًرا — **وهو الشرُط الذي يفرّق املحرّكين**: معاملُة
  Postgres تُلغى بعد الخطأ فيفشل كلُّ ما بعدها، وSQLite يسمح باملتابعة.
  فالقفُل سليٌم على االثنين.
- **ال استعالَم داخل أعمدة JSON** — كلُّها تُقرأ كائناٍت في بايثون، فال
  يمسّها فرُق ``JSON``/``JSONB``.
"""
from __future__ import annotations

import pathlib


def test_the_index_names_a_living_guard_for_each_difference():
    """**وفهٌرس يُشير إلى حارٍس ذهب فهٌرس يكذب.**

    فكلُّ سطٍر في الجدول أعاله يسمّي ملَّف حارٍس — ويُقاس أنه قائم.
    """
    tests = pathlib.Path(__file__).resolve().parent
    for name in ("test_zzz_unbounded_lists", "test_zzz_host_clock",
                 "test_zzz_catalog_reconcile", "test_zzz_dialect_case",
                 "test_zzz_production_only_branches"):
        assert (tests / f"{name}.py").exists(), f"ذهب الحارس: {name}"


def test_the_lock_still_rolls_back_after_a_conflict():
    """**والنتيجُة السالبة تُحرَس كما يُحرَس العطل.**

    فلو حُذفت ``db.rollback()`` بعد ``IntegrityError``، صار خاسُر القفل
    يُفسِد معاملَته على Postgres — ويمرّ على SQLite. فتُقاس هنا، وإال
    وجب إعادُة الفحص الذي انتهى إلى «سليم».
    """
    import inspect

    from app import job_lock

    src = inspect.getsource(job_lock)
    i = src.index("except IntegrityError")
    assert "db.rollback()" in src[i:i + 200], src[i:i + 200]


def test_no_query_reaches_inside_a_json_column():
    """**والنتيجُة السالبة الثانية**: ال استعالَم داخل JSON.

    فلو أُضيف غًدا ``payload_json["x"] == y`` صار الفرُق بين ``JSON`` في
    SQLite و``JSONB`` في Postgres بابًا لعطٍل ال يظهر محلًّيا — فيسقط هذا
    الحارس معلًنا أن الفرَق يُدرَس.
    """
    app = pathlib.Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for p in app.rglob("*.py"):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if s.startswith("#"):
                continue
            for pat in ('_json["', "json_extract", ".astext", '_json.op('):
                if pat in s:
                    offenders.append(f"{p.name}:{i}")
    assert not offenders, (
        "استعالٌم داخل عمود JSON — يُدرَس فرُق املحرّكين: " + str(offenders))
