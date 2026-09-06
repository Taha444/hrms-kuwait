# -*- coding: utf-8 -*-
"""البند 20 — قراءة OCR تظهر في قصّة المعاملة.

**والعطل لم يكن غياب التسجيل.** ``renewal_ocr_read`` مسجَّل منذ البداية
وله تسمية في التايملاين — لكنه يُسجَّل باسم كيان **الموظف**، والتايملاين
يقرأ ما سُجِّل باسم **المعاملة**. فالحدث موجود ومُودَع في القصة الخطأ.

وهو نصف قصّة التجديد: ماذا قرأ النظام من المستند وبأي ثقة. ومن يراجع
معاملة بعد شهور — أو يعترض على تاريخ انتهاء — يحتاج أن يعرف هل قُرئ
آلًيا بثقة عالية أم أُدخل يًدا بعد فشل القراءة.

**ولا يُنزَع من ملف الموظف**: مستنده وقراءته تخصّانه أيًضا. سطران لحدث
واحد أصدق من سطر في المكان الخطأ.
"""
from __future__ import annotations

import inspect
import re

from app.routers import renewals as rn_router


def test_every_audited_action_has_a_timeline_label():
    """ولا حدث بلا اسم: «renewal_upload» خام في القصة لا يُقرأ."""
    src = inspect.getsource(rn_router)
    audited = set(re.findall(r'audit\(db,\s*(?:user|None),\s*"([a-z_]+)"', src))
    missing = sorted(a for a in audited if a not in rn_router.TIMELINE_LABELS)
    assert not missing, f"أفعال مسجَّلة بلا تسمية: {missing}"


def test_no_label_is_left_without_an_event():
    """**ولا تسمية بلا حدث**: اسٌم لا يُنتَج أبًدا يوهم بتغطية لا وجود لها.

    وهذا ما كشف العطل: ``renewal_ocr_read`` له تسمية، وبحثي الأول لم يجد
    له تسجيًلا — ثم تبيّن أنه مسجَّل باسم كيان آخر. فالتسمية كانت صادقة
    والقصّة هي التي لا تصله.
    """
    src = inspect.getsource(rn_router)
    audited = set(re.findall(r'audit\(db,\s*(?:user|None),\s*"([a-z_]+)"', src))
    orphan = sorted(k for k in rn_router.TIMELINE_LABELS if k not in audited)
    assert not orphan, f"تسميات بلا حدث: {orphan}"


def test_the_ocr_event_is_recorded_against_the_renewal():
    """**جوهر الإصلاح**: الحدث يُسجَّل باسم المعاملة التي تُقرأ قصّتها."""
    src = inspect.getsource(rn_router._ocr_proposal)
    assert 'renewal_id' in src, "لا سبيل لربط القراءة بالمعاملة"
    assert '"renewal", renewal_id' in src, (
        "القراءة ما زالت خارج قصّة المعاملة"
    )


def test_it_is_still_recorded_against_the_employee():
    """ولا يُنزَع من ملف الموظف: مستنده وقراءته تخصّانه."""
    src = inspect.getsource(rn_router._ocr_proposal)
    assert 'audit(db, None, "renewal_ocr_read", entity_type, entity_id' in src, (
        "نُقل الحدث بدل أن يُضاف"
    )


def test_the_renewal_upload_sites_pass_the_link():
    """وكل موضع رفع في مسار التجديد يمرّر المعاملة — لا بعضها."""
    src = inspect.getsource(rn_router)
    calls = re.findall(r"_ocr_proposal\(db, \"employee\", emp\.id, doc_kind([^)]*)\)",
                       src)
    assert calls, "لم يعد يُستدعى في مسار التجديد"
    for tail in calls:
        assert "renewal_id=rn.id" in tail, (
            f"موضع رفع بلا ربط بالمعاملة: _ocr_proposal(...{tail})"
        )


def test_the_timeline_reads_only_renewal_scoped_rows():
    """والقصّة من كيان واحد: خلط الكيانات يجرّ أحداث موظف إلى معاملة غيره."""
    src = inspect.getsource(rn_router.renewal_timeline)
    assert '("renewal", "residency_renewal")' in src, (
        "تغيّر نطاق القراءة — أعد النظر في ربط الأحداث"
    )
