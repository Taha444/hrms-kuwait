# -*- coding: utf-8 -*-
"""سلسلة الترحيلات تُطبَّق على قاعدة فارغة — اختبار التنصيب.

ROOT CAUSE: حزمة الاختبارات كلها تبني الجداول بـ``Base.metadata.create_all``،
فلم يكن أي اختبار يمرّ على مسار الترحيلات إطلاًقا. والنتيجة أن
``alembic upgrade head`` كان **يفشل على قاعدة SQLite فارغة** بأربعة أعطال
متمايزة، ولا شيء يكشفها حتى يوم التنصيب عند العميل.

هذا الملف يسدّ الثغرة: يبني قاعدة نظيفة ويطبّق السلسلة كاملة كما يفعل التنصيب.
بطيء نسبًيا وهذا مقبول — يُشغَّل مرة واحدة ويحمي المسار الذي لا يمرّ عليه أحد.
"""
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def _upgrade_fresh(tmp_db: str) -> subprocess.CompletedProcess:
    """يطبّق السلسلة في عملية منفصلة — الاختبارات تشارك محرّك القاعدة."""
    env = {**os.environ, "DATABASE_URL": "sqlite:///" + tmp_db.replace(os.sep, "/"),
           "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=600,
        # مخرجات alembic عربية؛ ترميز ويندوز الافتراضي يفشل في قراءتها
        encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def fresh_db():
    d = tempfile.mkdtemp()
    db = os.path.join(d, "install.db")
    proc = _upgrade_fresh(db)
    assert proc.returncode == 0, (
        "فشل تطبيق السلسلة على قاعدة فارغة — أي أن تنصيًبا جديًدا يتوقّف:\n"
        + (proc.stderr or proc.stdout)[-1500:])
    yield db


def test_migration_chain_applies_to_empty_database(fresh_db):
    """التنصيب من الصفر ينجح ويصل إلى الرأس."""
    c = sqlite3.connect(fresh_db)
    try:
        tables = {r[0] for r in c.execute(
            "select name from sqlite_master where type='table'")}
        # عيّنة من الجداول التي لا يقوم النظام بدونها
        for t in ("users", "employees", "companies", "requests", "documents",
                  "document_templates", "notification_templates", "residency_renewals"):
            assert t in tables, f"جدول {t} غائب بعد الترحيل"
    finally:
        c.close()


def test_official_templates_are_seeded_by_migrations(fresh_db):
    """القوالب الرسمية تصل القاعدة الجديدة.

    كانت الترحيلات التي تبذرها تفشل قبل الوصول إليها (NOW() لا توجد في SQLite)،
    فيُنصَّب النظام بلا نصّ عقد حكومي — والمندوب يرى «القالب غير موجود» ولا
    يستطيع توليد عقد لأي تجديد.
    """
    c = sqlite3.connect(fresh_db)
    try:
        for code in ("GOV-CONTRACT-RENEWAL", "COMPANY-CONTRACT-HIRE"):
            n = c.execute("select count(*) from document_templates where code=?",
                          (code,)).fetchone()[0]
            assert n >= 1, f"قالب {code} غير مبذور — التنصيب ناقص"
        assert c.execute("select count(*) from notification_templates").fetchone()[0] >= 50
        assert c.execute("select count(*) from request_types").fetchone()[0] >= 20
    finally:
        c.close()


def test_migration_chain_is_rerunnable(fresh_db):
    """إعادة التشغيل على قاعدة مطبَّقة لا تكسرها.

    الترقية عند العميل تعني تشغيل الأمر على قاعدة قائمة. لو لم تكن العمليات
    محصَّنة ضد التكرار، فشلت الترقية الثانية بـ"duplicate column".
    """
    proc = _upgrade_fresh(fresh_db)
    assert proc.returncode == 0, (
        "إعادة تشغيل السلسلة كسرت قاعدة مطبَّقة:\n" + (proc.stderr or proc.stdout)[-1200:])


def test_gov_contract_text_has_no_scan_typos(fresh_db):
    """نصّ العقد الحكومي بلا آثار مسح ضوئي.

    ROOT CAUSE: النصّ أُدخل بمسح ضوئي لنموذج الهيئة العامة للقوى العاملة،
    فحمل آثار القراءة الآلية — «تسععرى» بدل «تسري»، «تخت المحكمة» بدل
    «تختص»، «باللاتين العربية» بدل «باللغتين». والمستند يُطبع ويُقدَّم لجهة
    رسمية بهذه الأخطاء، فتُقرأ على أنها إهمال في إعداد عقد قانوني.

    الاختبار يقرأ ما وصل القاعدة فعًلا بعد السلسلة كاملة — لا ما في ملف
    الترحيل — لأن التنصيب هو ما يراه العميل.
    """
    import importlib.util
    import re
    import sqlite3
    import sys
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "_fixmig",
        Path(__file__).resolve().parents[1] / "alembic" / "versions"
        / "r7j8k9l0m1n_fix_gov_contract_typos.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_fixmig"] = mod
    spec.loader.exec_module(mod)

    c = sqlite3.connect(fresh_db)
    try:
        row = c.execute("select body_html from document_templates "
                        "where code='GOV-CONTRACT-RENEWAL'").fetchone()
        assert row and row[0], "قالب العقد الحكومي غير مبذور"
        flat = re.sub(r"\s+", " ", row[0])

        remaining = [w for w, _ in mod.TYPOS if w in flat]
        assert not remaining, f"أخطاء مسح ما زالت في النصّ المنشور: {remaining}"

        # وعيّنة من الصيغ الصحيحة موجودة فعًلا — لا حذف بلا استبدال
        for good in ("تسري أحكام", "القطاع الأهلي", "تختص المحكمة",
                     "باللغتين العربية", "بنصوص اللغة العربية", "ثلاث نسخ"):
            assert good in flat, f"الصيغة الصحيحة غائبة: {good}"

        # والبنود القانونية لم تُمَسّ — التصحيح إملائي لا صياغي
        for legal in ("رقم 6 لسنة 2010", "رقم 46 لسنة 1987", "رقم 1 لسنة 1999"):
            assert legal in flat, f"مرجع قانوني تغيّر أو ضاع: {legal}"

        # لا نقاط حول خانات يملؤها النظام: في النموذج الورقي هي مواضع كتابة
        # باليد، وحين يملأها النظام تصير «لا يوجد.........» — خانة نصفها
        # مطبوع ونصفها مهمل.
        assert "................{{special_condition" not in flat,             "نقاط الكتابة اليدوية ما زالت حول خانة يملؤها النظام"
        assert "..... {{annual_leave_days}}" not in flat

        # ولا تكرار في تذييل التحقق
        assert flat.count("Verification Code") <= 1 or "QR</div>" not in flat
    finally:
        c.close()
