# -*- coding: utf-8 -*-
"""سجٌّل بلا ملف — ومن يكتشفه أوًلا لا ينبغي أن يكون طالب الورقة.

**من أين جاء**: ``P1-01``. تنزيُل مستٍند مولَّد كان يعود ``410``: الصفّ في
القاعدة والملف مفقود — قرٌص مؤقّت يُمحى مع كل نشرة والسجلّ يبقى.

وبنيُة التخزين أُصلحت قبل هذه الجولة (مفتاٌح نسبيّ ومخزٌن واحد، و``S3``
خلفيًّة، وعلامُة دوام في ``/health/deep``). **وبقي السؤال الذي لا تجيبه
البنية**: أيّ الصفوف القائمة بلا ملف الآن؟ ولا يُعرَف إلا حين يضغط
مستخدٌم فيقع على ``410``.

وهذه الحرّاس لا تقيس «صفٌر ضائع» — ذلك رقٌم يتغيّر ببيئة التشغيل. تقيس أن
**الأداة تصلح للاعتماد عليها**: تغطّي كل عمود، ولا تطمئن حين لا تقرأ
شيًئا، ولا تخلط علامًة نصّية بملفٍّ ضائع.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sqlalchemy import String

from app import models

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "storage_orphans.py"


def test_the_sweep_covers_every_storage_key_column():
    """**قائمٌة مكتوبٌة بيد تشيخ بصمت.**

    والأعمدة تُشتقّ من وصف الجداول، فعموٌد جديد يدخل المسح يوم يُضاف. وهي
    علّة ``AWS-01`` نفسها التي دعت إلى توحيد التخزين: ثلاثة عشر موضع
    كتابة، فيبقى موضٌع لم يُحوَّل — وهو بالضبط الملف الذي يضيع.
    """
    from scripts.storage_orphans import _key_columns

    covered = {f"{t.name}.{c}" for t, c in _key_columns()}
    expected = {f"{t.name}.{c.name}"
                for t in models.Base.metadata.tables.values()
                for c in t.columns
                if c.name.endswith("_path") and isinstance(c.type, String)}
    assert covered == expected, sorted(expected ^ covered)
    assert covered, "لا عمود مفاتيح أصًلا — المسح يقيس لا شيء"


def test_a_marker_is_not_a_lost_file():
    """**وقيمٌة ليست مفتاًحا أصًلا ليست ملًفا ضائًعا.**

    صفوف البذرة تحمل ``(تجريبي)`` في خانة الصورة. وعدُّها «مفقودة» يُغرِق
    ضياَع ورقٍة رسمية في ثمانٍ وأربعين ضجّة، فيُقرأ التقرير مرًة ويُهمَل
    بعدها. والقاعدة §3 من الحماية: بيانات الاختبار ليست عطًلا في المنتج.
    """
    from scripts.storage_orphans import _looks_like_key

    assert not _looks_like_key("(تجريبي)")
    assert not _looks_like_key("")
    assert not _looks_like_key("لا-مجلّد-ولا-امتداد")
    assert _looks_like_key("archive/ab12cd_x.pdf")
    assert _looks_like_key("requests\\\\req5_exit_9f.pdf")


def test_the_report_names_the_database_it_read():
    """**تقريٌر لا يقول ما قرأ لا يُبنى عليه قرار.**

    مساُر SQLite النسبيّ يُحَل على مجلَّد التشغيل. فشُغِّلت الأداة أول مرّة
    من جذر المستودع فقرأت قاعدًة أخرى وطبعت «صفوٌف بلا ملف: 0» — طمأنينٌة
    مصدُرها أنها لم تقرأ ما يُقصَد. فصارت تعلن هدفها في كل تشغيل، ويبقى
    انعداُم المقروء خروًجا بالرمز 2 لا صفًرا.
    """
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                       text=True, encoding="utf-8", cwd=str(BACKEND))
    assert "القاعدة المقروءة:" in (r.stdout or ""), (r.stdout or "")[:300]


def test_the_sweep_runs_and_reports_officially_weighted_rows():
    """وتعمل على القاعدة الصحيحة، وتزن الرسميّ غير الشخصي.

    فورقٌة رسمية تُفقد ليست كصورٍة شخصية تُفقد، ومن يقرأ التقرير يحتاج أن
    يعرف أيّها وقع.
    """
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True,
                       text=True, encoding="utf-8", cwd=str(BACKEND))
    assert r.returncode in (0, 1), (r.returncode, (r.stderr or "")[:300])
    out = r.stdout or ""
    assert "documents.file_path" in out and "[رسمي]" in out, out[:400]
