# -*- coding: utf-8 -*-
"""السفُر ثاني لحظٍة يخرج فيها المال — وكانت صامتة.

**القياس**: ``outstanding_loan`` يُستشار في موضٍع واحد — ``exit_case`` عند
نهاية الخدمة. ويقول شرحُه بحرفه: يُرفَع المبلُغ مهمًة حرجة، ومصيرُه «حٌد
قانوني ومسألُة سياسة» ال يُقرَّر في الشيفرة، **«لكنه يُسمّى فيبلغ من يسوّي
الحساب، بدل أن يُكتشَف بعد إغلاق الملف أو ال يُكتشَف أصًلا»**.

**ومغادرُة البالد تنطبق عليها العبارُة بحرفها**: من يسافر وعليه أقساٌط قد ال
يعود، والدُين يصير غيَر قابٍل للتحصيل. ومساُر إجازة السفر يمرّ بالمندوب
لإذن المغادرة — **ولم يكن شيٌء يفحص الدَين هناك**.

**وال يُقرَّر شيء**: الإجازُة ال تُوقَف، وال يُقتطَع فلٌس. يُسمّى المبلُغ لمن
يسوّي الحساب **في اللحظة التي يمكن فيها التسوية**.

**وهذا ليس المستنَد المعلَن**: ``WF-002`` يعلن ``OD-012`` «إفادة مالية
للسفر» — تخطيطُها ``LAY-06`` (أسرُة إخالء الطرف) وحقلُها ``financial_status``
— **وهي وثيقٌة تنتظر قراَر صاحبها**. واإلخطاُر تنبيٌه إلى أن موضَعها له
معنى، ال بديٌل عنها.
"""
from __future__ import annotations

import inspect

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal


def test_the_debt_is_named_before_travel():
    """**جوهر البند**: مبلٌغ يُسمّى في اللحظة التي يمكن فيها تسويتُه."""
    from app import workflow as W

    src = inspect.getsource(W.enter_stage)
    assert "_warn_debt_before_travel" in src, "مرحلُة المندوب ال تفحص الدَين"
    helper = inspect.getsource(W._warn_debt_before_travel)
    assert "outstanding_loan" in helper


def test_it_decides_nothing():
    """**واإلخطاُر ال يوقف إجازًة وال يقتطع فلًسا.**

    فالقطُع حٌد قانوني ومسألُة سياسة — وهو ما تقوله سابقُة ``exit_case``
    بحرفها. وإخطاٌر يمنع سفًرا يجعل من التنبيه عقوبًة لم يُقرَّها أحد.
    """
    from app import workflow as W

    helper = inspect.getsource(W._warn_debt_before_travel)
    for forbidden in ("raise HTTPException", "req.status =", "Deduction(",
                      "EffectAlreadyApplied"):
        assert forbidden not in helper, f"اإلخطاُر يتصرّف: {forbidden}"
    assert "ال تُوقَف" in helper or "لا تُوقَف" in helper


def test_the_precedent_it_follows_is_still_there():
    """**وسابقٌة تُتبَع يُقاس أنها قائمة.**

    فلو تغيّر ``exit_case`` — بأن صار يقتطع مثًلا — وجب مراجعُة هذا
    الموضع، ال أن يمضي على نسٍق لم يبقَ.
    """
    from app import exit_case

    src = inspect.getsource(exit_case)
    assert "outstanding_loan" in src, "ذهبت السابقة"
    # **وتُقاس البنيُة لا العبارة**: مطابقُة نٍّص بالتشكيل هّشة،
    # والمقصوُد أن السابقَة **تُسمّي ولا تقتطع** — وذلك يُقاس بما تفعله.
    assert "create_task(" in src, "لم تبقَ تُسمّي المبلغ لمن يسوّي"
    for acts in ("Deduction(", "basic_salary ="):
        assert acts not in src, (
            f"صارت السابقُة تقتطع — تُراجَع الموازاة: {acts}")


def test_no_notice_when_there_is_no_debt():
    """وال يُرسَل إخطاٌر لمن ال دَين عليه — فضجيٌج يُدرَّب على تجاهله."""
    from app import workflow as W

    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1))
        req = models.Request(company_id=1, employee_id=emp.id,
                             request_type_code="leave", status="pending",
                             payload_json={"travel_required": True})
        db.add(req)
        db.flush()
        rid = req.id
        W._warn_debt_before_travel(db, req, emp.name)
        db.commit()
        made = db.scalars(select(models.Task).where(
            models.Task.dedup_key.like(f"travel_loan_due:{rid}:%"))).all()
        owed = W.outstanding_loan(db, emp.id)
    finally:
        db.close()

    try:
        if owed <= 0:
            assert not made, "أُرسل إخطاٌر بال دَين"
        else:
            assert made, f"عليه {owed} ولم يُخطَر أحد"
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.Task).where(
                models.Task.dedup_key.like(f"travel_loan_due:{rid}:%")))
            db.execute(sa_delete(models.Request).where(models.Request.id == rid))
            db.commit()
        finally:
            db.close()


def test_the_declared_document_is_not_claimed_to_be_done():
    """**وإخطاٌر ال يُعَدّ وثيقة**: ``OD-012`` ما زالت فجوًة معلنة.

    فلو حُذفت من ``OUTPUT_GAPS`` بحجّة أن التنبيه يكفي، صار السجلُّ يقول
    إن المستنَد يُنتَج وهو ال يُنتَج.
    """
    from app import v15_registry as R

    assert "WF-002/OD-012" in R.OUTPUT_GAPS, \
        "رُفعت الفجوُة واإلخطاُر ليس وثيقة"
    assert "WF-002/OD-012" in set(R.output_gaps())
