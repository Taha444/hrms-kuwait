# -*- coding: utf-8 -*-
"""فحٌص يتجاوز مهلَة المنصّة يُبلِّغ أن النظام ساقٌط وهو قائم.

**القياس على الإنتاج**: ``/api/health/deep`` ردَّ **502** («Application
failed to respond») في أول نداء، ثم ردَّ **200 في 15.8 ثانية** في الثاني.
وكلُّ فحوصه ``ok`` و``alembic.up_to_date: true`` — أي أن النظاَم **سليم**
والفحَص هو من يكذب عليه.

**والسبُب مكتوٌب في شرح الشيفرة نفسها**: ``find_seed_accounts`` تكلفتُه
مقصودة — PBKDF2 بمئتين وأربعين ألف دورة، ``~0.6`` ثانية **لكل مستخدم**
عبر كل كلمات البذرة، إذ ال سبيَل لمعرفة أن كلمًة تفتح حساًبا إال بتجريبها.
وشرُحه يقول ذلك ويضيّقه **عند الإقلاع** بحدّين::

    hits = find_seed_accounts(db, privileged_only=True,
                              max_users=BOOT_SCAN_LIMIT)

بعلٍّة صريحة: «الفحص نفسه يصير سبب انهيار الإقلاع بمهلة المنصّة».

**وكان نداُء الفحص بال تضييق**: قيس 6.7 ثانية على عشرين مستخدًما محلًّيا،
و15.8 على الإنتاج. وعلى قاعدٍة بخمسمئة موظف **خمُس دقائق** — فيصير
المساُر الذي بُني للتحقّق بعد كل نشرة هو ما يُظهر النظاَم معطًّلا. قاعدٌة
في موضعين: أحدهما مضيٌَّق بعلّته، واآلخر — األكثُر نداًء — بال تضييق.

فنُقل القراُر المكتوب في الإقلاع كما هو (نفُس الحدّين، من موضعهما ال نسخًة
ثالثة)، وأُضيفت ذاكرٌة عمرُها خمُس دقائق.

**وفائدٌة ثانية لم تكن مقصودة**: المساُر **غيُر مصادَق** (الحالُة مكشوفة
والتفصيُل محروس). فكان تكراُر استفساٍر يُجري تجزئًة ثقيلة استنزاًفا
رخيًصا للخادم. والذاكرُة تحدّه إلى مسٍح واحد كلَّ خمس دقائق.
"""
from __future__ import annotations

import inspect
import time


def test_the_health_scan_uses_the_same_narrowing_as_boot():
    """**القراُر من موضعه ال نسخٌة ثالثة منه.**

    فالإقلاُع ضيّق بحدّين بعلٍّة مكتوبة، والفحُص يقرأ الحدّين نفسهما.
    """
    import app.main as M
    from app import seed_guard

    boot = inspect.getsource(seed_guard.guard_or_raise) \
        if hasattr(seed_guard, "guard_or_raise") else inspect.getsource(seed_guard)
    assert "privileged_only=True" in boot and "BOOT_SCAN_LIMIT" in boot, \
        "افتراُض القياس: الإقلاُع يضيّق بحدّين"

    src = inspect.getsource(M._cached_seed_scan)
    assert "privileged_only=True" in src, "الفحُص ما زال يمسح بال تضييق"
    assert "seed_guard.BOOT_SCAN_LIMIT" in src, "حٌدّ مكتوٌب بالي;د ال من موضعه"


def test_the_endpoint_no_longer_scans_on_every_call():
    """**ونداٌء ثاٍن ال يُعيد تجزئًة ثقيلة** — وإال لم تنفع الذاكرة."""
    import app.main as M

    src = inspect.getsource(M.health_deep)
    assert "_cached_seed_scan()" in src, "الفحُص ينادي المسَح مباشرًة"
    assert "seed_guard.find_seed_accounts(_db)" not in src, \
        "ما زال يمسح بال تضييٍق وال ذاكرة"


def test_the_second_call_is_fast(client):
    """ويُقاس األثر ال الشكل: النداُء الثاني أسرُع بكثير من األول."""
    client.get("/api/health/deep")          # يُسخِّن الذاكرة
    t0 = time.monotonic()
    r = client.get("/api/health/deep")
    dt = time.monotonic() - t0
    assert r.status_code in (200, 503), r.status_code   # 503 = degraded محلًّيا
    assert dt < 2.0, f"النداُء الثاني استغرق {dt:.2f}s — الذاكرُة ال تعمل"


def test_the_cache_has_an_age():
    """**وذاكرٌة بال عمٍر تُخفي تلوًثا جديًدا.**

    فمن يُعيد كلمَة بذرٍة بعد الإقلاع يجب أن يُرى — ولذلك ذاكرٌة بعمٍر ال
    «حكُم الإقلاع» يبقى صادًقا إلى األبد.
    """
    import app.main as M

    assert 0 < M._SEED_SCAN_TTL_SECONDS <= 900, M._SEED_SCAN_TTL_SECONDS


def test_the_full_scan_still_exists_where_a_human_waits():
    """**والتضييُق ال يُلغي المسَح الشامل** — ينقله إلى من ينتظره.

    ``remediate_seed_accounts`` يمسح بال حٍّد ويعالج الكلّ، ويُشغّله إنسان.
    """
    from app import remediate_seed_accounts as R

    src = inspect.getsource(R)
    assert "find_seed_accounts(db, progress=True)" in src, \
        "ذهب المسُح الشامل من موضعه الذي ينتظره إنسان"


def test_the_health_answer_never_carries_a_password():
    """وال يُفصح الجواُب عن كلمٍة وال اسٍم — الرقُم المدني والدوُر يكفيان."""
    import app.main as M

    src = inspect.getsource(M.health_deep)
    block = src[src.index('"seed_accounts"'):]
    block = block[:800]
    assert '"civil_id"' in block and '"role"' in block
    for bad in ("password", "full_name", "password_hash"):
        assert bad not in block, bad
