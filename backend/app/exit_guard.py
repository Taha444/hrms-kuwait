# -*- coding: utf-8 -*-
"""P6-27 — خروج واحد للموظف في وقت واحد.

**ما ظهر بالقياس، وهو أسوأ مما يصفه البند:**

فتحتُ للموظف نفسه (خالد العتيبي) ثلاثة مسارات خروج في دقيقة واحدة،
وقُبلت كلها:

* ``EosCase`` بتاريخ إنهاء **2026-10-01**
* مسودة إنهاء على ملفه بتاريخ **2026-11-15** — و**بتسوية محسوبة كاملة**
* طلب ``REQEOS`` بآخر يوم عمل **2026-12-01**

ثلاثة تواريخ مختلفة لمغادرة واحدة، وحسابان مستقلّان للمستحقّات. وأيُّ
مسار يبلغ نهايته أوًلا يكتب ``status="terminated"`` و
``eos_settlement_json`` **فوق** ما كتبه الآخر — بلا تعارض ظاهر ولا
سؤال. فيُدفع للموظف رقم، ويبقى في السجلّ رقم آخر.

**وأيُّ وحدة هي المرجع سؤال عمل** لا استنتاج شيفرة: هل يبدأ الخروج من
حالة نهاية الخدمة، أم من مسودة على الملف، أم من طلب استقالة يقدّمه
الموظف؟ لكل واحد منطق، والجواب يخصّ إجراءات الشركة.

**أما «خروجان مفتوحان مًعا» فليس سؤاًلا**: لا سياسة تقصده. فيُمنع الآن،
ويبقى تعيين المرجع قراًرا يُتَّخذ لاحًقا بلا أن يظلّ الباب مفتوًحا
للتناقض في هذه الأثناء.

**وREQCLR مستثنى عمًدا**: إخلاء الطرف **خطوة داخل** الخروج لا خروج
مستقلّ — وحالة نهاية الخدمة نفسها فيها مرحلة ``clearance``. منعُه
يمنع إجراًء مشروًعا أثناء خروج قائم.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select

from . import models

#: حالات نهاية الخدمة التي تُعدّ **مفتوحة**: لم تبلغ الصرف بعد.
#: و``settled`` نهاية المسار المالي؛ ما بعدها (طباعة/حفظ) أثر ورقي.
OPEN_EOS_STATUSES = ("initiated", "calculated", "approved", "clearance",
                     "acknowledged")

#: أنواع الطلبات التي **تبدأ** خروًجا.
#:
#: وREQCLR ليس منها: إخلاء الطرف خطوة داخل الخروج لا خروج مستقلّ،
#: ومنعُه يمنع إجراًء مشروًعا أثناء خروج قائم.
EXIT_REQUEST_TYPES = ("REQRESIGN", "REQEOS")

#: حالات الطلب التي تعني «ما زال جارًيا».
LIVE_REQUEST_STATUSES = ("pending", "awaiting_signature", "awaiting_delegate",
                         "ready_for_pickup", "returned", "apply_failed")


def open_exits(db, employee_id: int) -> list[dict]:
    """كل خروج مفتوح على هذا الموظف — من المسارات الثلاثة مًعا.

    يقرأ الثلاثة في موضع واحد. ولو سأل كل باب عن نفسه فقط، لَبقي كل
    منها يرى مساره نظيًفا ويجهل الآخرَين — وهو ما وقع فعًلا.
    """
    found: list[dict] = []

    case = db.scalar(select(models.EosCase).where(
        models.EosCase.employee_id == employee_id,
        models.EosCase.status.in_(OPEN_EOS_STATUSES)))
    if case:
        found.append({
            "kind": "eos_case", "id": case.id,
            "label": f"حالة نهاية خدمة {case.reference_no or f'#{case.id}'}",
            "state": case.status,
            "date": str(case.termination_date or ""),
            "where": "شاشة نهاية الخدمة"})

    emp = db.get(models.Employee, employee_id)
    if emp is not None and emp.pending_termination_json:
        found.append({
            "kind": "termination_draft", "id": emp.id,
            "label": "مسودة إنهاء خدمة على ملف الموظف",
            "state": ("معتمَدة" if emp.pending_termination_approved_at
                      else "مُعدّة بانتظار الاعتماد"),
            "date": "",
            "where": "ملف الموظف ← إنهاء الخدمة"})

    for req in db.scalars(select(models.Request).where(
            models.Request.employee_id == employee_id,
            models.Request.request_type_code.in_(EXIT_REQUEST_TYPES),
            models.Request.status.in_(LIVE_REQUEST_STATUSES))).all():
        found.append({
            "kind": "request", "id": req.id,
            "label": f"طلب {req.request_type_code} ‏#{req.id}",
            "state": req.status,
            "date": "",
            "where": "شاشة الطلبات"})

    return found


def assert_single_exit(db, employee_id: int) -> None:
    """يمنع فتح خروج ثانٍ، **ويقول أين الأول**.

    ولا يستثني نوع الباب الذي يُفتح منه: كتبتُ أوًلا مرشًِّحا يُسقط ما
    يطابق نوع الفاتح، ظًنا أنه يمنع تعارض الباب مع نفسه — وليس هناك
    تعارض من هذا النوع أصًلا (الفحص يسبق الإنشاء في المسارات الثلاثة).
    وكان أثره الوحيد أن يمرّ ``REQRESIGN`` بجانب ``REQEOS`` لأن كليهما
    ``request`` — أي أن الحارس يفتح الثغرة التي بُني لسدّها.
    """
    existing = open_exits(db, employee_id)
    if not existing:
        return
    first = existing[0]
    where = " و".join(sorted({e["where"] for e in existing}))
    raise HTTPException(status_code=409, detail={
        "code": "EXIT_ALREADY_OPEN",
        "message": (
            f"لهذا الموظف خروج مفتوح بالفعل: {first['label']} "
            f"({first['state']}"
            + (f" — {first['date']}" if first["date"] else "")
            + "). أغلقه أو ألغِه قبل فتح غيره، فمساران مفتوحان يعنيان "
              "تاريخَي مغادرة وتسويتين لمغادرة واحدة."),
        "where": where,
        "open_exits": existing,
    })
