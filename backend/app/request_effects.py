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

- **ولا يقع أثٌر قبل تاريخ نفاذه**: ``effective_date`` في المستقبل يؤجّل
  الأثر — والطلب يكتمل — ويلتقطه المسُح اليومي حين يحلّ اليوم
  (``due_deferred_effects`` و``apply_due_effects``). وكان يُطبَّق فوًرا
  ويُدوَّن تاريخ النفاذ في ملاحظة، أي يخالف القاعدة ثم يسجّلها.

- **والتاريخ في مصدٍر واحد**: ما يُنشَر إلى ``Document.expiry_date`` —
  الذي يقرؤه محرّك التنبيهات — يُنشَر معه، فلا تُظهر شاشٌة تاريًخا جديًدا
  وينادي تنبيٌه على قديم. انظر ``DOCUMENT_EXPIRY_EFFECTS``.
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
    # **مفتاٌح لا يطابق نوًعا لا يعمل أبًدا.** الطلب يُخزَّن بكود الكتالوج
    # المُحَل (``request_type_code=rt.code``) لا بالكنية المرسَلة، فأثٌر
    # مسجٌَّل تحت كنية لا يُستدعى قط. وكانت ثلاثة: ``REQCIVIL`` (والكود
    # ``REQCID``) و``REQPROM`` (``REQPROMO``) و``REQTRANS`` (``REQTRF``).
    #
    # فبقيت ترقيٌة تُعتمد ولا يتغيّر راتب، وبطاقٌة مدنية تُجدَّد ولا يتغيّر
    # رقمها، ونقٌل يُعتمد ولا ينتقل أحد — وكلّها تُغلَق «مكتملة».
    #
    # ولم يمسكه حارٌس لأن لا شيء كان يقابل مفاتيح هذا السجلّ بالكتالوج.
    "REQCID": ("تحديث البطاقة المدنية", {
        "civil_id": ("new_civil", _as_text),
    }),
    "REQCONTACT": ("تحديث بيانات الاتصال", {
        "phone": ("new_phone", _as_text),
        "email": ("new_email", _as_text),
    }),
    "REQPROMO": ("ترقية / مراجعة راتب", {
        "job_title": ("new_title", _as_text),
        "basic_salary": ("new_salary", _as_float),
    }),
    "REQSHIFT": ("تغيير الوردية", {
        "shift_id": ("requested_shift_id", _as_int),
    }),
    "REQTRF": ("نقل إلى فرع آخر", {
        "branch_id": ("to_branch_id", _as_int),
    }),
    "REQTRFLIC": ("نقل فرع / ترخيص", {
        "branch_id": ("to_branch_id", _as_int),
        "license_id": ("to_license_id", _as_int),
    }),
}

#: **مصدران لتاريٍخ واحد، والتجديد يحدّث الذي لا يقرؤه المحرّك.**
#:
#: تاريُخ انتهاء الجواز مخزٌَّن في موضعين: ``Employee.passport_expiry``
#: (تقرؤه شاشُة الملف) و``Document.expiry_date`` للمستند الجاري (يقرؤه
#: محرُّك التنبيهات وحده — ``notifications`` يستعلم ``Document`` لا
#: ``Employee``). فـ``REQPASS`` كان يكتب عموَد الموظف **فقط**: الشاشة
#: تُظهر التاريخ الجديد، والتنبيه يظلّ ينادي على التاريخ القديم.
#:
#: و``REQCID`` أسوأ: **لا عموَد للبطاقة المدنية في الموظف أصًلا** —
#: تاريخها في المستند وحده. فكان النموذج يسأل «تاريخ الانتهاء الجديد»
#: ولا أحَد يكتبه في أيّ موضع. حقٌل يُدخَله المستخدم ويُلقى.
#:
#: والقاعدُة من السكيل بنصّها: «حدّث **المصدر الواحد** الذي تقرأ منه
#: الشاشات… ولا يبقى جزٌء من النظام شايف التاريخ القديم وجزٌء آخر شايف
#: الجديد».
DOCUMENT_EXPIRY_EFFECTS: dict[str, tuple[str, str]] = {
    "REQPASS": ("new_expiry", "passport"),
    "REQCID": ("new_expiry", "civil_id"),
}


