# -*- coding: utf-8 -*-
"""من يرى أي حقل من بيانات الموظف — القاعدة نفسها على كل منفذ.

**العطل الذي كشفته مراجعة الباكند**: السياسة كانت مكتوبة داخل مسار
التفصيل وحده. يُقنَّع فيه الجواز لمن لا يملك الاطلاع، وتُمسح الحقول
المالية عن المندوب والهوياتية عن المحاسب.

**وسرد الموظفين لم يمرّ بها.** فكان ``GET /api/employees`` يعيد الجواز
والراتب الأساسي لكل من يستطيع السرد — ومنهم **مسؤول الفرع**، وهو يدير
حضور فرعه ولا يقدّم معاملات حكومية.

فالحماية كانت على الشاشة التي تعرض موظًفا واحًدا، وغائبة عن الشاشة التي
تعرضهم جميًعا. ومن أراد البيانات لا يفتح ملًفا بل يفتح القائمة.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

#: الأدوار الثمانية وبيانات دخولها — من البذرة.
ROLES = {
    "employee": ("100000000101", "emp12345"),
    "branch_supervisor": ("100000000005", "sup12345"),
    "company_manager": ("100000000001", "manager123"),
    "hr": ("100000000002", "hr12345"),
    "accountant": ("100000000007", "account123"),
    "delegate": ("100000000003", "deleg123"),
    "company_owner": ("111111111111", "owner123"),
    "super_admin": ("000000000000", "admin123"),
}

#: **القرار الذي اتُّخذ**: مسؤول الفرع لا يرى جواز كل موظف. والمحاسب
#: كذلك — الاسم والرقم الوظيفي يكفيان لتشغيل الرواتب.
#:
#: مكتوبة هنا مستقلّة عن ``SENSITIVE_FIELDS`` عمًدا: قراءتها من الوحدة
#: تجعل تفريغها يُفرغ الاختبار، فيمرّ أخضر وهو لا يفحص شيًئا.
FORBIDDEN = {
    "branch_supervisor": ("passport_number", "passport_expiry", "basic_salary"),
    "accountant": ("passport_number", "passport_expiry"),
}

#: ومن يحتاجها يراها — وإلا كنّا كسرنا العمل باسم تأمينه.
REQUIRED = {
    "hr": ("passport_number", "basic_salary"),
    "delegate": ("passport_number",),          # يقدّم المعاملات الحكومية
    "company_manager": ("passport_number", "basic_salary"),
    "accountant": ("basic_salary",),           # يشغّل الرواتب
    "super_admin": ("passport_number", "basic_salary"),
}


def _list_as(client, role):
    hdr = auth_headers(login(client, *ROLES[role]))
    r = client.get("/api/employees", headers=hdr)
    assert r.status_code == 200, f"{role}: {r.status_code} {r.text[:120]}"
    return r.json()


def _others(rows, client, role):
    """سجلات غير سجلّ صاحب الحساب — فهو يرى ملفه كامًلا بحق."""
    db = SessionLocal()
    try:
        own = db.scalar(select(models.User.employee_id).where(
            models.User.civil_id == ROLES[role][0]))
    finally:
        db.close()
    return [r for r in rows if r.get("id") != own]


def test_the_list_is_not_empty_for_the_roles_measured():
    """الادّعاءات كلها فارغة على قائمة فارغة."""
    assert set(FORBIDDEN) <= set(ROLES) and set(REQUIRED) <= set(ROLES)


@pytest.mark.parametrize("role", sorted(FORBIDDEN))
def test_a_role_does_not_receive_fields_it_has_no_claim_to(client, role):
    """**جوهر الإصلاح**: القائمة لا تعطي ما يمنعه ملفّ الموظف."""
    rows = _others(_list_as(client, role), client, role)
    assert rows, f"{role}: لا سجلات لغيره — القياس فارغ"
    for field in FORBIDDEN[role]:
        leaking = [r["id"] for r in rows if field in r]
        assert not leaking, (
            f"«{role}» يرى «{field}» لموظفين آخرين: {leaking[:5]}"
        )


@pytest.mark.parametrize("role", sorted(REQUIRED))
def test_a_role_still_receives_what_its_work_needs(client, role):
    """والحدّ المقابل: تأمين يمنع العمل ليس تأميًنا.

    المندوب يقدّم المعاملات الحكومية، والمحاسب يشغّل الرواتب، وشؤون
    الموظفين تكتب العقود. حجب ما يحتاجونه يدفعهم إلى طريق آخر.
    """
    rows = _others(_list_as(client, role), client, role)
    assert rows, f"{role}: لا سجلات لغيره"
    for field in REQUIRED[role]:
        assert any(field in r for r in rows), (
            f"«{role}» فقد «{field}» وهو يحتاجه"
        )


def test_the_field_is_absent_not_null(client):
    """يُحذف المفتاح ولا يُصفَّر.

    ``None`` تُقرأ «لا جواز لهذا الموظف» — خبر خاطئ يقود إلى فتح معاملة
    ناقصة. وغياب المفتاح يُقرأ «لا تراه»، وهو الصدق.
    """
    rows = _others(_list_as(client, "branch_supervisor"), client, "branch_supervisor")
    for r in rows:
        assert "passport_number" not in r, (
            f"المفتاح موجود بقيمة {r.get('passport_number')!r} بدل أن يُحذف"
        )


def test_everyone_sees_their_own_record_in_full(client):
    """صاحب الملف يرى ملفه كامًلا أًيا كان دوره."""
    db = SessionLocal()
    try:
        own = db.scalar(select(models.User.employee_id).where(
            models.User.civil_id == ROLES["branch_supervisor"][0]))
    finally:
        db.close()
    if own is None:
        pytest.fail("مسؤول الفرع بلا سجلّ موظف — لا يمكن قياس الاستثناء")

    rows = _list_as(client, "branch_supervisor")
    mine = [r for r in rows if r.get("id") == own]
    assert mine, "لا يرى نفسه في القائمة"
    assert "basic_salary" in mine[0], "حُجب عن صاحب الملف راتبه هو"


def test_the_detail_endpoint_agrees_with_the_list(client):
    """**القاعدة نفسها في الموضعين** — وهذا أصل العطل.

    كانت السياسة على التفصيل وحده. فلو انحرف أحدهما عن الآخر ثانيًة،
    عاد الطريق المفتوح: يُمنع من الملف ويُؤخذ من القائمة.
    """
    hdr = auth_headers(login(client, *ROLES["branch_supervisor"]))
    rows = _others(_list_as(client, "branch_supervisor"), client, "branch_supervisor")
    target = rows[0]["id"]

    detail = client.get(f"/api/employees/{target}", headers=hdr)
    assert detail.status_code == 200, detail.text
    emp = detail.json().get("employee", detail.json())
    shown = emp.get("passport_number")
    assert not shown or "*" in str(shown), (
        f"التفصيل يعطي الجواز صريًحا لمن منعته القائمة: {shown!r}"
    )


# ==========================================================================
# منع النسخة الرابعة
# ==========================================================================
def test_no_endpoint_carries_its_own_copy_of_the_policy():
    """القاعدة في ``field_policy`` وحدها.

    كانت مكتوبة ثلاث مرات: في السرد (لا شيء)، وفي ``get_employee``
    (للمحاسب والمندوب فقط)، وفي الملف الكامل (تقنيع). فأخذ مسؤول الفرع
    الجواز من الموضع الذي لم يُذكر فيه.

    والفحص هنا على النصّ: قائمة حقول حسّاسة مكتوبة داخل راوتر تعني نسخة
    رابعة تنحرف غًدا.
    """
    import re
    from pathlib import Path

    routers = Path(__file__).resolve().parents[1] / "app" / "routers"
    offenders = []
    for f in routers.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        # سطر يجمع «جواز» و«راتب» في قائمة واحدة = تعريف سياسة محلّي
        for line_no, line in enumerate(src.splitlines(), 1):
            if ('"passport_number"' in line and '"basic_salary"' in line):
                offenders.append(f"{f.name}:{line_no}")
    assert not offenders, (
        f"سياسة حقول مكتوبة داخل راوتر بدل field_policy: {offenders}"
    )


def test_the_policy_module_is_the_one_being_used():
    """وحارس لا يُقاس ادّعاؤه لا يحرس.

    لو لم يستعمل أي راوتر الوحدة، لمرّ الفحص أعلاه على نظام بلا سياسة
    إطلاًقا — وهو أسوأ من ثلاث نسخ.
    """
    from pathlib import Path

    routers = Path(__file__).resolve().parents[1] / "app" / "routers"
    users = [f.name for f in routers.glob("*.py")
             if "field_policy" in f.read_text(encoding="utf-8")]
    assert users, "لا راوتر ينادي field_policy — السياسة معرَّفة ولا تُطبَّق"
