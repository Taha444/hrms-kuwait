# -*- coding: utf-8 -*-
"""مطابقة الأسماء العربية — الصورة المجرَّدة لا الحروف كما كُتبت.

**العطل المقيس على الإنتاج**: بحثت الأداة عن «النيل الأزرق» في موقع
يكتبها «النيل الازرق»، فقالت **«لا شركة بهذا الاسم — أنشئها أوًلا»**
والشركة قائمة على الشاشة أمام المستخدم.

والفارق حرٌف واحد: ``أ`` (0x623) مقابل ``ا`` (0x627). ومستندات الشركة
الرسمية نفسها تكتب اسمها ثلاث صور — «شركة النيل الأزرق» و«شركه النيل
الازرق» و«شركة النيل الازرق». فالمطابقة الحرفية ترى ثلاثة أسماء حيث
يرى القارئ اسًما واحًدا.

**وهذا عيب مطابقة لا عيب بيانات**: الجهات الرسمية الكويتية لا تلتزم
صورًة واحدة، فمن يطابق حرًفا بحرف يخطئ دائًما لا أحيانًا.
"""
from __future__ import annotations

from app.arabic import contains_ar, normalize_ar, same_ar

SITE = "شركة النيل الازرق للمجوهرات"        # كما على الموقع — بلا همزة
DOCS = "شركة النيل الأزرق للمجوهرات"        # كما في ملف البيانات
ALT = "شركه النيل الازرق للمجوهرات"         # كما في ترخيص الاستيراد


def test_the_three_spellings_are_one_name():
    """**جوهر العطل**: ثلاث صور لاسم واحد في مستندات الشركة نفسها."""
    assert same_ar(SITE, DOCS) and same_ar(SITE, ALT), (
        normalize_ar(SITE), normalize_ar(DOCS), normalize_ar(ALT))


def test_the_search_that_failed_now_finds_it():
    """والبحث الذي ردّ «أنشئ الشركة» وهي قائمة."""
    assert contains_ar(SITE, "النيل الأزرق")
    assert contains_ar(DOCS, "النيل الازرق")


def test_it_does_not_swallow_a_different_company():
    """**ولا يُصلَح التشدّد بتساهل**: شركٌة أخرى تبقى أخرى.

    وعلى الموقع نفسه «شركة قمة النيل الخالد» — فمطابقٌة فضفاضة تخلط
    مستندات شركة بشركة، وهو أسوأ من ألّا تجد.
    """
    assert not contains_ar("شركة قمة النيل الخالد للتجارة", "النيل الأزرق")
    assert not same_ar("شركة ميلانو المتحدة للأقمشة", SITE)


def test_the_ornaments_do_not_make_a_new_name():
    """التشكيل والتطويل والفراغات الزائدة: زينٌة لا تميّز اسًما عن اسم."""
    assert same_ar("شركـة  النيل   الأزرق للمجوهرات", SITE)
    assert same_ar("شَرِكَة النيل الأزرق للمجوهرات", SITE)


def test_nothing_matches_an_empty_needle():
    """**وفراٌغ لا يطابق كل شيء**: وإلا لأخذت الأداة أول شركة تجدها."""
    assert not contains_ar(SITE, "")
    assert not contains_ar(SITE, None)
    assert not same_ar("", "")


def test_the_importer_matches_through_it_in_both_modes():
    """والوضعان يقرآن من الدالّة نفسها — لا نسخٌة في كلٍّ تنحرف."""
    import inspect

    import app.import_company_package as M

    assert "contains_ar" in inspect.getsource(M._company)
    assert "contains_ar" in inspect.getsource(M.run_api)


def test_the_stored_name_is_never_rewritten():
    """**ولا يُمسّ المخزون**: الاسم يُحفظ كما كتبه صاحبه.

    والتجريد للمقارنة وحدها — تغيير المحفوظ يُفسد ما يُطبع على المستندات
    الرسمية، وهي تُقدَّم لجهات تقرأ الاسم حرًفا بحرف.
    """
    import inspect

    import app.arabic as A

    src = inspect.getsource(A)
    assert "db.commit" not in src and "setattr" not in src, (
        "وحدة المطابقة تكتب — وهي للقراءة"
    )