def _propagate_document_expiry(db: Session, req: models.Request,
                               emp: models.Employee,
                               payload: dict) -> dict[str, dict[str, Any]]:
    """ينشر تاريخ الانتهاء الجديد إلى المستند الذي يقرؤه محرّك التنبيهات.

    ويُغلق تنبيه المستند القديم: المسُح اليومي **يتخطّى** أيَّ مستنٍد له
    مهمٌة ``doc_expiring`` مفتوحة، فتنبيٌه قديٌم يبقى مفتوًحا بتاريٍخ بطل
    **ويمنع أيَّ تنبيٍه مصّحح** — يقول المستند ينتهي في تاريٍخ مضى، ولا
    سبيل لتصحيحه. والإغلاق يُستدعى من دالته المقيَّدة بمستندها، لا
    يُكتب ثانيًة.
    """
    spec = DOCUMENT_EXPIRY_EFFECTS.get(req.request_type_code)
    if not spec:
        return {}
    field, doc_type = spec
    new = _as_date(payload.get(field))
    if new is None:
        return {}

    doc = db.scalar(select(models.Document).where(
        models.Document.entity_type == "employee",
        models.Document.entity_id == emp.id,
        models.Document.document_type_code == doc_type,
        models.Document.is_current == True))  # noqa: E712
    if doc is None:
        # لا مستنَد جاٍر من هذا النوع — لا يُخلَق مستٌند من طلب.
        return {}
    before = doc.expiry_date
    if before == new:
        return {}

    doc.expiry_date = new
    from .routers.documents import _close_expiry_tasks_for
    _close_expiry_tasks_for(db, doc.id)
    return {f"doc:{doc_type}.expiry_date": {
        "before": before.isoformat() if isinstance(before, date) else before,
        "after": new.isoformat(),
    }}


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

    # **ولا يقع أثٌر قبل تاريخ نفاذه.**
    #
    # كان يُطبَّق فوًرا، ويُقرأ ``effective_date`` **لكتابة ملاحظة فقط**:
    # «تاريخ السريان المعلن: …». أي أن النظام يعرف أن التاريخ في المستقبل
    # ويطبّق، ثم يسجّل القاعدة التي خالفها. فترقيٌة تُعتمد في يناير بنفاٍذ
    # في أبريل ترفع الراتب في يناير — وثلاثُة أشهر فرًقا في الأجر وفي كل
    # ما يُحسب منه.
    #
    # والتأجيل نجاٌح لا فشل: الطلب يكتمل، والأثر ينتظر يومه. ويلتقطه
    # المسح اليومي حين يحلّ — ولا يحتاج جدوًلا جديًدا، فبصمُة التطبيق
    # (سطر التدقيق) هي ما يميّز ما وقع ممّا لم يقع.
    eff_declared = _as_date(payload.get("effective_date")
                            or payload.get("effective_from"))
    if eff_declared and eff_declared > kuwait_today():
        return True, (f"{label}: مؤجٌَّل حتى تاريخ نفاذه "
                      f"{eff_declared.isoformat()} — لم يُطبَّق بعد")
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

    # **والنشُر قبل حكم «لا تغيير»**: تاريٌخ يتغيّر في المستند وحده تغيٌُّر.
    changes.update(_propagate_document_expiry(db, req, emp, payload))

    if not changes:
        return True, f"{label}: القيم المطلوبة مطابقة للحالي — لا تغيير"

    eff = _as_date(payload.get("effective_date") or payload.get("effective_from"))
    note_eff = ""

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


def due_deferred_effects(db: Session) -> list[models.Request]:
    """طلباٌت اكتملت وأثُرها مؤجٌَّل إلى تاريخ نفاٍذ قد حلّ.

    **وتأجيٌل بلا يوٍم يحلّ فيه تسويٌف لا تأجيل.** فالمسح اليومي هو ما
    يجعل «مؤجَّل» وعًدا يُوفى.

    والتمييز ببصمة التطبيق (سطر التدقيق) لا بعموٍد جديد: هي موجودٌة أصًلا
    ولا تُحذف، ولا يُضاف مصدٌر ثاٍن لحقيقٍة واحدة.
    """
    codes = tuple(FIELD_EFFECTS)
    if not codes:
        return []
    rows = db.scalars(select(models.Request).where(
        models.Request.request_type_code.in_(codes),
        models.Request.status == "completed",
    )).all()

    today = kuwait_today()
    due = []
    for req in rows:
        payload = req.payload_json or {}
        eff = _as_date(payload.get("effective_date")
                       or payload.get("effective_from"))
        if eff and eff > today:
            continue                     # لم يحن بعد
        if already_applied(db, req):
            continue
        due.append(req)
    return due


def apply_due_effects(db: Session) -> dict:
    """يطبّق ما حلّ من الآثار المؤجَّلة — يُستدعى من المسح اليومي.

    **والفشل لا يُبتلع**: الطلب يبقى بلا أثر ويُعاد غًدا، ويُسجَّل سببه.
    فأثٌر يفشل صامًتا أسوأ من أثر يتأخّر.
    """
    applied, failed = [], []
    for req in due_deferred_effects(db):
        try:
            ok, note = apply_field_effect(db, req)
        except Exception as exc:  # pragma: no cover — لا تُسقط بقية الطلبات
            db.rollback()
            failed.append({"request_id": req.id, "note": f"{type(exc).__name__}: {exc}"})
            continue
        (applied if ok else failed).append({"request_id": req.id, "note": note})
    if applied:
        db.commit()
    return {"applied": len(applied), "failed": len(failed),
            "details": applied + failed}
