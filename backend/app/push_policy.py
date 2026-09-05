# -*- coding: utf-8 -*-
"""ما يستحقّ إشعاًرا فورًيا، وبأي نصّ يظهر على شاشة مقفلة.

**قراران منفصلان، وكلاهما يقع قبل أي اتصال بـFirebase**:

1. **هل يُدفَع أصًلا؟** — نظام يدفع كل شيء يُسكِته المستخدم بعد يومين،
   فيضيع معه المهمّ. والقاعدة: *لو لم يفعل شيًئا الآن، هل يتأخّر عمل أو
   يفوت موعد؟*

2. **ماذا يُكتب؟** — الإشعار الفوري يظهر على **شاشة القفل**، يقرؤه من
   يحمل الجهاز ولو لم يفتحه. فلا يحمل راتًبا ولا رقًما مدنًيا ولا اسم
   موظف في سياق تأديبي. يقول إن هناك ما يُراجَع، والتفصيل خلف تسجيل
   الدخول.

**ولماذا وحدة مستقلّة**: القراران منطق عمل خالص — يُقاسان ويُختبران بلا
مزوّد ولا شبكة ولا رمز جهاز. وخلطهما بالنقل يجعل صحّتهما رهينة توفّر
Firebase.

والفرز يُبنى على ``task_kinds`` القائم لا على قائمة ثانية: ما هو
«إشعار» هناك (يُقرأ ولا يُنفَّذ) لا يُدفَع هنا إلا استثناًء معلًَّلا.
"""
from __future__ import annotations

import re

from .task_kinds import NOTIFICATION_TYPES

#: يُدفَع فوًرا — عمل يتأخّر أو موعد يفوت إن لم يُرَ الآن.
PUSH_TYPES: dict[str, str] = {
    "request": "طلب ينتظر قرارك",
    "task": "مهمة مسندة إليك",
    "renewal": "معاملة تجديد تنتظر إجراءك",
    "renew_residency": "إقامة تقترب من الانتهاء",
    "doc_expiring": "مستند يقترب من الانتهاء",
    "license_expiring": "ترخيص يقترب من الانتهاء",
    "permit": "إذن عمل يحتاج متابعة",
    "appointment": "موعد محدَّد لك",
    "apply_failed": "قرار معتمَد لم يقع أثره",
    "config_gap": "إعداد ناقص يوقف مساًرا",
    "signature_replacement": "طلب استبدال توقيع ينتظر اعتمادك",
    "security": "تنبيه أمني",
    "capacity_exceeded": "تجاوز في الطاقة الاستيعابية",
    "job_failure": "مهمة مجدولة تعثّرت",
}

#: يُقرأ ولا يُدفَع — خبر لا إجراء، أو تجميعة دورية.
#:
#: و``request_update`` منها عمًدا: «اعتُمد طلبك» خبر يسرّ ولا يوقف عمًلا.
#: أما ``digest`` فملخّص يومي — دفعُه يعني إشعاًرا يومًيا ثابًتا، وهو
#: أسرع طريق إلى إسكات التطبيق كلّه.
NO_PUSH_TYPES: frozenset[str] = frozenset({
    "request_update", "digest", "sla_escalation", "ready_to_print",
})

#: مسار الفتح لكل كيان — من نوع الكيان لا من نصّ يُبنى في كل موضع.
DEEP_LINKS: dict[str, str] = {
    "request": "/requests/{id}",
    "renewal": "/renewals",
    "employee": "/employees/{id}",
    "eos_case": "/eos/cases",
    "document": "/archive",
    "task": "/tasks",
}

#: ما لا يُكتب على شاشة قفل: أرقام تُقرأ كمبالغ أو هويّات.
#:
#: والقياس على **الشكل** لا على أسماء الحقول: النصّ يصل جاهًزا من مئات
#: المواضع، ولا يُعرف أيّ رقم فيه راتب. فيُعتَّم كل ما يشبه مبلًغا أو
#: رقًما مدنًيا أو رقم جواز.
_CIVIL_ID = re.compile(r"\b\d{12}\b")
_PASSPORT = re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")
_MONEY = re.compile(r"\b\d{1,3}(?:[,،]\d{3})*(?:\.\d{1,3})?\s*(?:د\.?ك|KWD|دينار)")
_LONG_NUM = re.compile(r"\b\d{7,}\b")


def should_push(kind: str | None) -> bool:
    """هل يستحقّ هذا النوع إشعاًرا فورًيا؟

    والافتراض **لا**: نوع يُضاف غًدا لا يبدأ بإزعاج الناس حتى يُدرَج
    عن قصد. وقائمة يُدفَع فيها كل ما ليس ممنوًعا تنمو بلا مراجعة.
    """
    k = (kind or "").strip()
    if not k or k in NO_PUSH_TYPES:
        return False
    return k in PUSH_TYPES


def headline(kind: str | None) -> str:
    """عنوان الإشعار الفوري — من النوع لا من نصّ الإشعار الداخلي.

    نصّ الإشعار الداخلي مكتوب لمن فتح النظام وسجّل دخوله، فقد يحمل
    اسًما أو رقًما. والعنوان هنا **ثابت لكل نوع**، فلا يتسرّب منه شيء
    مهما تغيّر النصّ الداخلي.
    """
    return PUSH_TYPES.get((kind or "").strip(), "تحديث يحتاج مراجعتك")


def redact(text: str | None) -> str:
    """يحذف ما لا يصحّ ظهوره على شاشة مقفلة.

    ولا يُعاد بناء النصّ من الصفر: يُعتَّم ما يشبه المبالغ والهويّات
    ويبقى الباقي، فيظلّ الإشعار مفيًدا («طلب #120 يحتاج قرارك») بلا أن
    يكشف رقًما.
    """
    t = (text or "").strip()
    if not t:
        return ""
    t = _MONEY.sub("•••", t)
    t = _CIVIL_ID.sub("•••", t)
    t = _PASSPORT.sub("•••", t)
    t = _LONG_NUM.sub("•••", t)
    return t[:120]


def deep_link(entity_type: str | None, entity_id: int | None) -> str:
    """أين تفتح الضغطة — مسار داخل النظام لا رابط خارجي."""
    tpl = DEEP_LINKS.get((entity_type or "").strip())
    if not tpl:
        return "/tasks"
    return tpl.format(id=entity_id) if entity_id else tpl.split("/{")[0]


def build(kind: str | None, title: str | None, body: str | None,
          entity_type: str | None = None,
          entity_id: int | None = None) -> dict | None:
    """حمولة الإشعار الفوري، أو ``None`` إن كان لا يُدفَع.

    القرار والتعتيم في موضع واحد: من يبني حمولة بنفسه في مكان آخر
    يتجاوز القاعدتين مًعا.
    """
    if not should_push(kind):
        return None
    return {
        "title": headline(kind),
        "body": redact(body or title),
        "link": deep_link(entity_type, entity_id),
        "kind": (kind or "").strip(),
    }
