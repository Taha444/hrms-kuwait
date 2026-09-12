# -*- coding: utf-8 -*-
"""عموٌد يُعلَن ولا يُكتب — مخطٌَّط يعِد بحفٍظ لا يُوفى.

**القياس**: كلُّ عموٍد في النماذج، هل يذكره شيٌء خارج ``models.py``؟
ثمانيٌة لا. وعموٌد يبقى ``NULL`` دائًما وله اسٌم ذو معنى **فٌّخ**: من
يستعلم عنه يجده فارًغا فيستنتج أن البيان لم يُجمَع، وقد جُمع في موضٍع
آخر — أو لم يُجمَع قط والمخطَُّط يوهم أنه يُجمَع.

**وأثقلُها كان دليًلا مفقوًدا**: ``AttendanceRecord.in_lat`` و``in_lng``
و``out_lat`` و``out_lng``. فـ``validate-qr`` يستقبل إحداثيات الموظف
ويفحص بها السياج الجغرافي، **ثم يُلقيها** — والسجلُّ يُنشأ في نداٍء آخر
(``check-in``) لا يستقبلها. فمن نازع في حضوره لا يجد ما يُحتَجّ به له ولا
عليه، وقراُر السياج نفسه لا يُعاد بناؤه.

وتُحمَل الآن في **التذكرة الموقَّعة**: فما يُخزَّن هو ما مرّ بالسياج. ولو
استُقبلت ثانيًة في ``check-in`` أمكن إرسال موضٍع غير الذي أُقِرّ.

**وأربعٌة تُركت بعلّتها لا سهًوا** — ويُحرَس أنها ما زالت كذلك:

- ``Request.cancelled_at`` و``cancel_reason``: ``workflow.cancel`` تكتب
  ``closed_at`` وتُنشئ صفَّ ``RequestApproval`` بعنوان «إلغاء المدير
  العام» وملاحظته. فملؤهما يجعل للحقيقة الواحدة موضعين ينحرفان.
- ``Request.needs_info_note``: ``needs_info`` فعٌل معلٌن في ``v15_status``
  **ولا يُنفَّذ**؛ المنفَّذ ``returned``. فهو توأُم فعٍل لم يُبنَ.
- ``Task.escalation_task_id``: عمٌود مبٌنّي على فرٍض لا يقع —
  ``notify_roles`` تُنشئ مهمًة **لكل مستقبِل**، فمفتاٌح أجنبٌي واحد لا
  يحمل رابًطا متفرًّعا. والرابُط القائم بادئُة
  ``sla_escalation:{task.id}:``.

**وواحٌد صحَّ فمُلئ**: ``Task.escalated_at`` — علامٌة ذات معنى على المهمة
الأصلية، فمن يقرؤها يعرف أنها صُعِّدت ومتى.
"""
from __future__ import annotations

import pathlib
import re

import pytest
from sqlalchemy import select

from app import models
from app.database import SessionLocal

BACK = pathlib.Path(__file__).resolve().parents[1] / "app"

#: أعمدٌة تبقى فارغًة **بعلّتها** — تُسمّى صراحًة فلا يمرّ عموٌد جديد
#: صامًتا في ظلّها.
_SUPERSEDED = {
    ("Request", "cancelled_at"): "closed_at + صفُّ قرار الإلغاء",
    ("Request", "cancel_reason"): "ملاحظُة قرار الإلغاء",
    ("Request", "needs_info_note"): "فعٌل معلٌن ولم يُبنَ — المنفَّذ returned",
}

#: و``Task.escalation_task_id`` **ليس في هذه القائمة بقصد**: الكنُس
#: يستثني كلَّ عموٍد ينتهي بـ``_id`` (وإلا لأنذر على كل مفتاٍح أجنبّي
#: يُستعمل بالعالقات لا باسمه). فنصفا القياس يتناقضان لو أُدرِج فيها.
#: ويحرسه بدله ``test_the_escalation_link_is_the_dedup_prefix`` —
#: وحاٌرس مخصٌَّص أدقُّ من قائمٍة لا يمسّها الكنس.


def _code_only(text: str) -> str:
    """الشيفرُة بلا تعليقات.

    **وقد خُدع هذا القياس بشرٍح كُتب عن العمود نفسه**: سطٌر يشرح لماذا
    ``escalation_task_id`` منسوٌخ جعل العمود «مذكوًرا». والمقصود أن
    **تقرأه شيفرة** لا أن يسمّيه نص — فتُسقَط التعليقاُت قبل البحث.
    """
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        out.append(line.split("  # ")[0])
    return chr(10).join(out)


#: **وقياٌس يُعاد بناؤه لكل اختبار كلفٌة بال فائدة.** الشجرُة نفسها
#: تُقرأ، فتُقرأ مرًة: اختباران هنا كانا يمشيان على الخادم والواجهة
#: معًا (~2.3 ثانية لكل منهما).
_CACHE: list[tuple[str, str]] | None = None


