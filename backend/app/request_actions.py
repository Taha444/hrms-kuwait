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
    # P11-36 — أفعال المراحل التي **تُنفَّذ ولا تُقرَّر**.
    "upload_signed_scan": {"ar": "رفع النسخة الموقّعة", "en": "Upload Signed Copy"},
    "upload_exit_permit": {"ar": "رفع إذن المغادرة", "en": "Upload Exit Permit"},
    "confirm_received": {"ar": "تسجيل استلام العامل", "en": "Confirm Receipt"},
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

#: P11-36 — مراحل **تُنفَّذ ولا تُقرَّر**: مخرجها عمٌل يقع، لا زرّ قرار.
#:
#: **العطل المقيس**: إجازة السفر تصل مرحلة المندوب فتقف. المندوب يرى في
#: صندوقه طلًبا و``allowed_actions: []`` و``no_actions_reason: ""`` —
#: شاشٌة صامتة لا فعل فيها ولا سبب. ثم إن ضغط «اعتماد» ردّه الخادم:
#: «هذه المرحلة تكتمل برفع إذن المغادرة لا بالاعتماد المباشر». فالخادم
#: يعرف المخرج، والشاشة لا تذكره.
#:
#: **والسبب** أن الدالتين أدناه تنصرفان عند ``status != "pending"``، وهذه
#: المراحل حالتها ``awaiting_delegate`` و``ready_for_pickup``. فكل ما
#: بُني في APP-01 — أن الشاشة تعرض ما يقبله الخادم — كان مقصوًرا على
#: القرارات، وسقط منه ما يُنفَّذ.
#:
#: و``via`` هو **كيف** يقع الفعل: ``decide`` قراٌر يُرسَل إلى ``/decide``،
#: و``upload`` مستنٌد يُرفَع، و``post`` نداٌء على مسار. والواجهة تقرأ هذا
#: ولا تخمّن: كان زرّ الاستلام مشروًطا بـ``approve_request`` — الصلاحية
#: الموصوفة في هذا الملف نفسه بأنها مهجورة — وحقل إذن المغادرة مشروًطا
#: بدور ``delegate`` نًصّا. وهو انحراف APP-01 عينه، معاًدا في مكان آخر.
#: ويُفتَرَس بالحالة لا بنوع المرحلة: ``awaiting_signature`` حاٌل **داخل**
#: مرحلة ``hr_review`` نفسها التي تقبل القرار قبلها — فالمفتاح الصادق هو
#: «ما تحتاجه هذه الحال كي تكتمل».
EXECUTION_ACTIONS_BY_STATUS: dict[str, dict] = {
    # ``self_forbidden`` — لا يُتمّ المرء توقيع طلبه. والراية هنا لأن
    # الشرط على الخادم أيًضا: لو عُرض الفعل ثم رُدّ، لعاد العطل مقلوًبا —
    # زٌر يُعرَض ويُردّ. أما إذن المغادرة فورقٌة تستخرجها الوزارة والمندوب
    # ساعٍ إليها لا مقرٌّ بها، فلا يُمنع منها في شركٍة مندوبها واحد.
    "awaiting_signature": {"action": "upload_signed_scan", "via": "upload",
                           "doc_kind": "signed_scan", "who": "signature",
                           "self_forbidden": True,
                           "executor": "شؤون الموظفين"},
    "awaiting_delegate": {"action": "upload_exit_permit", "via": "upload",
                          "doc_kind": "exit_permit", "who": "delegate",
                          "executor": "المندوب"},
    "ready_for_pickup": {"action": "confirm_received", "via": "post",
                         "path": "received", "who": "approval",
                         "executor": "شؤون الموظفين"},
}


def _may_execute(db: Session, user: models.User, who: str) -> bool:
    """هل يقبل الخادمُ من هذا المستخدم تنفيذ هذه الحال؟

    كل فرع أدناه يقرأ من موضع الشرط الأصلي: أي تعديل هناك يجب أن يُقرأ
    هنا، وإلا عادت الشاشة تعرض ما يُردّ أو تُخفي ما يُقبَل.
    """
    from .deps import get_user_perms

    if who == "delegate":
        # routers/requests.upload_request_document — kind="exit_permit"
        return user.role == "delegate" or user.role in workflow.CANCEL_ROLES
    if who in ("approval", "signature"):
        # routers/requests.mark_received — require_any_perm(*APPROVAL_PERMS)
        # وrouters/requests.upload_request_document — kind="signed_scan"
        assigned = get_user_perms(user, db)
        return any(permissions.check_legacy(user.role, assigned, perm)
                   for perm in permissions.APPROVAL_PERMS)
    return False


def execution_stage_hint(status: str | None) -> str | None:
    """ما تحتاجه هذه الحالة كي تكتمل — عبارٌة واحدة للشاشة وللمسار.

    P11-36 — كان في ``/decide`` ردٌّ يقول الحقيقة: «هذه المرحلة تكتمل
    برفع إذن المغادرة لا بالاعتماد المباشر». وكان **لا يُقرأ أبًدا**:
    الحارس الذي يشترط ``pending`` يسبقه، فيردّ 409 بعبارة «لا يمكن اتخاذ
    قرار في هذه الحالة» — وهي لا تقول ما الحال ولا ما يُفعل. فبقيت
    الجملة الصحيحة مكتوبًة في شيفرة لا يبلغها نداء.

    وهي هنا في موضع واحد: يقرأها ``no_actions_reason`` ويقرأها ردّ 409،
    فلا تنحرف إحداهما عن الأخرى.
    """
    spec = EXECUTION_ACTIONS_BY_STATUS.get(status or "")
    if spec is None:
        return None
    return (f"هذه المرحلة تكتمل بـ«{ACTION_LABELS[spec['action']]['ar']}» "
            f"من {spec['executor']} — لا بالاعتماد المباشر.")


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
    if user is None:
        return []

    # P11-36 — ما يُنفَّذ يُوصَف قبل شرط ``pending``: حالته ليست ``pending``
    # بحكم التصميم، فالشرط كان يُسكت هذه الحالات كلّها.
    spec = EXECUTION_ACTIONS_BY_STATUS.get(req.status)
    if spec is not None:
        if not _may_execute(db, user, spec["who"]):
            return []
        if spec.get("self_forbidden") and user.employee_id                 and req.employee_id == user.employee_id:
            return []
        a = spec["action"]
        out = {"action": a, "via": spec["via"], "decision": None,
               "label_ar": ACTION_LABELS[a]["ar"], "label_en": ACTION_LABELS[a]["en"]}
        for k in ("doc_kind", "path"):
            if k in spec:
                out[k] = spec[k]
        return [out]

    if req.status != "pending":
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
             "via": "decide",
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
    # P11-36 — مرحلٌة تُنفَّذ ولا يملكها هذا المستخدم: تقول من يملكها.
    # وكانت تسكت لأن حالتها ليست ``pending`` — فيقف المندوب أمام لا شيء.
    spec = EXECUTION_ACTIONS_BY_STATUS.get(req.status)
    if spec is not None:
        if spec.get("self_forbidden") and user.employee_id                 and req.employee_id == user.employee_id:
            return "لا يجوز إتمام توقيع طلبك بنفسك — يتولّاه غيرك."
        if _may_execute(db, user, spec["who"]):
            return None
        return execution_stage_hint(req.status)
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
