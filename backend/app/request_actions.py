# -*- coding: utf-8 -*-
"""APP-01 — الأفعال المتاحة للمستخدم على طلب: مصدر واحد للواجهة وللمسار.

**العطل.** المعتمِد الحالي لا يرى أزرار اعتماد/رفض/إرجاع رغم أن الخادم
يقبل قراره. السبب أن الصلاحية تُحسب مرّتين بقاعدتين مختلفتين:

- الخادم يشترط **صلاحية مجال الفئة** (``approve_leave`` · ``approve_finance``
  · ``complete_validation`` …) — يختارها ``can_complete_stage`` حسب فئة
  الطلب ونوع الخطوة.
- والواجهة تشترط ``approve_request`` العامة، وهي موصوفة في الشيفرة نفسها
  بأنها «مهجورة».

فمن يعتمد الإجازات بصلاحية ``approve_leave`` — وهو المعتمِد الفعليّ —
يقبله الخادم وتُخفي عنه الواجهة الأزرار. أي منطق صلاحيات مكرَّر في مكانين
ينحرف أحدهما عن الآخر؛ هذه حالة الانحراف بعينها.

**القاعدة.** شريط الإجراءات يُبنى من ردّ الخادم. الواجهة تعرض ما في
``allowed_actions`` ولا تحسب شيًئا.

**وهذا الإصلاح يُظهر أزراًرا كانت مخفيّة، فخطره أن يفتح ثغرة.** ولهذا
تُشتقّ القائمة من **نفس الدالتين** اللتين يستدعيهما مسار ``/decide`` —
``can_decide`` و``can_complete_stage`` — لا من نسخة ثالثة منهما. فما تعرضه
الواجهة هو ما يقبله الخادم بالضبط: لا زر بلا صلاحية، ولا صلاحية بلا زر.

وبلاغ سابق موثَّق: مدير الشركة اعتمد مرحلة مسؤول الفرع ثم مرحلته ثم مرحلة
HR بحسابه وحده. فلا يُعالَج «الأزرار مخفيّة» بإظهارها للجميع.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from . import models, permissions, workflow

#: نوع الخطوة ← الأفعال التي تُعرَض. الأسماء مشتقّة من نوع الخطوة لا من
#: مسمّى موحَّد: «اعتماد» في خطوة قرار ليس «صالح» في خطوة تحقّق، وعرضهما
#: بلفظ واحد يجعل من يتحقّق يظنّ أنه يقرّر.
ACTIONS_BY_STEP_TYPE: dict[str, list[str]] = {
    "DECISION": ["approve", "reject", "return"],
    "VALIDATION": ["valid", "invalid", "return"],
    "EXECUTION": ["start", "complete", "cannot_complete"],
    # P11-35 — **محسوم بقرار المالك**: الاعتراض يُسجَّل والمسار يكمل.
    #
    # كان ``dispute`` مربوًطا بـ``rejected``، أي أن اعتراض موظف على إنذار
    # يُسقط الطلب كلّه — فيُلغى الإنذار باعتراض من وُجّه إليه. وصار
    # مربوًطا بالتقدّم، والاعتراض يبقى مسجًَّلا في ``action``.
    #
    # ولا سلسلة تستعمل هذا النوع بعد (المراحل غير DECISION أربع، ثلاث
    # VALIDATION وواحدة إقرارات جهات). لكنه صار آمن الاستعمال يوم
    # يُستعمَل: معناه محسوم، لا مفاجأة فيه.
    "ACKNOWLEDGEMENT": ["acknowledge", "dispute"],
}

#: الفعل ← تسميته المعروضة. في مكان واحد فلا يختلف اللفظ بين شاشتين.
ACTION_LABELS: dict[str, dict[str, str]] = {
    "approve": {"ar": "اعتماد", "en": "Approve"},
    "reject": {"ar": "رفض", "en": "Reject"},
    "return": {"ar": "إرجاع للتصحيح", "en": "Return for Correction"},
    "valid": {"ar": "البيانات صحيحة", "en": "Valid"},
    "invalid": {"ar": "البيانات غير صحيحة", "en": "Invalid"},
    "start": {"ar": "بدء التنفيذ", "en": "Start"},
    "complete": {"ar": "تمّ التنفيذ", "en": "Complete"},
    "cannot_complete": {"ar": "تعذّر التنفيذ", "en": "Cannot Complete"},
    "acknowledge": {"ar": "علمت", "en": "Acknowledge"},
    "dispute": {"ar": "اعتراض", "en": "Dispute"},
}

#: الفعل ← القرار الذي يُرسَل إلى ``/decide``. الواجهة لا تترجم أفعاًلا إلى
#: قرارات بنفسها: ترجمة في الواجهة تعني قاعدة ثانية تنحرف.
#:
#: P11-35 — **وهذه الخريطة أثرٌ على المسار لا معًنى**. ثلاث قيم يفرّع
#: عليها المحرّك، وتسعة أفعال تنهار إليها: من ضغط «البيانات صحيحة» أو
#: «تمّ التنفيذ» أو «علمت» كان يُسجَّل «اعتمد» وانتهى الأمر. وفي نزاع
#: عمّالي «اعتمدت الشؤون القانونية الخصم» دعوى غير «تحقّقت من الأرقام».
#:
#: فلم تُوسَّع القيم — توسيعها يكسر كل تفريع في المحرّك — بل صار الفعل
#: يُحفَظ إلى جانب أثره في ``RequestApproval.action``، ويُعرَض بلفظه.
ACTION_DECISION: dict[str, str] = {
    "approve": "approved", "valid": "approved", "complete": "approved",
    "acknowledge": "approved",
    "reject": "rejected", "invalid": "rejected", "cannot_complete": "rejected",
    # **قرار المالك**: اعتراض الموظف يُسجَّل والمسار يكمل.
    #
    # كان مربوًطا بـ``rejected`` — أي أن اعتراض موظف على إنذار **يُسقط
    # الطلب كلّه**. فيُلغى الإنذار باعتراض من وُجّه إليه، ولا يبقى منه
    # أثر يُراجَع.
    #
    # و``decision`` أثرٌ على المسار لا حكم على المضمون (P11-35): قيمته
    # هنا «تقدَّم» لأن المرحلة تمّت — والموظف ردّ. أما **ما فعله** فيبقى
    # ``action="dispute"``، ويُعرض بلفظه «اعتراض» في الشاشة والخطّ
    # الزمني. فالاعتراض مسجَّل والمسار ماضٍ، وهو ما يطابق النصّ الرسمي
    # للنوع: «استلام الإنذار لا يعني الإقرار بصحته».
    "dispute": "approved",
    "return": "returned",
}

#: الإرجاع للتصحيح متاح في المراحل الأولى فقط: بعد قطع الطلب شوًطا يصير
#: إرجاعه إلى مقدّمه إلغاءً لقرارات اتُّخذت قبله.
RETURN_MAX_STAGE = 2

#: يُقرأ من المحرّك فلا تتباعد قائمتان لنفس الصلاحية.
from .workflow import APPLY_RETRY_ROLES as _RETRY_ROLES  # noqa: E402


def allowed_actions(db: Session, req: models.Request,
                    user: models.User | None) -> list[dict]:
    """الأفعال التي يملكها هذا المستخدم على هذا الطلب الآن.

    قائمة فارغة تعني: لا شيء يُعرَض. وهي الحالة الصحيحة لغير المعيَّن —
    لا رسالة صامتة ولا زر مُعطَّل يوحي بأن الأمر ممكن.
    """
    if user is None or req.status != "pending":
        return []

    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    chain = workflow._chain(rt, req)
    if not (0 <= req.current_stage < len(chain)):
        return []
    stage = chain[req.current_stage]

    # الشرط الأول: هل هو معتمِد هذه المرحلة أصًلا؟ (يمنع الاعتماد الذاتي
    # والتسلسل بحساب واحد)
    try:
        if not workflow.can_decide(db, req, user, stage, rt=rt):
            return []
    except Exception:
        return []

    # الشرط الثاني: هل يملك صلاحية مجال هذه الفئة؟ — نفس الفحص الذي
    # يُجريه /decide، لا نسخة منه.
    from .deps import get_user_perms

    step_type = stage.get("step_type") or "DECISION"
    if not permissions.can_complete_stage(user.role, get_user_perms(user, db),
                                          rt.category if rt else None, step_type):
        return []

    names = list(ACTIONS_BY_STEP_TYPE.get(step_type, ACTIONS_BY_STEP_TYPE["DECISION"]))
    if "return" in names and req.current_stage >= RETURN_MAX_STAGE:
        names.remove("return")

    return [{"action": a,
             "decision": ACTION_DECISION[a],
             "label_ar": ACTION_LABELS[a]["ar"],
             "label_en": ACTION_LABELS[a]["en"]}
            for a in names]


def why_not(db: Session, req: models.Request, user: models.User | None) -> str | None:
    """سبب عدم وجود أفعال — للعرض بدل الإخفاء الصامت.

    من ينتظر دوره يحتاج أن يعرف أنه ينتظر، لا أن يظنّ الشاشة معطَّلة.
    """
    if user is None:
        return None
    # P11-34 — حالة تحتاج إجراًء تقول ما هو، ومن يملكه.
    #
    # ``apply_failed`` لافتتها «فشل التطبيق — يحتاج إجراء»، وكانت
    # ``allowed_actions`` فارغة و``no_actions_reason`` فارًغا: شاشة صامتة
    # أمام طلب معتمَد لم يقع أثره. من يقرأها يظنّ الطلب ماضًيا في طريقه.
    if req.status == "apply_failed":
        if user.role in _RETRY_ROLES:
            return ("لم يُطبَّق أثر هذا الطلب بعد اعتماده. صحّح سبب الفشل "
                    "ثم أعد التطبيق.")
        return ("لم يُطبَّق أثر هذا الطلب بعد اعتماده — الشؤون القانونية "
                "مُبلَّغة وتتولّى تصحيحه.")
    if req.status != "pending":
        return None
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    chain = workflow._chain(rt, req)
    if not (0 <= req.current_stage < len(chain)):
        return "حالة الطلب غير متناسقة — أعد فتحه."
    stage = chain[req.current_stage]
    if user.employee_id and req.employee_id == user.employee_id:
        return "لا يجوز اعتماد طلبك بنفسك."
    try:
        if not workflow.can_decide(db, req, user, stage, rt=rt):
            return "هذا الطلب ينتظر اعتماد جهة أخرى — لست الموافق الحالي في هذه المرحلة."
    except Exception:
        return "تعذّر تحديد المعتمِد الحالي."
    from .deps import get_user_perms

    step_type = stage.get("step_type") or "DECISION"
    if not permissions.can_complete_stage(user.role, get_user_perms(user, db),
                                          rt.category if rt else None, step_type):
        need = permissions.decision_permission(rt.category if rt else None)
        return f"أنت الموافق الحالي لكن تنقصك صلاحية «{need}» لهذه الفئة."
    return None
