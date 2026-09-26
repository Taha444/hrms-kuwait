# -*- coding: utf-8 -*-
"""M09 #8 — لا حالةَ طلبٍ بلا مخرج: كلُّ حالةٍ يكتبها الكود مصنَّفةٌ نهايةً أو لها مخرجٌ مسمّى.

الحارس يستخرج الحالات من **الشيفرة نفسها** (كل ``status = "..."`` على طلب)، فحالةٌ تُضاف غدًا بلا تصنيفٍ تُسقط
الاختبار بدل أن تصير طلبًا عالقًا لا يجد صاحبُه ما يفعله.
"""
import re
from pathlib import Path

from app import request_actions

APP = Path(__file__).resolve().parents[1] / "app"

#: نهايات: لا ينتظر فيها أحدٌ شيئًا
TERMINAL = {"completed", "rejected", "cancelled", "approved"}
#: غير نهائية ولكلٍّ مخرجٌ مسمّى: قرار المعتمِد / إعادة التقديم من صاحبه / إجراءٌ تنفيذيّ / إعادة التطبيق
EXITS = {
    "pending": "decision",
    "returned": "resubmit",
    "apply_failed": "retry_apply",
}


def _status_literals():
    found = set()
    for f in ("workflow.py", "routers/requests.py", "request_actions.py", "request_effects.py"):
        text = (APP / f).read_text(encoding="utf-8")
        found |= set(re.findall(r"\b(?:req|request|r)\.status\s*=\s*\"([a-z_]+)\"", text))
    return found


def test_every_status_the_code_writes_is_terminal_or_has_a_named_exit():
    statuses = _status_literals()
    assert {"pending", "returned", "apply_failed"} <= statuses, "الاستخراج معطوب"
    exec_exits = set(request_actions.EXECUTION_ACTIONS_BY_STATUS)
    unclassified = statuses - TERMINAL - set(EXITS) - exec_exits
    assert not unclassified, f"حالاتٌ بلا تصنيف (نهاية أو مخرج): {sorted(unclassified)}"


def test_the_named_exits_exist_as_doors():
    from app import workflow
    assert callable(workflow.resubmit) and callable(workflow.retry_apply) and callable(workflow.cancel)
    assert {"awaiting_signature", "awaiting_delegate", "ready_for_pickup"} <= set(
        request_actions.EXECUTION_ACTIONS_BY_STATUS)
