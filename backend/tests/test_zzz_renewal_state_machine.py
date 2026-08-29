# -*- coding: utf-8 -*-
"""RNW-D3 — لا حالة بلا مخرج، في آلة الحالات كلها.

القفلة عند ``pending_hr_verify`` (RNW-D1/D2) لم تكن حالة شاذّة بل عرًضا:
**الانتقالات بلا شروط دخول واضحة**. فُحصت واحدة وأُصلحت، ويبقى السؤال
لكل حالة أخرى.

**ولماذا فحص آلي لا مراجعة مكتوبة**: المراجعة تصحّ يوم كُتبت. وحالة
تُضاف بعد شهر لا تمرّ عليها. فالفحص يقرأ آلة الحالات نفسها من الشيفرة،
ويسقط يوم تُضاف حالة بلا مخرج — لا يوم يتذكّر أحد أن يراجع.

القاعدة: **كل حالة غير نهائية لها مخرج واحد على الأقل، لفاعل موجود.**
"""
from __future__ import annotations

import re
from pathlib import Path

from app import renewal as R
from app.routers.renewals import STAGE_ACTOR, STAGE_TASK_PREFIX

SOURCE = Path(__file__).resolve().parents[1] / "app" / "routers" / "renewals.py"

#: الحالات التي لا يُطلب منها مخرج — نهاية الطريق.
TERMINAL = {R.COMPLETED, R.REJECTED}

#: كل حالات المحرّك، من الوحدة نفسها لا من قائمة تُكتب هنا وتنسى.
ALL_STATES = set(R.STATUS_LABELS)


def _assignments_in_source() -> set[str]:
    """الحالات التي تُسنَد فعًلا في الشيفرة — أي التي يمكن الوصول إليها.

    يُقرأ ``rn.status = R.X`` من النصّ: قائمة تُكتب يدوًيا تنحرف عن
    الشيفرة أول تعديل.
    """
    text = SOURCE.read_text(encoding="utf-8")
    names = []
    for line in text.splitlines():
        # الإسناد قد يكون شرطًيا في سطر واحد:
        #   rn.status = R.PENDING_HR if ... else R.AWAITING_CONTRACTS
        # وقد يكون على متغيّر يُمرَّر للإنشاء:  status = R.PENDING_MANAGER
        # فقراءة أول اسم بعد «=» تُسقط نصف الانتقالات وتُبلّغ عن حالات
        # حيّة كأنها ميتة — أداة تكذب أسوأ من غيابها.
        if re.search(r"(?:rn\.)?status\s*=(?!=)", line):
            names += re.findall(r"R\.([A-Z_]+)", line)
    return {getattr(R, n) for n in names if hasattr(R, n)}


def test_the_reader_actually_finds_transitions():
    """أداة لا تجد شيًئا تُمرّر كل شيء."""
    found = _assignments_in_source()
    assert len(found) >= 5, f"لم تُقرأ الانتقالات من الشيفرة: {found}"


def test_every_reachable_state_has_an_owner():
    """حالة بلا فاعل معروف = حالة لا يعرف أحد أنه مسؤول عنها."""
    missing = [s for s in _assignments_in_source() if s not in STAGE_ACTOR]
    assert not missing, (
        f"حالات يمكن الوصول إليها بلا فاعل معرَّف: {missing}"
    )


def test_every_non_terminal_state_has_a_way_forward():
    """**القاعدة الحاكمة**: ممنوع أن تصل المعاملة إلى حالة بلا استمرار.

    والمخرج يعني أحد أمرين: مهمة تُنشأ لصاحب المرحلة فيعرف أن عليه
    فعًلا، أو فاعل مسمّى يملك الفعل. حالة بلا هذا ولا ذاك تُصبح صامتة:
    لا أحد يُنبَّه، ولا أحد يعرف أنه المسؤول.
    """
    stranded = []
    for state in _assignments_in_source():
        if state in TERMINAL:
            continue
        has_task = state in STAGE_TASK_PREFIX
        has_actor = STAGE_ACTOR.get(state) not in (None, "—")
        if not (has_task or has_actor):
            stranded.append(state)
    assert not stranded, (
        f"حالات بلا مخرج ولا مسؤول: {stranded}"
    )


def test_terminal_states_are_terminal_on_purpose():
    """والنهائية نهائية عن قصد لا عن سهو: تُعلَن ولا تُستنتج."""
    for state in TERMINAL:
        assert state in ALL_STATES
        assert STAGE_ACTOR.get(state) == "—", (
            f"«{state}» نهائية ومع ذلك لها فاعل — إمّا ليست نهائية أو الجدول خاطئ"
        )


def test_no_state_is_labelled_but_unreachable_without_notice():
    """حالة معرَّفة لا تُسنَد أبًدا: إمّا بقيّة ميّتة أو انتقال نُسي.

    لا يسقط الفحص عليها — قد تكون مقصودة — لكنه يُبقيها مرئية بقائمة
    صريحة، فلا تتراكم حالات لا أحد يعرف إن كانت تعمل.
    """
    #: حالات لا تُنتجها انتقالات اليوم، ولكلٍّ سبب مكتوب:
    known_unassigned = {
        # لم يعد أي انتقال يُنتجها، وصفوف قديمة قد تحملها — ولهذا يقبلها
        # ``finalize`` ضمن حالاته. تُترك ولا تُحذف: حذفها يترك تلك الصفوف
        # بحالة لا يعرفها المحرّك. وتُذكر هنا كي لا تُقرأ سهًوا.
        R.WITH_DELEGATE,
        # افتراضي العمود في النموذج. كل مسار إنشاء يكتب الحالة الحقيقية
        # فوقه (PENDING_MANAGER أو AWAITING_CONTRACTS)، فلا صفّ يستقرّ
        # عليها — لكنها تبقى شبكة أمان: صفّ يُنشأ بلا حالة يُقرأ «جديد»
        # لا فارًغا.
        R.NEW,
    }
    unreachable = ALL_STATES - _assignments_in_source() - known_unassigned
    assert not unreachable, (
        f"حالات معرَّفة ولا تُسنَد في الشيفرة: {sorted(unreachable)} — "
        "أضِفها إلى known_unassigned بسبب مكتوب، أو احذفها"
    )
