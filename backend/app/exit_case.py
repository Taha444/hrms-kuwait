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


def open_case(db, emp: models.Employee, *, termination_date: date, reason: str,
              actor_user_id: int | None,
              source_request_id: int | None = None) -> models.EosCase:
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

    return True, (f"فُتحت حالة نهاية الخدمة {case.reference_no} — "
                  f"{eos_engine.TERMINATION_REASONS.get(reason, reason)} @ {last_day}")
