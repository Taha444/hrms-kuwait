# -*- coding: utf-8 -*-
"""WF-09 — الأثر الفعلي على البيانات عند اكتمال الطلب.

الطلب كان يمرّ بكل مراحل الاعتماد ثم يُغلق "مكتمل" بلا أن يتغيّر شيء:
جواز جديد يُعتمد ورقمه القديم يبقى في السجل — ومحرّك انتهاء الصلاحية يظلّ
ينبّه على تاريخ بطل. ترقية تُعتمد والراتب كما هو، فالمسيّر يحسب بالقديم.
نقل فرع يُعتمد والموظف في مكانه. الأسوأ أن كل ذلك يبدو ناجًحا: حالة الطلب
"مكتمل" وسلسلة الاعتمادات كاملة، فلا أحد يكتشف الفجوة إلا بمقارنة يدوية.

الحلّ هنا **جدول تصريحي** لا سلسلة ``if``: كل نوع يعلن الحقول التي يغيّرها
ومصدر كل قيمة من نموذجه. إضافة نوع جديد سطر في الجدول، لا فرع في دالة —
فيستحيل أن يوجد نوع "يُفترض أنه يغيّر بيانات" ولا أحد يعرف أين يغيّرها.

قواعد ثابتة لكل أثر:
- **مرّة واحدة**: البصمة تُحفظ في AuditLog، وإعادة التطبيق تُكتشف فتُرجِع
  نجاًحا بلا تكرار — لا يُرفع الراتب مرتين لأن الطلب أُعيد إنهاؤه.
- **قبل/بعد**: كل تغيير يُقيَّد بقيمته السابقة واللاحقة، فالسجل يشرح نفسه.
- **الرفض أوضح من الصمت**: قيمة غير صالحة أو حقل مفقود تُفشل التطبيق
  (apply_failed) بدل أن تكتب None فوق بيانات صحيحة.

**قيد معلوم**: ``effective_date`` المستقبلي يُطبَّق فور الاعتماد ويُدوَّن
تاريخه في السجل — لا يوجد جدولة مؤجَّلة. مسجَّل في FOUND_EXTRA.md.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Callable

from sqlalchemy import select

from .audit_context import actor_user_id, original_actor_user_id
from sqlalchemy.orm import Session

from . import models
from .clock import today as kuwait_today


def _as_date(v: Any) -> date | None:
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str) and v.strip():
        try:
            return date.fromisoformat(v.strip()[:10])
        except ValueError:
            return None
    return None


def _as_int(v: Any) -> int | None:
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _as_float(v: Any) -> float | None:
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _as_text(v: Any) -> str | None:
    s = str(v).strip() if v is not None else ""
    return s or None


#: نوع الطلب ← (وصف الأثر، خريطة {عمود الموظف: (حقل النموذج، محوِّل)})
#:
#: العمود على اليسار لأنه الوجهة الوحيدة الممكنة؛ الحقل على اليمين لأن اسمه
#: في النموذج قد يختلف (new_passport ← passport_number) وهذا هو الالتباس
#: الذي يجب أن يُكتب صراحة في مكان واحد.
FIELD_EFFECTS: dict[str, tuple[str, dict[str, tuple[str, Callable[[Any], Any]]]]] = {
    "REQPASS": ("تحديث بيانات الجواز", {
        "passport_number": ("new_passport", _as_text),
        "passport_expiry": ("new_expiry", _as_date),
    }),
    "REQCIVIL": ("تحديث البطاقة المدنية", {
        "civil_id": ("new_civil", _as_text),
    }),
    "REQCONTACT": ("تحديث بيانات الاتصال", {
        "phone": ("new_phone", _as_text),
        "email": ("new_email", _as_text),
    }),
    "REQPROM": ("ترقية / مراجعة راتب", {
        "job_title": ("new_title", _as_text),
        "basic_salary": ("new_salary", _as_float),
    }),
    "REQSHIFT": ("تغيير الوردية", {
        "shift_id": ("requested_shift_id", _as_int),
    }),
    "REQTRANS": ("نقل إلى فرع آخر", {
        "branch_id": ("to_branch_id", _as_int),
    }),
    "REQTRFLIC": ("نقل فرع / ترخيص", {
        "branch_id": ("to_branch_id", _as_int),
        "license_id": ("to_license_id", _as_int),
    }),
}

#: حقول لا يجوز أن تصير فارغة بأثر طلب — تفريغها يفقد بيانات لا تُستعاد.
_REQUIRED_TARGETS = {"civil_id", "passport_number", "basic_salary", "job_title"}


def _audit_action(code: str) -> str:
    return f"request_effect_applied:{code}"


def already_applied(db: Session, req: models.Request) -> bool:
    """هل طُبِّق أثر هذا الطلب من قبل؟

    البصمة سطر تدقيق لا عمود جديد: السجل موجود أصًلا ولا يُحذف، فهو أصدق
    مرجع من علَم قابل لإعادة الضبط.
    """
    row = db.scalar(select(models.AuditLog).where(
        models.AuditLog.entity_type == "request",
        models.AuditLog.entity_id == req.id,
        models.AuditLog.action == _audit_action(req.request_type_code),
    ))
    return row is not None


def apply_field_effect(db: Session, req: models.Request) -> tuple[bool, str]:
    """يطبّق أثر الطلب على سجل الموظف. يعيد (نجح، شرح للسجل)."""
    spec = FIELD_EFFECTS.get(req.request_type_code)
    if not spec:
        return True, "لا أثر بيانات لهذا النوع"
    label, mapping = spec

    if already_applied(db, req):
        return True, f"{label}: مطبَّق مسبًقا لهذا الطلب — لم يُطبَّق مرتين"

    emp = db.get(models.Employee, req.employee_id)
    if not emp:
        return False, "الموظف غير موجود"

    payload = req.payload_json or {}
    changes: dict[str, dict[str, Any]] = {}
    for column, (field, cast) in mapping.items():
        raw = payload.get(field)
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            # حقل اختياري لم يُملأ (بريد مثًلا) — يُترك، ولا يُكتب فوقه فراغ
            if column in _REQUIRED_TARGETS:
                return False, f"{label}: الحقل «{field}» مطلوب ولم يُملأ"
            continue
        value = cast(raw)
        if value is None:
            return False, f"{label}: قيمة غير صالحة للحقل «{field}»: {raw!r}"

        before = getattr(emp, column)
        if before == value:
            continue
        setattr(emp, column, value)
        changes[column] = {
            "before": before.isoformat() if isinstance(before, date) else before,
            "after": value.isoformat() if isinstance(value, date) else value,
        }

    if not changes:
        return True, f"{label}: القيم المطلوبة مطابقة للحالي — لا تغيير"

    eff = _as_date(payload.get("effective_date") or payload.get("effective_from"))
    note_eff = f" (تاريخ السريان المعلن: {eff.isoformat()})" if eff and eff > kuwait_today() else ""

    db.add(models.AuditLog(
        company_id=req.company_id, user_id=actor_user_id(),
        original_user_id=original_actor_user_id(),
        action=_audit_action(req.request_type_code),
        entity_type="request", entity_id=req.id,
        detail=f"{label} — الموظف #{emp.id}{note_eff}",
        correlation_id=f"req:{req.id}",
        before_json={c: v["before"] for c, v in changes.items()},
        after_json={c: v["after"] for c, v in changes.items()},
    ))
    # سطر ثانٍ على الموظف نفسه: من يفتّش تاريخ موظف يبحث بـentity=employee
    # لا بـentity=request، فلا يعثر على التغيير إن لم يُقيَّد هنا أيًضا.
    db.add(models.AuditLog(
        company_id=req.company_id, user_id=actor_user_id(),
        original_user_id=original_actor_user_id(),
        action="employee_updated_by_request",
        entity_type="employee", entity_id=emp.id,
        detail=f"{label} — بموجب الطلب #{req.id}{note_eff}",
        correlation_id=f"req:{req.id}",
        before_json={c: v["before"] for c, v in changes.items()},
        after_json={c: v["after"] for c, v in changes.items()},
    ))

    summary = "، ".join(
        f"{c}: {v['before'] if v['before'] not in (None, '') else '—'} ← {v['after']}"
        for c, v in changes.items()
    )
    return True, f"{label}{note_eff}: {summary}"
