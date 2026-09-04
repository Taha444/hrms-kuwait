# -*- coding: utf-8 -*-
"""P3-13 / P3-14 — كتالوج الموظف من السجلّ القانوني وحده.

**العطل**: ``salary_certificate`` موسوم في السجلّ «Alias retired —
استخدم OD-001»، ومع ذلك كان يظهر للموظف بجانب ``REQCERTSAL`` بالاسم
نفسه: «طلب شهادة راتب» **مرّتين** في قائمة واحدة.

فيقف الموظف أمام خيارين لا فرق بينهما في الاسم ولا في الشرح. وأيّهما
اختار، فالنصف الآخر بقيّة ميّتة تستقبل طلبات لا يعرف أحد لماذا وصلت
مسارًا قديًما.

**والقاعدة تُشتقّ من السجلّ** لا تُكتب استثناًء بكود بعينه: alias
يُتقاعد غًدا يختفي يوم يُوسَم، لا يوم يتذكّره أحد.
"""
from __future__ import annotations

from collections import Counter

from app import v15_registry as R
from tests.conftest import auth_headers, login

EMPLOYEE = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")


def _catalog(client, creds):
    hdr = auth_headers(login(client, *creds))
    r = client.get("/api/requests/types", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def test_the_registry_still_marks_a_retired_alias():
    """الادّعاء فارغ لو لم يعد في السجلّ alias متقاعد."""
    retired = [c for c, e in R.LEGACY_REQUEST_ALIASES.items()
               if isinstance(e, dict) and "retired" in str(e.get("note", "")).lower()]
    assert retired, "لا aliases متقاعدة — راجع الفحص لا الشيفرة"


def test_no_retired_alias_reaches_the_employee_catalogue(client):
    """**جوهر البند**: المتقاعد لا يُعرض على الموظف."""
    retired = {c for c, e in R.LEGACY_REQUEST_ALIASES.items()
               if isinstance(e, dict) and "retired" in str(e.get("note", "")).lower()}
    codes = {t.get("code") for t in _catalog(client, EMPLOYEE)}
    leaked = retired & codes
    assert not leaked, f"aliases متقاعدة في كتالوج الموظف: {leaked}"


def test_no_duplicate_names_in_the_employee_catalogue(client):
    """ولا اسمان متطابقان: خياران لا فرق بينهما ليسا خيارًا."""
    names = Counter((t.get("name") or "").strip()
                    for t in _catalog(client, EMPLOYEE))
    dups = {n: c for n, c in names.items() if c > 1 and n}
    assert not dups, f"أسماء مكرّرة في كتالوج الموظف: {dups}"


def test_the_canonical_replacement_is_still_offered(client):
    """والبديل باقٍ — وإلا كنّا حذفنا الميزة لا نظّفناها."""
    codes = {t.get("code") for t in _catalog(client, EMPLOYEE)}
    assert "REQCERTSAL" in codes, (
        "اختفى النوع القانوني لشهادة الراتب مع المتقاعد"
    )


def test_internal_actions_are_not_offered_as_requests(client):
    """P3-14 — الإجراءات الداخلية ليست طلبات يقدّمها موظف."""
    internal = {c for c, e in R.LEGACY_REQUEST_ALIASES.items()
                if isinstance(e, dict) and e.get("internal_action")}
    assert internal, "لا إجراءات داخلية معرَّفة — راجع الفحص"
    codes = {t.get("code") for t in _catalog(client, EMPLOYEE)}
    leaked = internal & codes
    assert not leaked, f"إجراءات داخلية معروضة كطلبات: {leaked}"


def test_the_catalogue_is_not_empty_for_the_employee(client):
    """وكل ما سبق فارغ على قائمة فارغة."""
    catalog = _catalog(client, EMPLOYEE)
    assert len(catalog) >= 10, f"كتالوج الموظف صغير بشكل مريب: {len(catalog)}"


def test_hr_still_sees_more_than_the_employee(client):
    """والتنظيف لم يمسّ من يرى الكتالوج كامًلا."""
    emp = {t.get("code") for t in _catalog(client, EMPLOYEE)}
    hr = {t.get("code") for t in _catalog(client, HR)}
    assert len(hr) > len(emp), (
        f"شؤون الموظفين لا ترى أكثر من الموظف: {len(hr)} مقابل {len(emp)}"
    )
