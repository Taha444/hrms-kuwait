# -*- coding: utf-8 -*-
"""ترحيل الملفات إلى التخزين الدائم — والتحقّق قبل حذف أي شيء.

**AWS-01.** نقل الملفات ليس نسًخا: النقل الذي لا يُتحقَّق منه يبدو ناجًحا
حتى يطلب أحدهم جواز موظف بعد شهر فلا يجده. ولهذا الأداة تعمل على ثلاث
مراحل منفصلة، ولا تحذف شيًئا في أي منها:

    python -m app.migrate_storage --check     ماذا في القاعدة وماذا على القرص
    python -m app.migrate_storage --upload    يرفع إلى S3 (لا يحذف الأصل)
    python -m app.migrate_storage --verify    يقارن البصمات ملًفا ملًفا

والحذف يدويّ بعد ``--verify`` نظيف ونسخة احتياطية — عمًدا: أمر يحذف بيانات
عميل لا يجوز أن يوجد في أداة يُنادى عليها بالخطأ.

ويُبلَّغ عن الصفوف التي تحمل مساًرا مطلًقا من بيئة أخرى بدل أن تُبتلع: هي
بالضبط الملفات التي تضيع بصمت في نقل غير محقَّق.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from sqlalchemy import select

from . import models
from .config import settings
from .database import SessionLocal
from .storage import LocalStorage, _to_key


def _discover_key_columns() -> list[tuple[type, str]]:
    """يكتشف الأعمدة من النماذج نفسها لا من قائمة مكتوبة بيد.

    كتبتُ القائمة يدويًّا أوًلا فأغفلت ثلاثة جداول — منها صور الحضور
    وإصدارات التواقيع. وهذا بالضبط ما يُضيّع الملفات في نقل يبدو مكتمًلا:
    ليس الملف الذي فشل رفعه بل الجدول الذي لم يخطر ببال أحد. والاكتشاف
    من النماذج يجعل عموًدا جديًدا مشمولًا يوم يُضاف لا يوم يُتذكَّر.
    """
    out: list[tuple[type, str]] = []
    for name in dir(models):
        obj = getattr(models, name)
        table = getattr(obj, "__table__", None)
        if table is None:
            continue
        for col in table.columns:
            if col.name.endswith("_path"):
                out.append((obj, col.name))
    return sorted(out, key=lambda x: (x[0].__tablename__, x[1]))


KEY_COLUMNS: list[tuple[type, str]] = _discover_key_columns()


def _all_keys(db) -> list[tuple[str, int, str]]:
    """(اسم الجدول، المعرّف، المفتاح) لكل صفّ يحمل ملًفا."""
    out = []
    for model, col in KEY_COLUMNS:
        if not hasattr(model, col):
            continue
        rows = db.scalars(select(model).where(getattr(model, col).isnot(None))).all()
        for r in rows:
            v = getattr(r, col)
            if v:
                out.append((f"{model.__tablename__}.{col}", r.id, v))
    return out


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cmd_check() -> int:
    db = SessionLocal()
    local = LocalStorage()
    try:
        rows = _all_keys(db)
        missing, absolute, ok = [], [], 0
        for table, rid, val in rows:
            if Path(val).is_absolute():
                absolute.append((table, rid, val))
            if local.exists(val):
                ok += 1
            else:
                missing.append((table, rid, val))
        print(f"صفوف تحمل ملًفا: {len(rows)}")
        print(f"  موجود على القرص: {ok}")
        print(f"  مفقود:           {len(missing)}")
        print(f"  بمسار مطلق:      {len(absolute)}")
        if missing:
            print("\nمفقود — هذه هي الملفات التي ستضيع بصمت في نقل غير محقَّق:")
            for t, i, v in missing[:25]:
                print(f"  · {t}#{i}: {v}")
            if len(missing) > 25:
                print(f"  … و{len(missing) - 25} غيرها")
        if absolute:
            print("\nبمسار مطلق — يُطبَّع إلى مفتاح نسبيّ بـ--normalize:")
            for t, i, v in absolute[:10]:
                print(f"  · {t}#{i}: {v}")
        return 0
    finally:
        db.close()


def cmd_normalize(apply_changes: bool) -> int:
    """يحوّل المسارات المطلقة إلى مفاتيح نسبيّة.

    المسار المطلق يربط الصفّ بقرص بعينه، فينكسر عند أول نقل. والتطبيع
    قبل الرفع لا بعده: بعده تُرفع الملفات على مفاتيح خاطئة.
    """
    db = SessionLocal()
    try:
        n = 0
        for model, col in KEY_COLUMNS:
            if not hasattr(model, col):
                continue
            for r in db.scalars(select(model).where(getattr(model, col).isnot(None))).all():
                v = getattr(r, col)
                k = _to_key(v)
                if k != v and not Path(k).is_absolute():
                    if apply_changes:
                        setattr(r, col, k)
                    n += 1
        if apply_changes:
            db.commit()
            print(f"طُبِّع {n} صًفا.")
        else:
            print(f"سيُطبَّع {n} صًفا. أعد التشغيل مع --apply للتنفيذ.")
        return 0
    finally:
        db.close()


def cmd_upload() -> int:
    if (settings.storage_backend or "local").lower() != "s3":
        print("STORAGE_BACKEND ليس s3 — لا وجهة للرفع.")
        return 1
    from .storage import S3Storage

    db, local, remote = SessionLocal(), LocalStorage(), S3Storage()
    try:
        rows = _all_keys(db)
        up, skipped, failed = 0, 0, []
        for table, rid, val in rows:
            key = _to_key(val)
            if Path(key).is_absolute():
                failed.append((table, rid, val, "مسار مطلق — طبّعه أوًلا"))
                continue
            if not local.exists(val):
                failed.append((table, rid, val, "غير موجود على القرص"))
                continue
            if remote.exists(key):
                skipped += 1
                continue
            remote.save_at(local.read(val), key)
            up += 1
        print(f"رُفع {up} · مرفوع سابًقا {skipped} · تعذّر {len(failed)}")
        for t, i, v, why in failed[:25]:
            print(f"  · {t}#{i}: {v} — {why}")
        print("\nلم يُحذف شيء. شغّل --verify قبل أي حذف.")
        return 1 if failed else 0
    finally:
        db.close()


def cmd_verify() -> int:
    """يقارن بصمة كل ملف على الوجهتين. هذا هو ما يجعل النقل محقًَّقا."""
    if (settings.storage_backend or "local").lower() != "s3":
        print("STORAGE_BACKEND ليس s3 — لا شيء يُقارَن.")
        return 1
    from .storage import S3Storage

    db, local, remote = SessionLocal(), LocalStorage(), S3Storage()
    try:
        rows = _all_keys(db)
        same, diff, absent = 0, [], []
        for table, rid, val in rows:
            key = _to_key(val)
            if not remote.exists(key):
                absent.append((table, rid, val))
                continue
            if not local.exists(val):
                # على القرص لا شيء والملف في S3 — مقبول بعد نقل مكتمل
                same += 1
                continue
            if _sha(local.read(val)) == _sha(remote.read(key)):
                same += 1
            else:
                diff.append((table, rid, val))
        print(f"مطابق: {same} · مختلف: {len(diff)} · غير موجود في S3: {len(absent)}")
        for t, i, v in (diff + absent)[:25]:
            print(f"  · {t}#{i}: {v}")
        if diff or absent:
            print("\n✘ النقل غير مكتمل — لا تحذف المجلد القديم.")
            return 1
        print("\n✔ كل ملف في القاعدة له مقابل مطابق في S3.")
        print("  يجوز الآن حذف المجلد القديم — بعد نسخة احتياطية.")
        return 0
    finally:
        db.close()


def main() -> int:
    if "--check" in sys.argv:
        return cmd_check()
    if "--normalize" in sys.argv:
        return cmd_normalize("--apply" in sys.argv)
    if "--upload" in sys.argv:
        return cmd_upload()
    if "--verify" in sys.argv:
        return cmd_verify()
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
