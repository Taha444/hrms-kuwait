# -*- coding: utf-8 -*-
"""AWS-01 — كل تخزين يمرّ من طبقة واحدة.

كان كل موضع يكتب على القرص بنفسه: ثلاثة عشر موضع كتابة وثلاثون موضع قراءة.
ومجلد على قرص الخادم يعني أن إعادة النشر تمحو الجوازات والعقود والإقامات.

والحارس هنا ليس على S3 بل على **الطبقة**: ما دامت الكتابة موزّعة، سيبقى
موضع لم يُحوَّل — وهو بالضبط الملف الذي يضيع. وقد حدث ذلك فعًلا أثناء
التحويل: ``verify.py`` فات القائمة، فكشفه اختبار التحقّق من صحّة مستند.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"

#: استثناءات مبرَّرة، كلٌّ بسببه. أي إضافة هنا قرار لا سهو.
ALLOWED = {
    "storage.py": "هو الطبقة نفسها",
    "main.py": "يخدم ملفات الواجهة المبنيّة — قرص حقيقي بحقّه",
    "ocr.py": "يعمل على ملف مؤقّت بمساره الحقيقي",
    "safe_files.py": "تنقية الأسماء لا تخزين",
}

RE_WRITE = re.compile(r"""(?<!fd)open\([^)]*["']wb["']""")

#: ``os.fdopen`` مستثنى لأنه يكتب على واصف ملف من ``tempfile.mkstemp``
#: — ملف عمل يُقرأ ثم يُحذف، لا مستنًدا يُحفظ. والاستثناء مشروط:
#: الاختبار التالي يرفض ``fdopen`` في ملف لا ينادي ``mkstemp``، فلا
#: يصير باًبا خلفيًّا لكتابة دائمة على القرص.


def _sources():
    return [p for p in APP.rglob("*.py") if p.name not in ALLOWED]


def test_no_direct_disk_writes_outside_the_storage_layer():
    """لا ``open(..., "wb")`` خارج الطبقة.

    موضع واحد منسيّ يكفي: هو الملف الذي يبقى على قرص الـinstance ويضيع مع
    أول إعادة نشر — وبقيّة النظام تبدو سليمة.
    """
    hits = []
    for p in _sources():
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if RE_WRITE.search(line):
                hits.append(f"{p.relative_to(APP)}:{i}: {line.strip()[:80]}")
    assert not hits, (
        "كتابة مباشرة على القرص خارج طبقة التخزين — تضيع مع أول إعادة نشر.\n"
        "البديل: storage.save_bytes أو storage.save_at_key.\n" + "\n".join(hits)
    )


def test_no_filesystem_checks_on_stored_keys():
    """ما يُحفظ في القاعدة مفتاح لا مسار — فلا يُسأل عنه نظام الملفات."""
    rx = re.compile(r"os\.path\.(exists|getsize)\([\w.]*(file_path|_path|fpath)\b")
    hits = []
    for p in _sources():
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if rx.search(line):
                hits.append(f"{p.relative_to(APP)}:{i}: {line.strip()[:80]}")
    assert not hits, (
        "فحص نظام الملفات على مفتاح مخزَّن — يعطي False دائًما على S3.\n"
        "البديل: storage.key_exists.\n" + "\n".join(hits)
    )


def test_round_trip_through_the_layer():
    """الحفظ ثم القراءة ثم الحذف — العقد الذي تعتمد عليه بقيّة الشيفرة."""
    from app.storage import (delete_key, key_exists, read_bytes, save_at_key,
                             save_bytes)

    data = "محتوى اختبار".encode("utf-8")
    key = save_bytes(data, "tests", "ملف.txt", prefix="t_")
    assert not key.startswith("/") and ":" not in key[:3], (
        f"المفتاح يجب أن يكون نسبيًّا لا مساًرا مطلًقا: {key}"
    )
    assert key_exists(key)
    assert read_bytes(key) == data
    assert delete_key(key)
    assert not key_exists(key)

    fixed = save_at_key(data, "tests/مفتاح-محدد.txt")
    assert read_bytes(fixed) == data
    # الاستبدال مقصود على المفتاح المحدَّد: إعادة التوليد تكتب فوق نسختها
    save_at_key(b"new", "tests/mfth-mhdd.txt")
    assert read_bytes(save_at_key(b"newer", "tests/mfth-mhdd.txt")) == b"newer"
    delete_key(fixed)
    delete_key("tests/mfth-mhdd.txt")


def test_legacy_absolute_paths_still_resolve():
    """صفوف قديمة تحمل مساًرا مطلًقا داخل مجلد الرفع — لا تُكسر بالترحيل.

    التوافق في الطبقة لا في ثلاثين موضع نداء: من يضع الشرط في كل موضع
    ينسى موضًعا.
    """
    from app.config import settings
    from app.storage import _to_key, key_exists, save_bytes

    key = save_bytes(b"x", "tests", "legacy.txt")
    absolute = str((Path(settings.upload_dir) / key).resolve())
    assert _to_key(absolute) == key, "لم يُشتقّ المفتاح من المسار المطلق"
    assert key_exists(absolute), "صفّ قديم بمسار مطلق لم يعد يُقرأ"
    from app.storage import delete_key
    delete_key(key)


def test_s3_backend_declares_no_credentials():
    """لا مفاتيح وصول في الإعداد — الاعتماد من IAM role وحده.

    أي مفتاح يُكتب في .env هو مفتاح يُسرَّب مع أول نسخة احتياطية أو سجلّ.
    """
    from app.config import Settings

    fields = set(Settings.model_fields)
    forbidden = {f for f in fields
                 if re.search(r"(aws|s3).*(access|secret|key)", f, re.I)}
    assert not forbidden, f"إعدادات تحمل مفاتيح وصول: {forbidden}"
    assert {"storage_backend", "s3_bucket", "s3_region"} <= fields


def test_temp_file_exception_stays_a_temp_file():
    """``os.fdopen`` مسموح فقط مع ``tempfile.mkstemp`` في الملف نفسه.

    الاستثناء الذي لا شرط له يصير قاعدة: من يريد كتابة دائمة على القرص
    سيكتبها بـ``fdopen`` ويمرّ. الشرط هنا يمنع ذلك.
    """
    for p in APP.rglob("*.py"):
        text = p.read_text(encoding="utf-8")
        if "os.fdopen(" in text:
            assert "tempfile.mkstemp" in text, (
                f"{p.name}: fdopen بلا mkstemp — كتابة دائمة متنكّرة في ملف مؤقّت"
            )
