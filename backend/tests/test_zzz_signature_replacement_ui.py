# -*- coding: utf-8 -*-
"""استبدال التوقيع: مهمٌة تأمر بفعل، وشاشٌة لا تفعله.

**العطل المقيس**: من يستبدل صورة توقيعه يُحفَظ له طلٌب معلَّق، ويُنشأ
للموارد البشرية **مهمة** عنوانها «طلب استبدال توقيع». والخادم يقصر
الاعتماد على الموارد البشرية وحدها.

**ولا شاشة تعتمده.** ``/signatures/pending`` وأخواتها الأربع لا يصلها
شيء من الواجهة. فالمهمة تصل ولا سبيل إلى إنجازها، والتوقيع الجديد يبقى
معلًَّقا إلى الأبد بينما القديم نشط.

**ورابٌط أضيق من مساره**: كان الرابط في القائمة بشرط ``manage_users``
والمسار بشرط ``view_documents`` — فالموارد البشرية، وهي **وحدها** من
يعتمد، تفتح الشاشة بالعنوان ولا ترى لها رابًطا. شرطان لباب واحد.
"""
from __future__ import annotations

import re
from pathlib import Path

FRONT = Path(__file__).resolve().parents[2] / "frontend" / "src"
PAGE = FRONT / "pages" / "Signatories.tsx"
APP = FRONT / "App.tsx"
I18N = FRONT / "i18n.tsx"


def test_the_screen_reaches_the_queue_the_task_points_at():
    """**جوهر العطل**: المهمة تُنشأ ولا شيء في الواجهة يقرأ الطابور."""
    page = PAGE.read_text(encoding="utf-8")
    assert "/signatures/pending" in page, "لا طريق إلى طابور الاستبدالات"


def test_it_can_both_approve_and_reject(client=None):
    """وقراٌر بلا نصفه الثاني ليس قراًرا: الرفض بابٌ كالاعتماد."""
    page = PAGE.read_text(encoding="utf-8")
    for action in ("approve", "reject"):
        assert re.search(rf'["\'`]{action}["\'`]', page), f"لا {action}"
    assert "sig_reject_reason" in page, "رفٌض بلا سبب يصل صاحبه"


def test_the_decision_is_made_on_an_image_that_is_actually_fetched():
    """**والقرار على صورة تُرى لا على اسم يُقرأ.**

    والصورة تُجلَب بالرمز: نقاط الخادم تشترط الاستيثاق، ورابٌط مباشر في
    ``<a href>`` يعود 401 ويُعرض صفحًة فارغة بلا تفسير.
    """
    page = PAGE.read_text(encoding="utf-8")
    assert "pending/${uid}/image" in page or "/image" in page
    assert 'responseType: "blob"' in page, "الصورة تُطلَب بلا رمز"


def test_the_link_is_no_narrower_than_the_route():
    """**شرطان لباب واحد ينحرفان** — والمنحرف هنا حجب الشاشة عمّن يعتمد."""
    app = APP.read_text(encoding="utf-8")
    nav = re.search(r'can\("(\w+)"\) && <Item to="/signatories"', app)
    guard = re.search(r'path="/signatories".*?a\.can\("(\w+)"\)', app, re.S)
    assert nav and guard, "تغيّرت بنية القائمة أو الحارس"
    assert nav.group(1) == guard.group(1), (
        f"الرابط بشرط {nav.group(1)} والمسار بشرط {guard.group(1)}"
    )


def test_the_screen_says_what_happens_while_it_waits():
    """ورسالٌة تصف الأثر: الجديد لا يُستعمَل، والقديم نشط حتى تقرّر."""
    i18n = I18N.read_text(encoding="utf-8")
    for key in ("sig_pending_title", "sig_pending_hint", "sig_pending_approved",
                "sig_pending_rejected"):
        assert key in i18n, f"مفتاح ناقص: {key}"
