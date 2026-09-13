# -*- coding: utf-8 -*-
"""مفرداُت الحالة — الواجهُة تكتبها بيدها، والخادُم يملكها.

**القياس**: كلُّ حرٍف تُقارِن به الواجهُة حالًة، هل يعرفه الخادم؟ اليوَم:
سبعٌة وعشرون حرًفا، كلُّها معروفة. **ال عطَل** — وهذا الحارُس يمنع أن
يصير عطًلا.

**ولماذا يُحرَس نفٌي**: الحالُة تُعرَّف في الخادم مرًة واحدًة (ثابٌت مثل
``R.PENDING_HR_VERIFY``) — وهذا هو النمُط الصحيح. لكنّ الواجهَة تكتب
النصَّ حرًفا، فال شيَء يربط النسختين: من يُعيد تسمية حالٍة في الخادم يجد
شاشًة تُقارن بما ال يعود يُرسَل — **فال يسقط شيٌء، بل يختفي زٌّر بال خبر**.
وهذا أسوأ من خطٍأ: الخطُأ يُرى، والزرُّ الغائُب يُقرأ «المّيزُة غيُر
موجودة».

**وهو من الحرّاس التي تقرأ النصَّ بحقّ**: المقيُس **غياُب** حرٍف في طرٍف
يعرفه الطرُف اآلخر — وال سلوَك له يُقاس، لأن ما يُقاس هنا هو التطابُق بين
ملّفين ال أثٌر في قاعدة.

**وقياٌس سابٌق لي أخطأ**: استخرجتُ حالاِت الخادم من ``status == "..."``
وحدها، فبدت تسٌع منها «مفقودة» — وهي ثوابُت معلَنٌة مرًة، وهو عيُن النمط
الحسن. فيُبحَث عن الحرف في **كل** شيفرة الخادم ال في صيغٍة بعينها.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
FE = ROOT / "frontend" / "src"
BE = ROOT / "backend" / "app"

#: حالاُت واجهٍة محضة — ال يعرفها الخادُم بقصد، فتُسمّى صراحًة.
_UI_ONLY: dict[str, str] = {}


def _frontend_status_literals() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    if not FE.exists():
        return out
    for p in FE.rglob("*.ts*"):
        for i, ln in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            where = f"{p.relative_to(FE)}:{i}"
            for m in re.finditer(r'status\s*(?:===|!==|==|!=)\s*["\']([a-z_]+)["\']', ln):
                out.setdefault(m.group(1), set()).add(where)
            for m in re.finditer(r'\[([^\]]*)\]\.includes\(\s*[\w.]*status', ln):
                for lit in re.findall(r'["\']([a-z_]+)["\']', m.group(1)):
                    out.setdefault(lit, set()).add(where)
    return out


def _backend_blob() -> str:
    return "".join(p.read_text(encoding="utf-8", errors="ignore")
                   for p in BE.rglob("*.py"))


def test_every_status_the_screen_compares_is_known_to_the_server():
    """**الحارس الدائم**: ال حرَف حالٍة في شاشٍة ال يعرفه الخادم.

    ومن أراد حالَة واجهٍة محضة سمّاها في ``_UI_ONLY`` بسببها — فقراٌر
    مكتوٌب يُراجَع، وحرٌف منسٌّي ال.
    """
    fe = _frontend_status_literals()
    if not fe:
        import pytest
        pytest.skip("ال واجهَة في هذا المسار")
    blob = _backend_blob()
    stray = {k: sorted(v)[:3] for k, v in fe.items()
             if k not in _UI_ONLY and not re.search(rf'["\']{re.escape(k)}["\']', blob)}
    assert not stray, ("حالاٌت تُقارِنها الشاشُة وال يعرفها الخادم:\n" +
                       "\n".join(f"  {k} ← {', '.join(v)}" for k, v in stray.items()))


def test_the_measurement_itself_still_sees_something():
    """**وقياٌس ال يرى شيًئا يمرُّ أخضَر دائًما.**

    لو تغيَّرت صيغُة المقارنة في الواجهة (مثًال إلى دالٍّة مساعدة) لصار
    االستخراُج فارًغا والحارُس ال يحرس شيًئا وهو أخضر — وهو الصنُف الذي
    أوقعني اليوَم مرًة. فيُشترَط أن يرى عدًدا معقوًال.
    """
    fe = _frontend_status_literals()
    if not FE.exists():
        import pytest
        pytest.skip("ال واجهَة في هذا المسار")
    assert len(fe) >= 15, (f"االستخراُج يرى {len(fe)} حالًة فقط — "
                           "تغيَّرت صيغُة المقارنة في الواجهة فصار القياُس أعمى")


def test_no_ui_only_status_is_secretly_known():
    """وحالٌة صار الخادُم يعرفها ترتفع من قائمة الاستثناء."""
    if not _UI_ONLY:
        return
    blob = _backend_blob()
    revived = sorted(k for k in _UI_ONLY
                     if re.search(rf'["\']{re.escape(k)}["\']', blob))
    assert not revived, f"حالاٌت صار الخادُم يعرفها: {revived}"
