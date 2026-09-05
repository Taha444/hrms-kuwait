# -*- coding: utf-8 -*-
"""ختم الأساس يُقاس بوجود إصدار مسجَّل، لا بوجود الجدول.

**ما ظهر بالقياس** (أثناء تشغيل النظام محلًّيا للتحقّق من شاشة نهاية
الخدمة): قاعدة فيها **خمسون جدوًلا**، و``alembic_version`` **موجود
وصفوفه صفر**. فالشرط ``"alembic_version" not in tables`` كان False،
فتُخطّى خطوة الختم، ثم يبدأ ``upgrade`` من أول ترحيل ويصطدم بجداول
قائمة — ويفشل الإقلاع.

وهذه الحالة تنشأ من ختم انقطع، أو ``downgrade base``، أو أداة أنشأت
الجدول بلا صفّ. ليست نادرة.

**ولماذا تستحقّ حارًسا**: هذا مسار إقلاع الإنتاج نفسه
(``CMD python -m app.db_migrate && … uvicorn``). وفشلُه بصوت مسموع
صواب حين يكون المخطّط فاسًدا — أما هنا فالحالة قابلة للإصلاح، فيوقف
النشر بلا سبب حقيقي.
"""
from __future__ import annotations

import inspect

from app import db_migrate


def test_the_condition_reads_a_recorded_version_not_a_table():
    """**جوهر الإصلاح**: الشرط على الصفّ لا على الجدول."""
    src = inspect.getsource(db_migrate.run)
    assert "SELECT version_num FROM alembic_version" in src, (
        "الشرط لا يقرأ الإصدار المسجَّل"
    )
    assert '"alembic_version" not in tables and tables' not in src, (
        "عاد الشرط يفحص وجود الجدول وحده — وجدول فارغ يتخطّى الختم"
    )


def test_an_empty_version_table_still_triggers_the_stamp():
    """قاعدة بجداول وإصدار غير مسجَّل تُختَم عند الأساس.

    القياس على المنطق نفسه بدل بناء قاعدة كاملة: الشرط يجب أن يصدق
    حين توجد جداول ولا يوجد إصدار.
    """
    for tables, stamped, expected in [
        ({"users", "alembic_version"}, None, True),    # الحالة المقيسة
        ({"users"}, None, True),                        # create_all بلا الجدول
        ({"users", "alembic_version"}, "68862c46506d", False),  # مختومة
        ({"alembic_version"}, None, False),             # قاعدة فارغة
        (set(), None, False),                           # لا شيء
    ]:
        got = bool(tables - {"alembic_version"}) and not stamped
        assert got is expected, (tables, stamped, got, expected)


def test_the_baseline_is_the_first_revision_in_the_chain():
    """والختم عند **الأساس** لا الرأس: وإلا تُخطّى كل الترحيلات.

    ``stamp head`` يكتب أحدث إصدار بلا تطبيق شيء — فتُقرأ القاعدة
    محدَّثة وهي ليست كذلك، صامًتا وإلى الأبد.
    """
    import re
    from pathlib import Path

    # الصيغة تختلف بين الملفات (``down_revision = None`` و
    # ``down_revision: Union[str, None] = None``)، فيُقاس المعنى لا الشكل:
    # إسناد ``None`` مهما كان التوصيف بينهما. وأول كتابة طابقت نًصا حرًفيا
    # فلم تجد جذًرا واحًدا — فحص يعدّ الصفر ويسكت.
    root_re = re.compile(r"^down_revision\s*(?::[^=]+)?=\s*None\s*$", re.M)
    versions = Path(db_migrate.__file__).resolve().parent.parent / "alembic" / "versions"
    roots = [p.name for p in versions.glob("*.py")
             if root_re.search(p.read_text(encoding="utf-8"))]
    assert len(roots) == 1, f"أكثر من جذر في سلسلة الترحيلات: {roots}"
    assert db_migrate.BASELINE_REVISION in roots[0], (
        f"الأساس {db_migrate.BASELINE_REVISION} ليس جذر السلسلة ({roots[0]})"
    )


def test_failure_still_stops_the_boot():
    """ولم يُرخَ الفشل: مخطّط فاسد يوقف النشر ولا يُقلع بصمت."""
    src = inspect.getsource(db_migrate)
    assert "sys.exit(1)" in src, (
        "فشل الترحيل لم يعد يوقف الإقلاع — يُقلع بمخطّط قديم بصمت"
    )
