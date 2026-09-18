# -*- coding: utf-8 -*-
"""نسخٌة احتياطية الآن — أو مفتاُح تشفيٍر جديد.

    # مرًة واحدة: مفتاُح التشفير (يُحفظ في Railway **وفي مكاٍن آمٍن خارجه** —
    # من يفقده يفقد النسخ كلَّها)
    backend/.venv/Scripts/python.exe backend/scripts/backup_now.py --new-key

    # نسخٌة إلى الحاوية الخارجية (بمتغيّرات BACKUP_* كما في app/backup.py)
    backend/.venv/Scripts/python.exe backend/scripts/backup_now.py

    # نسخٌة إلى ملفٍّ محلي (بلا حاوية) — تحتاج BACKUP_ENCRYPTION_KEY وحده
    backend/.venv/Scripts/python.exe backend/scripts/backup_now.py --out backup.bkp
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--new-key", action="store_true", help="ولّد مفتاح تشفير جديدًا واطبعه")
    ap.add_argument("--out", help="اكتب النسخة إلى هذا الملف بدل الحاوية")
    a = ap.parse_args(argv)

    from app import backup as B

    if a.new_key:
        print(B.new_key())
        print("احفظه في BACKUP_ENCRYPTION_KEY على Railway، ونسخًة منه خارج Railway.",
              file=sys.stderr)
        return 0
    if a.out:
        key = os.environ.get("BACKUP_ENCRYPTION_KEY", "").strip()
        if not key:
            print("BACKUP_ENCRYPTION_KEY غير مضبوط", file=sys.stderr)
            return 2
        from app.config import settings
        from app.database import engine

        up = settings.upload_dir if settings.storage_backend == "local" else None
        m = B.create_archive(engine, up, Path(a.out), key)
        print(f"كُتبت {a.out}: {len(m['tables'])} جدولًا، "
              f"{sum(t['rows'] for t in m['tables'].values())} صفًّا، {m['files']['count']} ملفًّا")
        return 0
    cfg = B.BackupConfig.from_env()
    if cfg is None:
        print("BACKUP_S3_BUCKET و BACKUP_ENCRYPTION_KEY مطلوبان", file=sys.stderr)
        return 2
    print(B.run_backup(cfg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
