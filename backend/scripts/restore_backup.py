# -*- coding: utf-8 -*-
"""استرجاُع نسخٍة احتياطية في قاعدٍة **فارغة** — ثم التحقّق منها.

لا يكتب فوق قاعدٍة فيها بيانات (إلا بـ``--force`` عن قصد): خطأٌ في الرابط
لا يمحو الإنتاج. ويُطابِق بعد الاسترجاع عدَد صفوف كل جدول وبصمَة كل ملف
بما في بيان النسخة، ويطبع النتيجة.

    # أحدث نسخة من الحاوية إلى قاعدٍة جديدة فارغة
    backend/.venv/Scripts/python.exe backend/scripts/restore_backup.py \\
        --from-s3 --target-db "postgresql://…/hrms_restore" --files-dir ./uploads_restored

    # من ملفٍّ محلي
    backend/.venv/Scripts/python.exe backend/scripts/restore_backup.py \\
        --archive backup.bkp --target-db "postgresql://…/hrms_restore" --files-dir ./uploads_restored

يلزم ``BACKUP_ENCRYPTION_KEY`` (ومتغيّرات الحاوية مع ``--from-s3``).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--archive", help="ملف النسخة المحلي")
    src.add_argument("--from-s3", nargs="?", const="", metavar="OBJECT",
                     help="من الحاوية: اسم النسخة، أو بلا قيمة لأحدثها")
    ap.add_argument("--target-db", required=True, help="رابط القاعدة الهدف (فارغة)")
    ap.add_argument("--files-dir", help="مجلد استرجاع الملفات المرفوعة")
    ap.add_argument("--schema", choices=("alembic", "metadata"), default="alembic",
                    help="بناء المخطط بالترحيلات (الافتراضي) أو من النماذج")
    ap.add_argument("--force", action="store_true", help="اكتب ولو كانت القاعدة غير فارغة")
    a = ap.parse_args(argv)

    from app import backup as B

    key = os.environ.get("BACKUP_ENCRYPTION_KEY", "").strip()
    if not key:
        print("BACKUP_ENCRYPTION_KEY غير مضبوط", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(a.archive) if a.archive else Path(tmp) / "download.bkp"
        if a.from_s3 is not None:
            cfg = B.BackupConfig.from_env()
            if cfg is None:
                print("متغيّرات الحاوية غير مضبوطة", file=sys.stderr)
                return 2
            name = B.download(cfg, a.from_s3 or None, archive)
            print(f"نُزّلت {name}")
        report = B.restore_archive(archive, key, a.target_db, a.files_dir,
                                   schema=a.schema, force=a.force)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print("✓ الاسترجاع مطابق للبيان" if report["ok"] else "✗ الاسترجاع لا يطابق البيان")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
