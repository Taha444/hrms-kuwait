# -*- coding: utf-8 -*-
"""إحداثياٌت اختياريٌة وأثرُها قاطع — نقٌص متوقٌَّع ال يُرى.

**القياس، ثم تصحيُحه مرتين:**

``_check_geofence`` يرفض البصَم بـ400 «إحداثيات GPS مطلوبة» متى كان نمُط
الموظف ``gps`` أو ``both`` **وفرعُه بال إحداثيات**. وفي قاعدة التطوير:
واحٌد وعشرون فرًعا من خمسٍة وعشرين بال إحداثيات.

1. **وقاعدُة التطوير ليست اإلنتاج**: البذُر يضع إحداثياٍت لكل فرٍع يُنشئه
   (``seed.py``)، وقاعدُة االختبار فيها أربعُة فروع كلُّها بإحداثيات. فالواحد
   والعشرون أُنشئت **من التطبيق**، ال من البذر.
2. **والشاشُة تجمعها**: ``Branches.tsx`` فيها حقال الموضع ونصُف القطر،
   وتُرسلهما إن مُلئا. فليست «حقًال بال مدخل» — **هي حقٌل اختياري**.

فالتشخيُص الصحيح أضيُق وأدقّ: **نقٌص متوقٌَّع بالتصميم وأثرُه قاطع.** من
يُنشئ فرًعا وال يعرف موضعه بعد يتركه فارًغا بحّق — ثم يُسنِد إليه موظًفا
على النمط الغالب (``both``) فيُردّ عند البصم، وال شيء قاله قبل أن يقف
أمام الشاشة.

فيُسمّى الناقُص لمن يملؤه، على عرف ``config_gap`` القائم في ستّة مواضع.

**وال تُختَلق إحداثيات**: موضُع الفرع بياٌن يعرفه صاحبه، وإحداثيٌة مخترعٌة
تجعل السياَج يقبل من هو بعيد ويرفض من هو حاضر — أسوأ من سياٍج معطَّل.

**والخطورُة تتبع األثر ال الشكل**: ``critical`` لفرٍع عليه موظفون على نمٍط
يطلب GPS، و``warning`` لفرٍع ال موظَف عليه بعد. فتحذيٌر بخطورٍة واحدة لكل
شيء يُدرَّب على تجاهله.
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete, func, select

from app import models
from app.database import SessionLocal


def _tasks(prefix: str) -> list[models.Task]:
    db = SessionLocal()
    try:
        return list(db.scalars(select(models.Task).where(
            models.Task.dedup_key.like(f"{prefix}%"))).all())
    finally:
        db.close()


def _purge() -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Task).where(
            models.Task.dedup_key.like("branch_no_coords:%")))
        db.commit()
    finally:
        db.close()


def test_a_branch_without_coordinates_is_named():
    """**جوهر البند**: الناقُص يُسمّى لمن يملؤه قبل أن يقف أحٌد أمام الشاشة."""
    from app.notifications import daily_scan

    _purge()
    db = SessionLocal()
    try:
        without = db.scalar(select(func.count()).select_from(models.Branch).where(
            models.Branch.latitude.is_(None))) or 0
        if not without:
            import pytest
            pytest.skip("كلُّ الفروع لها إحداثيات في هذه القاعدة")
        daily_scan(db)
        db.commit()
    finally:
        db.close()
    got = _tasks("branch_no_coords:")
    try:
        assert got, "فروٌع بال إحداثيات ولم يُسمَّ منها شيء"
        assert all("إحداثيات" in (t.title or "") for t in got), \
            [t.title for t in got][:3]
    finally:
        _purge()


def test_the_severity_follows_the_actual_harm():
    """**وتحذيٌر بخطورٍة واحدة لكل شيء يُدرَّب على تجاهله.**

    فـ``critical`` لفرٍع عليه من يُحجَب فعًلا، و``warning`` لفرٍع ال موظَف
    عليه بعد.
    """
    from app.notifications import daily_scan

    _purge()
    db = SessionLocal()
    try:
        daily_scan(db)
        db.commit()
        rows = db.scalars(select(models.Task).where(
            models.Task.dedup_key.like("branch_no_coords:%"))).all()
        verdicts = []
        for t in rows:
            at_risk = db.scalar(select(func.count()).select_from(models.Employee).where(
                models.Employee.branch_id == t.related_entity_id,
                models.Employee.status == "active",
                models.Employee.attendance_mode.in_(("gps", "both")))) or 0
            verdicts.append((t.severity, at_risk))
    finally:
        db.close()
    try:
        for sev, at_risk in verdicts:
            expected = "critical" if at_risk else "warning"
            assert sev == expected, (sev, at_risk)
    finally:
        _purge()


def test_no_coordinates_are_invented():
    """**وإحداثيٌة مخترعٌة أسوأ من سياٍج معطَّل.**

    فهي تجعل السياَج يقبل من هو بعيد ويرفض من هو حاضر. فال يكتب المسُح
    إحداثيًة، يسمّي نقَصها.
    """
    import inspect

    from app import notifications as N

    src = inspect.getsource(N.daily_scan)
    block = src[src.index("branch_no_coords"):]
    block = src[max(0, src.index("Branch.latitude.is_(None)")):][:1400]
    assert "latitude =" not in block and "longitude =" not in block, \
        "المسُح يكتب إحداثيًة بدل أن يسمّي نقَصها"


def test_the_fence_still_refuses_what_it_cannot_verify():
    """**والحارُس ال يُفتح الباَب**: من نمطُه GPS وفرعُه بال موضٍع يُردّ.

    فالتسميُة تنبيٌه ال تسويغ — والبديُل (قبوُل البصم بال تحقّق) يجعل
    السياَج ديكوًرا.
    """
    import inspect

    from app.routers import attendance as A

    src = inspect.getsource(A._check_geofence)
    assert "branch.latitude is None" in src and "status_code=400" in src, src[:300]
