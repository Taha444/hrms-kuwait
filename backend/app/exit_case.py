# -*- coding: utf-8 -*-
"""P6-27 — فتح حالة نهاية الخدمة: مصدر واحد يستدعيه كل من يبدأ خروًجا.

**قرار المالك**: حالة نهاية الخدمة (``EosCase``) هي المرجع.

**وما ظهر بالقياس**: مسار الطلبات **لا يبلغ المرجع إطلاًقا**. لا نوع
خروج له أثر عند الاكتمال — يقدّم الموظف استقالته، ويعتمدها المدير
وشؤون الموظفين، ويوقّعها، فيُختم الطلب «مكتمل»… ولا حالة نهاية خدمة
تُفتح، ولا يتغيّر شيء في ملفه. فيبقى على رأس العمل في كل تقرير حتى
يتذكّر أحدهم أن يفتح الحالة يدًوا.

وهو النمط الثالث من نوعه في هذه الجولة بعد ``REQSIG`` والمستند
المولَّد: **إجراء يُعلَن ناجًحا ولا يقع أثره**.

**ولماذا هنا لا في الراوتر**: المنطق كان مكتوًبا داخل ``initiate_case``
وحدها. واستدعاؤه من مسار الطلبات كان يعني نسخة ثانية منه — ونسختان
لقاعدة واحدة تنحرف إحداهما. فاستُخرج إلى هنا، ويستدعيه الطرفان.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select

from . import eos as eos_engine, models

#: حالة نهاية الخدمة تُعدّ **قائمة** ما لم تُحفَظ نهائًيا.
NOT_CLOSED = "filed"


#: الحالةُ التي يكتبها المسارُ عند بلوغ نهايته — بسبب الإنهاء.
#: قرار المالك (2026-09-17): الاستقالةُ تمرّ بمسار الإنهاء لا بقائمة الحالة،
#: فيكتب المسارُ «مستقيل» لسببها بدل «منتهية خدمته» للجميع.
FINAL_STATUS_BY_REASON = {"resignation": "resigned", "marriage": "resigned",
                          "retirement": "retired"}


def final_status(reason: str | None) -> str:
    return FINAL_STATUS_BY_REASON.get(reason or "", "terminated")


def notice_terms(db, company_id: int, reason: str, served: bool | None,
                 served_date: date | None, termination_date: date) -> tuple[float, dict]:
    """أيامُ بدل الإنذار ووصفُها — مصدرٌ واحد لمسار الحالة ومسودة الإنهاء.

    قرار المالك (2026-09-17): يُصرف عن الجزء غير المُبلَّغ من مدة الإنذار في
    الفصل غير التأديبي وحده. والمدةُ من السياسة ``eos.notice_days``. وإن لزم
    الجوابُ ولم يُسجَّل رُفض الحساب (409) — لا يُفترض أنه أُبلغ ولا أنه لم يُبلَّغ.
    """
    from . import policy
    pol = policy.get(db, company_id, "eos.notice_days", on_date=termination_date)
    notice_days = float((pol.get("value") or {}).get("days") or 0)
    if served and served_date and served_date > termination_date:
        raise HTTPException(status_code=400, detail=(
            "تاريخ إبلاغ الإنذار بعد تاريخ الإنهاء"))
    owed = eos_engine.notice_owed_days(reason, notice_days, served, served_date,
                                       termination_date)
    if owed is None:
        raise HTTPException(status_code=409, detail=(
            "الفصل غير التأديبي يستحق بدل إنذار عمّا لم يُبلَّغ من مدته — "
            "سجّل «هل أُبلغ الإنذار؟» (وتاريخ الإبلاغ إن أُبلغ) قبل الحساب"))
    return owed, {
        "applies": reason in eos_engine.NOTICE_PAY_REASONS,
        "served": served,
        "served_date": served_date.isoformat() if served_date else None,
        "notice_days": notice_days,
        "policy_source": pol.get("source"),
        "policy_version": pol.get("version"),
    }


def open_case(db, emp: models.Employee, *, termination_date: date, reason: str,
              actor_user_id: int | None,
              source_request_id: int | None = None,
              notice_served: bool | None = None,
              notice_served_date: date | None = None) -> models.EosCase:
    """يفتح حالة نهاية خدمة، أو يرفع 409 إن تعذّر.

    ``source_request_id`` هو **الرابط** الذي يطلبه البند: من يقرأ الحالة
    يعرف من أين جاءت، ومن يقرأ الطلب يصل إلى ما ترتّب عليه. وبلا هذا
    الرابط يبقى الأثر واقًعا وأصلُه مجهوًلا.
    """
    if getattr(emp, "non_payroll", False):
        raise HTTPException(status_code=409, detail=(
            "هذا السجل للوصول/الصلاحية فقط وليس وظيفة على كشف الرواتب — "
            "لا تُفتح له حالة نهاية خدمة"))
    if reason not in eos_engine.TERMINATION_REASONS:
        raise HTTPException(status_code=400, detail=(
            f"سبب غير معروف — المسموح: {list(eos_engine.TERMINATION_REASONS)}"))
    # **المصدر الواحد للأبواب الثلاثة**: كانت الحالةُ تُفتح لتاريخ إنهاء قبل تاريخ التعيين،
    # ولا يُرفض إلا عند الحساب لاحقًا برسالة عن مرحلة أخرى. (وحالةُ الموظف لا تُفحص هنا:
    # ``execute_termination`` يضبطها قبل أن يفتح المرجع، فحارسُها في الباب الذي يحتاجه.)
    if emp.hire_date and termination_date and termination_date < emp.hire_date:
        raise HTTPException(status_code=400, detail=(
            f"تاريخ انتهاء الخدمة ({termination_date}) أقدم من تاريخ التعيين ({emp.hire_date})"))

    existing = db.scalar(select(models.EosCase).where(
        models.EosCase.employee_id == emp.id,
        models.EosCase.status != NOT_CLOSED))
    if existing:
        raise HTTPException(status_code=409, detail=(
            f"توجد حالة مفتوحة بالفعل لهذا الموظف "
            f"(#{existing.id}، الحالة: {existing.status})"))

    now = datetime.now(timezone.utc)
    case = models.EosCase(
        company_id=emp.company_id, employee_id=emp.id, status="initiated",
        termination_date=termination_date, termination_reason=reason,
        initiated_by=actor_user_id, initiated_at=now,
        source_request_id=source_request_id,
        notice_served=notice_served,
        notice_served_date=notice_served_date if notice_served else None,
    )
    db.add(case)
    db.flush()
    case.reference_no = f"EOS/{emp.company_id}/{now:%Y%m}/{case.id:04d}"
    return case


#: النوع ← (حقل تاريخ آخر يوم عمل في الحمولة، حقل السبب أو سبب ثابت).
#:
#: ``REQRESIGN`` سببه استقالة بطبيعته، و``reason`` في حمولته نصّ حرّ
#: يشرح الدافع — لا مفتاح من مفاتيح المحرّك. أما ``REQEOS`` فيحمل
#: السبب بمفردات المحرّك نفسها (قائمة اختيار مطابقة لـ
#: ``TERMINATION_REASONS``).
EXIT_REQUEST_SPEC: dict[str, tuple[str, str | None]] = {
    "REQRESIGN": ("proposed_last_day", None),      # السبب ثابت: استقالة
    "REQEOS": ("last_day", "reason"),
}


def open_from_request(db, req: models.Request) -> tuple[bool, str]:
    """أثر اكتمال طلب خروج: يفتح المرجع ويربطه بالطلب.

    بتوقيع أثر الطلبات ``(نجح، شرح)`` — فيمرّ من الباب نفسه الذي تمرّ
    منه بقية الآثار: ذرّية واحدة، ومسار ``apply_failed`` واحد، ولا
    طريق ثانٍ يُطبَّق منه أثر.
    """
    from .audit_context import actor_user_id

    spec = EXIT_REQUEST_SPEC.get(req.request_type_code)
    if not spec:
        return True, "لا أثر خروج لهذا النوع"
    day_field, reason_field = spec

    # لا يُفتح مرجعان لطلب واحد لو أُعيد إنهاؤه.
    #
    # والقياس على **وجود المرجع نفسه** لا على بصمة تدقيق: جرّبتُ أوًلا
    # ``request_effects.already_applied`` وهي تبحث عن سطر تدقيق يكتبه
    # أثرُ الحقول ولا يكتبه هذا — فعادت False، وحاولت الفتح ثانيًة
    # فارتطمت بـ«توجد حالة مفتوحة» وأُعلن الطلب متعثًّرا. حارس تكرار
    # يقيس وكيًلا عن الشيء لا الشيء نفسه.
    linked = db.scalar(select(models.EosCase).where(
        models.EosCase.source_request_id == req.id))
    if linked:
        return True, (f"فُتحت حالة نهاية الخدمة سابًقا لهذا الطلب "
                      f"({linked.reference_no or f'#{linked.id}'})")

    emp = db.get(models.Employee, req.employee_id)
    if not emp:
        return False, "الموظف غير موجود"

    payload = req.payload_json or {}
    raw_day = payload.get(day_field)
    if not raw_day:
        return False, f"«{day_field}» غير مذكور في الطلب — لا تاريخ للمغادرة"
    try:
        last_day = date.fromisoformat(str(raw_day)[:10])
    except ValueError:
        return False, f"تاريخ غير صالح في «{day_field}»: {raw_day!r}"

    reason = (payload.get(reason_field) if reason_field else None) or "resignation"
    if reason not in eos_engine.TERMINATION_REASONS:
        return False, f"سبب غير معروف في الطلب: {reason!r}"

    try:
        case = open_case(db, emp, termination_date=last_day, reason=reason,
                         actor_user_id=actor_user_id(),
                         source_request_id=req.id)
    except HTTPException as exc:
        # الفشل يُعلَن ولا يُبتلع: الطلب يصير apply_failed بسببه المكتوب،
        # فيراه من يملك إصلاحه بدل أن يُختم «مكتمل» بلا أثر.
        return False, str(exc.detail)

    # **ودٌين قائٌم لا يختفي بانتهاء الخدمة.**
    #
    # أقساط القرض صفوُف خصم في أشهٍر قادمة، والرواتب تحسب للموظفين على رأس
    # العمل. فمن انتهت خدمته وعليه أقساٌط لم تُحتسب بعد **لا تُقرأ صفوفه
    # أبًدا** — فيسقط الدين بصمت ولا يظهر في أيّ شاشة ولا تقرير.
    #
    # ولا يُقرَّر هنا مصيُره: اقتطاعه من المستحقات حٌد قانوني ومسألُة
    # سياسة. لكنه **يُسمّى** فيبلغ من يسوّي الحساب، بدل أن يُكتشَف بعد
    # إغلاق الملف أو لا يُكتشَف أصًلا.
    from .workflow import outstanding_loan

    owed = outstanding_loan(db, emp.id)
    if owed > 0:
        from .notifications import create_task, users_by_role

        for u in users_by_role(db, emp.company_id, ["accountant", "hr"]):
            create_task(
                db, company_id=emp.company_id, type="config_gap",
                assignee_user_id=u.id, severity="critical",
                title=f"دٌين قرٍض قائم عند نهاية خدمة {emp.name}",
                detail=(f"بقي {owed:.3f} د.ك من أقساٍط لم تُحتسب بعد. وأقساُط "
                        f"ما بعد آخر يوم عمل لا تقرؤها الرواتب — فيلزم "
                        f"تسويتها في حساب نهاية الخدمة أو إسقاطها بقرار."),
                related_entity_type="eos_case", related_entity_id=case.id,
                dedup_key=f"exit_loan_due:{case.id}",
            )

    return True, (f"فُتحت حالة نهاية الخدمة {case.reference_no} — "
                  f"{eos_engine.TERMINATION_REASONS.get(reason, reason)} @ {last_day}"
                  + (f" · دٌين قرٍض قائم {owed:.3f}" if owed > 0 else ""))
