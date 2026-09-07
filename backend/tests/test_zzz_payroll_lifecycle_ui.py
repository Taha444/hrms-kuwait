# -*- coding: utf-8 -*-
"""دورة مسيّر الرواتب: للخادم دورٌة كاملة، وللشاشة زٌر واحد.

**العطل المقيس**: الخادم يفرض ``prepared → approved → finalized →
locked`` ويمنع كل قفزة. وشاشة الرواتب كان فيها زرّان: «معاينة»
و«تشغيل وحفظ». **ولا زرّ واحد يتقدّم بالمسيّر خطوة بعدها.**

فكل مسيّر يُجهَّز ويبقى ``prepared`` إلى الأبد: لا يُعتمَد، ولا يُقفَل،
ولا يُقفل نهائًيا، ولا تُبنى عليه تسوية. **وهي عملية الشهر الأساسية عند
العميل** — أي أن أكبر ما يفعله النظام لم يكن قابًلا للإتمام منه.

وثلاثة عيوب صغيرة تحته:

- **كل الحالات بلون النجاح**: يستوي في الجدول مسيٌّر لم يعتمده أحد
  ومسيٌّر مقفل صُرف — واللون أول ما يُقرأ.
- **الحالات بلا تسمية**: ``prepared`` و``finalized`` ليستا في خريطة
  التسميات، والدالة تُعيد المفتاح كما هو، فيظهر الكود وكأنه تسمية.
- **صفٌّ بلا زرّ ولا سبب**: من جهّز المسيّر لا يعتمده (فصل السلطات)،
  وكانت الشاشة تتركه أمام صفّ صامت.

**والأعلام تأتي من الخادم**: شرط المنع مكتوب مرّة، فلا يظهر زٌر يفشل
بـ403 — وهو ما يقيسه ``test_the_flags_agree_with_what_the_server_enforces``.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, purge

ACCOUNTANT = ("100000000007", "account123")
PAGE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "Payroll.tsx"
LABELS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "labels.ts"

#: فترة قديمة لا تتقاطع مع مسيّرات اختبارات أخرى.
PERIOD = "2019-04"


@pytest.fixture
def run_row(client):
    """مسيٌّر مجهَّز على فترة خاصّة بهذا الملف — ويُزال بعده."""
    hdr = auth_headers(login(client, *ACCOUNTANT))
    r = client.post(f"/api/payroll/run?period={PERIOD}&allow_open_attendance=true",
                    headers=hdr)
    assert r.status_code == 200, r.text
    rid = r.json()["run_id"]
    yield hdr, rid

    db = SessionLocal()
    try:
        db.execute(sa_delete(models.PayrollRun).where(
            models.PayrollRun.adjustment_of_run_id == rid))
        db.execute(sa_delete(models.PayrollRun).where(models.PayrollRun.id == rid))
        db.commit()
    finally:
        db.close()


def _row(client, hdr, rid) -> dict:
    rows = client.get("/api/payroll/runs", headers=hdr).json()
    return next(x for x in rows if x["id"] == rid)


# ---------------------------------------------------------------------------
# الشاشة
# ---------------------------------------------------------------------------

def test_the_screen_can_advance_the_run_through_its_whole_cycle():
    """**جوهر العطل**: دورٌة كاملة على الخادم بلا مخرج من الشاشة."""
    page = PAGE.read_text(encoding="utf-8")
    for step in ("approve", "finalize", "lock", "reopen", "adjustment"):
        assert re.search(rf'["\'`]{step}["\'`]', page), f"لا طريق إلى {step}"


def test_each_state_has_its_own_colour_and_its_own_name():
    """ولا يستوي المجهَّز والمقفل: لوٌن لكلٍّ، واسٌم عربي لكلٍّ."""
    page = PAGE.read_text(encoding="utf-8")
    assert "RUN_PILL" in page, "كل الحالات ما زالت بلون واحد"
    assert 'pill success' not in page.replace('RUN_PILL', ''), (
        "ما زال هناك لون نجاح ثابت في جدول المسيّرات"
    )
    labels = LABELS.read_text(encoding="utf-8")
    for code in ("prepared", "finalized", "adjustment_run"):
        assert f"{code}:" in labels, f"الحالة «{code}» تُعرض بكودها الخام"


# ---------------------------------------------------------------------------
# الخادم: الأعلام تطابق ما يفرضه فعًلا
# ---------------------------------------------------------------------------

def test_the_flags_agree_with_what_the_server_enforces(client, run_row):
    """**زٌر يظهر ثم يفشل بـ403 أسوأ من زرّ غائب.**

    من جهّز المسيّر لا يعتمده. فالعلَم عنده ``false``، والسبب مسمًّى —
    والاثنان من نفس الشرط الذي يفرضه المنع لا من نسخة ثانية منه.
    """
    hdr, rid = run_row
    row = _row(client, hdr, rid)
    assert row["status"] == "prepared"
    assert row["can_approve"] is False, "الشاشة ستعرض زًرا يفشل"
    assert row["blocked_reason"] and "جهّزته" in row["blocked_reason"], row

    refused = client.post(f"/api/payroll/runs/{rid}/approve", headers=hdr)
    assert refused.status_code == 403
    assert refused.json()["detail"] == row["blocked_reason"], (
        "رسالتان لقاعدة واحدة — تنحرفان"
    )


def test_the_row_says_who_prepared_it(client, run_row):
    """وفصل السلطات لا يُثبَت بغير أسماء: من جهّز ومن اعتمد."""
    hdr, rid = run_row
    row = _row(client, hdr, rid)
    assert row["prepared_by"], "المسيّر بلا اسم من جهّزه"
    assert row["approved_by"] is None


def test_a_second_holder_sees_the_button_and_the_cycle_completes(client, run_row):
    """**والدورة تُقطع من الشاشة**: اعتماد ← إقفال ← قفل ← تسوية."""
    hdr, rid = run_row

    db = SessionLocal()
    try:
        # محاسٌب ثانٍ في الشركة نفسها — بلا حساب ثانٍ لا يكتمل الفصل.
        first = db.scalar(select(models.User).where(
            models.User.civil_id == ACCOUNTANT[0]))
        second = models.User(
            civil_id="288800110088", full_name="محاسب ثانٍ للقياس",
            role="accountant", company_id=first.company_id, is_active=True,
            must_change_password=False,
            password_hash=first.password_hash)
        db.add(second)
        db.commit()
        sid = second.id
    finally:
        db.close()

    try:
        hdr2 = auth_headers(login(client, "288800110088", ACCOUNTANT[1]))
        row = _row(client, hdr2, rid)
        assert row["can_approve"] is True and row["blocked_reason"] is None

        assert client.post(f"/api/payroll/runs/{rid}/approve", headers=hdr2).status_code == 200
        assert _row(client, hdr2, rid)["can_finalize"] is True
        assert client.post(f"/api/payroll/runs/{rid}/finalize", headers=hdr2).status_code == 200
        assert _row(client, hdr2, rid)["can_lock"] is True
        assert client.post(f"/api/payroll/runs/{rid}/lock", headers=hdr2).status_code == 200

        locked = _row(client, hdr2, rid)
        assert locked["status"] == "locked"
        assert locked["can_adjust"] is True, "لا مخرج بعد القفل"
        assert locked["approved_by"], "المقفل بلا اسم من اعتمده"

        adj = client.post(f"/api/payroll/runs/{rid}/adjustment?reason=فرق بدل نقل",
                          headers=hdr2)
        assert adj.status_code == 200, adj.text
    finally:
        db = SessionLocal()
        try:
            # ``purge`` يحذف ما يشير إليه بترتيب مشتقّ من المخطّط — والمسيّر
            # يحمل اسم من اعتمده وقفله، فحذف الحساب وحده يسقط بقيد أجنبي.
            purge(db, "users", [sid])
            db.commit()
        finally:
            db.close()


def test_reopening_is_offered_to_nobody_but_the_super_admin(client, run_row):
    """وإعادة الفتح سلطة عليا — والعلَم يتبع من يملكها لا من يراها."""
    hdr, rid = run_row
    assert _row(client, hdr, rid)["can_reopen"] is False
