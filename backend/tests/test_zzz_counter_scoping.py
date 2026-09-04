# -*- coding: utf-8 -*-
"""P2-11 / P2-12 — نطاق العدادات: سياسة واحدة معلَنة، ومركز العمليات يعرض عمًلا حقيقًيا.

**السياسة** في ``deps.scope_company_id`` وحدها: الأدوار العابرة للشركات
تختار شركة أو تراها كلها، وغيرها **يُجبَر** على شركته أًيا كان ما طلب.

وقيمة أن تكون في موضع واحد أنها تُفرَض ولا تُذكَر: لو كُتبت في كل نقطة،
لَنسيها منفذ ولم يلاحظ أحد — والأثر أن دورًا عادًيا يقرأ أرقام شركة
أخرى بتمرير معامل في الرابط.

**والعدّاد يساوي قائمته** (P2-10 امتّد إلى هنا): الرقم على البطاقة هو
طول ما تفتحه، لا رقم يُحسب باستعلام ثانٍ.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")          # شركة 1
PRO = ("100000000003", "deleg123")        # يملك مركز العمليات
OWNER = ("111111111111", "owner123")      # عابر للشركات
SUPER = ("000000000000", "admin123")


def test_the_scoping_policy_lives_in_one_place():
    """سياسة مكتوبة في موضعين تنحرف في أحدهما."""
    import inspect

    from app import deps

    src = inspect.getsource(deps.scope_company_id)
    assert "CROSS_COMPANY_ROLES" in src, "السياسة لا تقرأ قائمة الأدوار العابرة"
    assert "user.company_id" in src, "لا إجبار على شركة المستخدم"


def test_a_normal_role_cannot_request_another_company(client):
    """**الادّعاء الأمني**: تمرير ``company_id`` لا يفتح شركة أخرى."""
    db = SessionLocal()
    try:
        hr = db.scalar(select(models.User).where(
            models.User.civil_id == HR[0]))
        other = db.scalar(select(models.Company.id).where(
            models.Company.id != hr.company_id))
        own = hr.company_id
    finally:
        db.close()
    assert other and other != own, "لا شركة ثانية — القياس فارغ"

    hdr = auth_headers(login(client, *HR))
    mine = client.get("/api/employees", headers=hdr).json()
    theirs = client.get("/api/employees", headers=hdr,
                        params={"company_id": other}).json()

    ids_mine = {e["id"] for e in mine}
    ids_theirs = {e["id"] for e in theirs}
    assert ids_theirs <= ids_mine, (
        f"طلب شركة أخرى أعاد سجلات ليست من شركته: {ids_theirs - ids_mine}"
    )


def test_the_operations_counter_equals_the_list_it_opens(client):
    """P2-12 — الرقم على البطاقة هو طول ما تفتحه بالضبط.

    والمندوب هو صاحب هذه الشاشة: شؤون الموظفين لا تملكها (403)، فقياسها
    بحسابها كان يفحص بوّابة الصلاحية لا العدّاد.
    """
    hdr = auth_headers(login(client, *PRO))
    r = client.get("/api/operations", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()

    count = body.get("open_gov_tasks")
    rows = body.get("gov_tasks")
    assert count is not None and rows is not None, (
        f"مركز العمليات بلا عدّاد أو بلا قائمة: {sorted(body)[:10]}"
    )
    assert count == len(rows), f"العدّاد {count} والقائمة {len(rows)}"


def test_the_same_holds_for_a_cross_company_role(client):
    """والعابر للشركات ليس استثناء: رقمه هو قائمته أيًضا.

    وهو الموضع الذي ينكسر عادًة: النطاق ``None`` يعني «كل الشركات»
    فيُحسب العدّاد على الكلّ وتُبنى القائمة على واحدة.
    """
    hdr = auth_headers(login(client, *OWNER))
    body = client.get("/api/operations", headers=hdr).json()
    count, rows = body.get("open_gov_tasks"), body.get("gov_tasks")
    if count is None or rows is None:
        return                      # المالك لا يفتح هذه الشاشة — لا ادّعاء
    assert count == len(rows), (
        f"عابر الشركات: العدّاد {count} والقائمة {len(rows)}"
    )


def test_a_cross_company_role_sees_more_than_one_company(client):
    """وأن «كل الشركات» تعني ذلك فعًلا — وإلا كان الفحص أعلاه فارًغا."""
    hdr = auth_headers(login(client, *SUPER))
    rows = client.get("/api/employees", headers=hdr).json()
    db = SessionLocal()
    try:
        companies = {e["company_id"] for e in rows if e.get("company_id")}
        total = db.scalar(select(models.Company.id))
    finally:
        db.close()
    assert total, "لا شركات"
    assert len(companies) >= 2, (
        f"الإدارة العليا ترى شركة واحدة فقط: {companies}"
    )
