# -*- coding: utf-8 -*-
"""ساعُة المضيف على ورٍق رسمي — عطٌل يعمل في بيئٍة ويصمت في أخرى.

**القياس، ثم تصحيُح القياس مرتين:**

أوًّلا بدا النظاُم يحمل ثالثَة أعراٍف لـ«الآن» في ستَّة عشر ملًفا: ``now()``
و``now(timezone.utc)`` و``clock.now()``. **ثم فُرِّق بين نوعين من
«العارية»**: ``datetime.utcnow()`` عاريٌة لكنّ ساعتها UTC فتتّفق مع
افتراض النظام (أحَد عشر موضًعا يقرأ المحفوَظ ويختمه UTC صراحًة)، و
``datetime.now()`` تحمل **ساعَة المضيف** وهي وحدها الخطر. فنزل العدُد من
ثالثٍة وأربعين إلى **ثالثَة عشر**.

**وأسوأُها موضٌع واحد**: ``templates.py`` يبني بيانات المستند الرسمي، و
``date_today`` في القاموس نفسه يُقرأ من ``kuwait_today()`` — ورقُم
الإشارة كان يُقرأ من ساعة المضيف. فبين منتصف الليل والثالثة فجًرا بتوقيت
الكويت، والخادُم على UTC، يحمل المستنُد **تاريَخ يوٍم ورقَم إشارٍة بتاريخ
يوٍم قبله**. ساعتان على ورقٍة واحدة — وهو ما بُني ``clock.py`` لأجله
بنصّه: «النظام يحمل ساعتين».

**وثانيها**: لحظاُت ``Task`` (``completed_at`` · ``claimed_at`` ·
``last_delivery_at``) كانت بساعة المضيف، و``sla_scan`` يقرأ لحظات المهمة
**ويختمها UTC**. فالكاتُب والقارئ بساعتين.

**وما تُرك بعلّته**: ``break_glass`` و``admin`` يكتبان ويقارنان بساعة
المضيف **معًا** — زوٌج متّسٌق داخلًيا، وتغييُر أحد طرفيه هو ما يصنع العطل.
و``requests.printed_at``/``filed_at`` تُعرَض ولا تُقارَن.

و``scripts/naive_clocks.py`` يُطبِع ما بقي لمن يراجع — **ولا يُجعَل حارًسا
يُفشِل السويت**: السويُت تجري في بيئٍة واحدة فالعرفان يتّفقان فيها، وحاٌرس
يسقط على أربعين موضًعا معقول حاٌرس يُحذَف.
"""
from __future__ import annotations

import inspect
import re


def test_the_official_reference_number_uses_the_kuwait_day():
    """**جوهر البند**: ال ساعتان على ورقٍة واحدة."""
    from app.routers import templates as T

    src = inspect.getsource(T)
    # **وللاسم نفسه موضعان**: تسميٌة («رقم المرجع») وسطُر البيانات. فيُنتقى
    # بما يميّزه — الموضُع الذي يبني القيمة من الشركة والموظف.
    ref = [l for l in src.splitlines()
           if '"ref_no"' in l and "emp.company_id" in l]
    assert ref, "ذهب سطُر بناء رقم الإشارة"
    assert "kuwait_today" in ref[0], ref[0].strip()
    assert "datetime.now()" not in ref[0], ref[0].strip()


def test_the_document_date_and_its_reference_read_one_clock():
    """والتاريُخ ورقُم إشارته من مصدٍر واحد — يُقاسان معًا ال كلٌّ وحده."""
    from app.routers import templates as T

    src = inspect.getsource(T)
    block = src[src.index('"date_today"'):src.index('"probation_days"')]
    clocks = set(re.findall(r"kuwait_today|datetime\.now\(\s*\)", block))
    assert clocks == {"kuwait_today"}, clocks


def test_task_timestamps_are_written_with_the_clock_that_reads_them():
    """**والكاتُب والقارئ بساعٍة واحدة.**

    ``sla_scan`` يقرأ لحظات المهمة **ويختمها UTC** صراحًة، فلحظٌة تُكتب
    بساعة المضيف تُقرأ على غير ما كُتبت.
    """
    from app import notifications as N
    from app.routers import tasks as T

    reader = inspect.getsource(N.sla_scan)
    assert "replace(tzinfo=timezone.utc)" in reader, \
        "افتراُض القياس: القارئ يختم المحفوظ UTC"

    src = inspect.getsource(T)
    for field in ("completed_at", "claimed_at", "last_delivery_at"):
        bad = [l for l in src.splitlines()
               if f"task.{field} = datetime.now()" in l]
        assert not bad, f"{field} ما زال بساعة المضيف: {bad}"


def test_the_storage_clock_rule_has_one_home():
    """والقاعدُة معلَنٌة في موضٍع واحد ال مفهومًة من االستعمال."""
    from app import clock

    assert clock._STORAGE_CLOCK_RULE == "UTC in storage, Kuwait on screen"
    assert "ثالثُة أعراٍف" in inspect.getsource(clock) or \
           "ثالثة أعراف" in inspect.getsource(clock)


def test_the_review_tool_separates_the_two_kinds_of_naive():
    """**وأداٌة ال تفرّق بين العاريتين تُبالغ ثالثة أضعاف.**

    فـ``utcnow()`` عاريٌة وساعتها UTC، و``now()`` ساعتها المضيف. وخلطُهما
    هو ما جعل القياَس األول يقول ثالثًة وأربعين والصواُب ثالثَة عشر.
    """
    import pathlib

    tool = (pathlib.Path(__file__).resolve().parents[1]
            / "scripts" / "naive_clocks.py")
    assert tool.exists(), "ذهبت أداُة المراجعة"
    body = tool.read_text(encoding="utf-8")
    assert "utcnow" in body, "األداُة ال تعرف العاريَة التي ساعتها UTC"
