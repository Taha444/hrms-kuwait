# -*- coding: utf-8 -*-
"""P4-22 — خطّ زمن التجديد يحكي القصة، لا عناوين عامّة.

**ما كان**: ثمانية أحداث، أحدها ``renewal_upload`` يمرّ به **ستة**
مستندات مختلفة — العقد المولَّد، ونسخة الموظف الموقّعة، والنسخة
النهائية، وإذن العمل، والبطاقة المدنية. فمن يقرأ الخطّ بعد شهور يرى
«رُفع مستند» ست مرّات ولا يعرف أيّها كان.

والكود مسجَّل في ``detail`` منذ البداية — الناقص أن يُقرأ.

**وقراءة المستند لم تكن تُسجَّل إطلاًقا**: النتيجة تُحفَظ في المستند
ولا تدخل السجلّ. فيُقرأ «رُفعت البطاقة» ثم «سُجّلت البيانات»، ولا يُعرف
هل قرأها النظام أم أُدخلت يدًوا ولا بأي ثقة. وهو ما تحرسه القاعدة 14:
لا تحديث صامت عند ضعف الثقة — والصمت في السجلّ نصف التحديث الصامت.
"""
from __future__ import annotations

from app import renewal as RN
from app.routers import renewals as R


def test_every_upload_kind_has_its_own_line():
    """ستة مستندات لا تُروى بسطر واحد."""
    kinds = {RN.DOC_CONTRACT_GOV, RN.DOC_SIGNED_GOV, RN.DOC_CONTRACT_FINAL,
             RN.DOC_WORK_PERMIT, RN.DOC_CIVIL_CARD}
    missing = [k for k in kinds if k not in R.UPLOAD_LABELS]
    assert not missing, f"مستندات بلا تسمية في الخطّ: {missing}"


def test_the_upload_labels_are_distinct():
    """وتسميات متطابقة لا تفرّق شيًئا."""
    labels = [R.UPLOAD_LABELS[k] for k in R.UPLOAD_LABELS]
    assert len(set(labels)) == len(labels), "تسميات مكرَّرة بين المستندات"


def test_the_label_resolver_uses_the_detail():
    """**جوهر الإصلاح**: التفصيل يُقرأ ولا يُهمَل."""
    generic = R.TIMELINE_LABELS["renewal_upload"]
    specific = R._timeline_label("renewal_upload", RN.DOC_SIGNED_GOV)
    assert specific != generic, "الرفع ما زال يُروى بالعنوان العامّ"
    assert "الموظف" in specific, specific


def test_an_unknown_detail_falls_back_to_the_generic_label():
    """وما لا يُعرف يُروى بالعامّ لا بالفراغ."""
    assert R._timeline_label("renewal_upload", "شيء-غير-معروف") == \
        R.TIMELINE_LABELS["renewal_upload"]
    assert R._timeline_label("renewal_upload", None) == \
        R.TIMELINE_LABELS["renewal_upload"]


def test_other_actions_are_unaffected():
    """ولم يُكسر ما كان يعمل."""
    for action in ("create_renewal", "hr_verify_renewal", "renewal_rejected"):
        assert R._timeline_label(action, "أي تفصيل") == R.TIMELINE_LABELS[action]


def test_document_reading_is_an_event_in_the_story():
    """قراءة المستند تُسجَّل — القاعدة 14 تبدأ من أن يُعرف أنها وقعت."""
    assert "renewal_ocr_read" in R.TIMELINE_LABELS, (
        "قراءة المستند بلا تسمية في الخطّ"
    )


def test_every_recorded_action_has_a_label():
    """**الادّعاء الجامع**: كل ما يُكتب في التدقيق له سطر مقروء.

    حدث بلا تسمية يظهر بكوده التقني في وجه القارئ — وهو تسرّب قيمة
    داخلية بالمعنى نفسه الذي عولج في بنود التسميات.
    """
    import re
    from pathlib import Path

    src = Path(R.__file__).read_text(encoding="utf-8")
    actions = set(re.findall(r'audit\(db, [^,]+, "([a-z_]+)"', src))
    assert actions, "لم تُقرأ أفعال التدقيق — راجع الفحص"
    unlabelled = [a for a in actions if a not in R.TIMELINE_LABELS]
    assert not unlabelled, (
        f"أفعال تُسجَّل ولا تُروى: {sorted(unlabelled)}"
    )


def test_the_story_is_richer_than_it_was():
    """والقياس على العدد أيًضا: ثمانية عامّة صارت ستة عشر متمايًزا."""
    distinct = len(set(R.TIMELINE_LABELS.values()) | set(R.UPLOAD_LABELS.values()))
    assert distinct >= 15, f"الخطّ ما زال فقيًرا: {distinct} سطًرا متمايًزا"
