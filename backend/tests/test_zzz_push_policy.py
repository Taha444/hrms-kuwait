# -*- coding: utf-8 -*-
"""ما يستحقّ إشعاًرا فورًيا، وبأي نصّ يظهر على شاشة مقفلة.

قراران يقعان **قبل** أي اتصال بـFirebase، فيُقاسان بلا مزوّد ولا شبكة
ولا رمز جهاز. وخلطهما بالنقل يجعل صحّتهما رهينة توفّر خدمة خارجية.

**الأول**: نظام يدفع كل شيء يُسكِته المستخدم بعد يومين فيضيع معه
المهمّ. **والثاني**: الإشعار الفوري يظهر على شاشة القفل، يقرؤه من يحمل
الجهاز ولو لم يفتحه — فلا يحمل راتًبا ولا رقًما مدنًيا.
"""
from __future__ import annotations

from app import push_policy as P
from app.task_kinds import NOTIFICATION_TYPES


def test_the_default_is_silence():
    """**الافتراض لا**: نوع يُضاف غًدا لا يبدأ بإزعاج الناس.

    قائمة يُدفَع فيها كل ما ليس ممنوًعا تنمو بلا مراجعة — فتصير كل
    إضافة إشعاًرا على هاتف كل موظف.
    """
    assert P.should_push("نوع_لم_يوجد_بعد") is False
    assert P.should_push(None) is False
    assert P.should_push("") is False


def test_work_that_waits_is_pushed():
    """وما يوقف عمًلا يُدفَع: طلب ينتظر قراًرا، ومهمة مسندة، وإقامة تنتهي."""
    for kind in ("request", "task", "renew_residency", "apply_failed"):
        assert P.should_push(kind), kind


def test_news_and_digests_are_not_pushed():
    """وما يُقرأ ولا يُنفَّذ لا يُدفَع.

    و«اعتُمد طلبك» خبر يسرّ ولا يوقف عمًلا. أما الملخّص اليومي فدفعُه
    يعني إشعاًرا يومًيا ثابًتا — أسرع طريق إلى إسكات التطبيق كلّه.
    """
    for kind in ("request_update", "digest", "sla_escalation"):
        assert not P.should_push(kind), kind


def test_the_split_agrees_with_the_existing_catalogue():
    """**ولا قائمة ثانية**: ما هو «إشعار» في ``task_kinds`` لا يُدفَع.

    قائمتان لقاعدة واحدة تنحرف إحداهما — وهو النمط الذي تكرّر في هذه
    الجولة أكثر من مرّة.
    """
    pushed_but_read_only = {k for k in P.PUSH_TYPES if k in NOTIFICATION_TYPES}
    assert not pushed_but_read_only, (
        f"أنواع تُقرأ ولا تُنفَّذ ومع ذلك تُدفَع: {sorted(pushed_but_read_only)}"
    )


def test_the_headline_never_comes_from_the_message_body():
    """العنوان من **النوع** لا من نصّ الإشعار الداخلي.

    النصّ الداخلي مكتوب لمن سجّل دخوله فقد يحمل اسًما أو رقًما. وعنوان
    مشتقّ منه يتسرّب مع أول قالب يتغيّر.
    """
    leaky = "راتب أحمد 500 د.ك عُدِّل — الرقم المدني 288001234567"
    payload = P.build("request", leaky, leaky, "request", 120)
    assert payload is not None
    assert "أحمد" not in payload["title"], payload["title"]
    assert payload["title"] == P.PUSH_TYPES["request"]


def test_money_and_identifiers_are_redacted():
    """**ما لا يُكتب على شاشة قفل**: مبالغ وهويّات."""
    out = P.redact("راتب 1,250.500 د.ك للرقم المدني 288001234567 جواز A1234567")
    for leak in ("1,250.500", "288001234567", "A1234567"):
        assert leak not in out, f"تسرّب «{leak}»: {out}"
    assert "•••" in out


def test_redaction_keeps_the_message_useful():
    """ولا يُمحى النصّ كلّه: إشعار بلا معًنى لا يُفتَح.

    التعتيم يستهدف ما يشبه المبالغ والهويّات ويُبقي الباقي — فيظلّ
    «طلب #120 يحتاج قرارك» مفهوًما.
    """
    out = P.redact("طلب #120 يحتاج قرارك")
    assert "120" in out, out
    assert "قرارك" in out


def test_the_body_is_bounded():
    """وطول محدود: شاشة القفل تقصّ، والقصّ الأعمى يقطع في منتصف كلمة."""
    assert len(P.redact("ا" * 500)) <= 120


def test_the_link_opens_the_thing_itself():
    """والضغطة تفتح ما يخصّها لا الصفحة الرئيسة."""
    assert P.deep_link("request", 120) == "/requests/120"
    assert P.deep_link("employee", 7) == "/employees/7"
    # وكيان لا مسار له يفتح صندوق المهام — لا صفحة فارغة ولا خطأ.
    assert P.deep_link("لا_يوجد", 3) == "/tasks"
    assert P.deep_link(None, None) == "/tasks"


def test_build_returns_nothing_for_what_must_not_be_pushed():
    """**والقرار والتعتيم في موضع واحد**: من يبني حمولة بنفسه يتجاوزهما."""
    assert P.build("digest", "ملخّص", "٣ مهام", "task", None) is None
    assert P.build("request_update", "تم الاعتماد", "طلبك", "request", 5) is None


def test_a_pushed_payload_carries_everything_the_device_needs():
    """وما يُدفَع يحمل عنواًنا ونًصا ومساًرا — لا حقل ناقص يُملأ في النقل."""
    p = P.build("renew_residency", "تجديد", "إقامة الموظف تنتهي خلال ٧ أيام",
                "renewal", 9)
    assert p and set(p) == {"title", "body", "link", "kind"}
    assert all(p[k] for k in ("title", "body", "link", "kind"))