def _unmentioned() -> list[tuple[str, str]]:
    """أعمدٌة لا **تقرؤها شيفرٌة** خارج ``models.py``."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    blob = "".join(_code_only(p.read_text(encoding="utf-8", errors="ignore"))
                   for p in BACK.rglob("*.py") if p.name != "models.py")
    front = BACK.parents[1] / "frontend" / "src"
    if front.exists():
        blob += "".join(_code_only(p.read_text(encoding="utf-8", errors="ignore"))
                        for p in front.rglob("*.ts*"))
    out = []
    for m in models.Base.registry.mappers:
        cls = m.class_.__name__
        for c in m.local_table.columns:
            n = c.name
            if n == "id" or n.endswith("_id"):
                continue
            if not re.search(rf"\b{re.escape(n)}\b", blob):
                out.append((cls, n))
    _CACHE = out
    return out


def test_no_new_column_is_declared_and_never_written():
    """**الحارس الدائم**: لا عموَد يُعلَن ثم لا يذكره شيء.

    ومن أراد عموًدا منسوًخا سمّاه في ``_SUPERSEDED`` بما يحمل الحقيقَة
    بدله — فقراٌر مكتوٌب يُراجَع، وعموٌد منسٌّي لا.
    """
    stray = [x for x in _unmentioned() if x not in _SUPERSEDED]
    assert not stray, "أعمدٌة تُعلَن ولا يذكرها شيء:\n" + "\n".join(
        f"  {c}.{n}" for c, n in stray)


def test_every_declared_superseded_column_is_still_unused():
    """وعموٌد صار يُقرأ لم يبقَ منسوًخا — فيُرفَع من القائمة."""
    live = set(_unmentioned())
    revived = sorted(k for k in _SUPERSEDED if k not in live)
    assert not revived, f"أعمدٌة صار يذكرها شيء: {revived}"


# ---------------------------------------------------------------------------
# ودليُل الموضع يُحفَظ
# ---------------------------------------------------------------------------

def test_the_ticket_carries_the_position_the_fence_approved():
    """**جوهر البند**: ما يُخزَّن هو ما مرّ بالسياج."""
    from app import qr_token

    token, _exp = qr_token.make_checkin_ticket(7, 3, 29.3759, 47.9774)
    payload = qr_token.decode(token, "checkin_ticket")
    assert payload["lat"] == pytest.approx(29.3759)
    assert payload["lng"] == pytest.approx(47.9774)


def test_a_ticket_without_a_position_still_works():
    """**ولا تُكسَر تذكرٌة في الطريق**: ما صدر قبل هذا يبقى صالًحا."""
    from app import qr_token

    token, _exp = qr_token.make_checkin_ticket(7, 3)
    payload = qr_token.decode(token, "checkin_ticket")
    assert "lat" not in payload and "lng" not in payload
    assert int(payload["employee_id"]) == 7


def test_the_record_stores_the_position_from_the_ticket():
    """والسجلُّ يقرأ الموضَع من التذكرة لا من العميل.

    فقبوٌل ثاٍن من العميل يسمح بإرسال موضٍع غير الذي أُقِرّ.
    """
    import inspect

    from app.routers import attendance as A

    src = inspect.getsource(A.check_in)
    assert 'in_lat=payload.get("lat")' in src, "الموضُع لا يُحفَظ عند الحضور"
    assert 'payload.get("lat")' in src.split("action == out")[-1] or \
           "rec.out_lat" in src, "الموضُع لا يُحفَظ عند الانصراف"
    # ولا يُقبَل من جسم الطلب مرًة أخرى.
    assert "lat: float" not in inspect.signature(A.check_in).__str__()


def test_the_fence_still_decides_on_what_it_was_given():
    """**والحفُظ لا يُبدِّل الحكم**: السياُج يفحص كما كان."""
    import inspect

    from app.routers import attendance as A

    src = inspect.getsource(A.validate_qr)
    assert "_check_geofence(emp, branch, data.lat, data.lng)" in src


# ---------------------------------------------------------------------------
# وعلامُة التصعيد
# ---------------------------------------------------------------------------

def test_an_escalated_task_carries_the_moment_it_was_escalated():
    """**ومهمٌَّة صُعِّدت تحمل أثر تصعيدها** — لا سلسلًة نصّية وحدها."""
    import inspect

    from app import notifications as N

    assert "task.escalated_at = now" in inspect.getsource(N.sla_scan), \
        "التصعيد لا يترك علامًة على المهمة الأصلية"


def test_the_escalation_link_is_the_dedup_prefix():
    """والرابُط المتفرّع يبقى في بادئة البصمة — لا يُملأ عمٌود بنصف حقيقة."""
    import inspect

    from app import notifications as N

    src = inspect.getsource(N.sla_scan)
    assert 'f"sla_escalation:{task.id}:"' in src
    # ولا **يُسنَد** إليه — وذكرُه في شرٍح يوضّح لماذا لا يُسنَد مطلوب.
    assert "escalation_task_id =" not in src, \
        "مفتاٌح أجنبٌي واحد لا يحمل تصعيًدا يتفرّع على عدّة مستقبلين"
