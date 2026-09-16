# -*- coding: utf-8 -*-
"""أثٌر ماليٌّ يُكتب في شهٍر أُقفل — يُعلَن واقًعا ولا يقع.

**القاعدة مكتوبٌة في ``workflow``** على الخصم المفرد: «الرواتب تقرأ
الخصومات بتاريخها داخل حدود الشهر، فصفٌّ يُكتب في شهر اكتمل مسيّره **لا
يقرؤه أحد أبًدا**». وعلى جدول القرض: «قسٌط يُكتب هناك لا يقرؤه أحد، فيبقى
الدين قائًما والجدول يقول إنه يُسدَّد».

**والبدُل وحده كان بلا فحص.** فبدٌل لمرٍّة واحدة نافٌذ في شهٍر مسيُّره
``approved``/``finalized``/``locked`` يُسجَّل، والطلُب يُغلَق «مكتمًلا» ورسالتُه
«بدٌل لمرٍّة واحدة X في YYYY-MM» — **ولا يُصرَف منه فلس**. والمتكّرُر يفقد
شهوَره المقفلة بصمت.

**ولا يُمسّ حساُب الراتب**: الفحُص يردّ الطلَب إلى ``apply_failed`` بسببه قبل
الكتابة، كما يفعل إخوته — والمسيُّر يقرأ ما كان يقرؤه.

**والحارُس يقيس الثلاثة معًا** — فقاعدٌة مكتوبٌة في موضعين وغائبٌة عن الثالث
هي الصنُف الذي جاء هذا الملفُّ لأجله.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models, workflow as W
from app.database import SessionLocal

_MONTH = "2031-02"


@pytest.fixture
def closed_month():
    """شهٌر مسيُّره ``finalized`` — ويُزال بعد الاختبار."""
    db = SessionLocal()
    run_id = None
    try:
        emp = db.scalar(select(models.Employee).where(models.Employee.company_id == 1))
        assert emp is not None
        run = models.PayrollRun(company_id=1, period=_MONTH, status="finalized")
        db.add(run)
        db.commit()
        run_id = run.id
        yield db, emp
    finally:
        db.rollback()
        if run_id:
            db.execute(sa_delete(models.PayrollRun).where(models.PayrollRun.id == run_id))
            db.commit()
        db.close()


def _req(db, emp, code: str, payload: dict, track: list) -> models.Request:
    req = models.Request(company_id=1, employee_id=emp.id, request_type_code=code,
                         status="approved", payload_json=payload)
    db.add(req)
    db.flush()
    track.append(req.id)
    return req


def test_an_allowance_does_not_start_in_a_closed_month(closed_month):
    """**جوهُر البند**: لا صفَّ بدٍل في شهٍر أُقفل — والسبُب مكتوٌب في الردّ."""
    db, emp = closed_month
    track: list[int] = []
    try:
        req = _req(db, emp, "REQALLOW", {
            "amount": 25, "effective_from": f"{_MONTH}-01",
            "allowance_type": "transport", "is_recurring": False}, track)
        ok, msg = W._apply_allowance(db, req)
        assert ok is False, msg
        assert _MONTH in msg and "أُقفل" in msg, msg
        assert db.scalar(select(models.Allowance).where(
            models.Allowance.request_id == req.id)) is None, \
            "سُجِّل بدٌل في شهٍر أُقفل — يُعلَن ولا يُصرَف"
    finally:
        for rid in track:
            db.execute(sa_delete(models.Allowance).where(models.Allowance.request_id == rid))
            db.execute(sa_delete(models.Request).where(models.Request.id == rid))
        db.commit()


def test_an_allowance_in_an_open_month_is_still_recorded(closed_month):
    """والمفتوُح يُكتب كما كان — التضييُق لا يمنع ما كان يعمل."""
    db, emp = closed_month
    track: list[int] = []
    try:
        req = _req(db, emp, "REQALLOW", {
            "amount": 25, "effective_from": "2031-03-01",
            "allowance_type": "transport", "is_recurring": False}, track)
        ok, msg = W._apply_allowance(db, req)
        assert ok is True, msg
        assert db.scalar(select(models.Allowance).where(
            models.Allowance.request_id == req.id)) is not None
    finally:
        for rid in track:
            db.execute(sa_delete(models.Allowance).where(models.Allowance.request_id == rid))
            db.execute(sa_delete(models.Request).where(models.Request.id == rid))
        db.commit()


def test_the_three_money_writers_guard_the_same_months():
    """**قاعدٌة واحدٌة في ثلاثة مواضع** — تُقاس معًا، فلا يغيب ثالٌث مرًة أخرى.

    وهو من الحرّاس التي تقرأ النصَّ بحقّ: المقيُس **حضوُر** الشرط نفسه في كل
    كاتٍب لأثٍر مالّي — والأثُر السلوكي للبدل مقيٌس أعلاه.
    """
    import inspect

    guard = '("approved", "finalized", "locked")'
    writers = [name for name in dir(W)
               if name.startswith("_apply_") and callable(getattr(W, name))
               and ("models.Deduction(" in inspect.getsource(getattr(W, name))
                    or "models.Allowance(" in inspect.getsource(getattr(W, name)))]
    assert len(writers) >= 3, f"القياُس يرى {writers} فقط — صار أعمى"
    unguarded = [w for w in writers if guard not in inspect.getsource(getattr(W, w))]
    assert not unguarded, f"كاتبو أثٍر ماليٍّ بلا فحص الشهر المقفل: {unguarded}"
