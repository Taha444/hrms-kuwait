# -*- coding: utf-8 -*-
"""Backfill — استخراج تواريخ الانتهاء للمستندات المرفوعة قبل الإصلاح (QA-06).

المستندات التي رُفعت قبل ربط الـOCR بالرفع تركت expiry_date فارًغا، فلا يراها
محرك الانتهاء ولا العدادات. هذا السكربت يمرّ عليها ويقرأ تاريخها من الملف
نفسه، ثم يزامن التصاريح.

التشغيل (من مجلد backend):

    python -m scripts.backfill_document_expiry            # تقرير فقط، بلا كتابة
    python -m scripts.backfill_document_expiry --apply    # يكتب فعلًا

لا يلمس مستنًدا له تاريخ بالفعل — الإدخال البشري لا يُصحَّح بآلة.
يطبع تقريًرا بالناجح والفاشل كما تشترط SKILL-6.
"""
from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import select

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models, ocr  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.routers.documents import _as_date, _sync_permit_from_document  # noqa: E402


def run(apply: bool = False) -> dict:
    db = SessionLocal()
    stats = {"scanned": 0, "filled": 0, "no_date_found": 0,
             "file_missing": 0, "failed": 0, "permits_synced": 0}
    failures: list[str] = []
    try:
        docs = db.scalars(select(models.Document).where(
            models.Document.expiry_date.is_(None),
            models.Document.is_current == True,  # noqa: E712
        )).all()
        for d in docs:
            stats["scanned"] += 1
            if not d.file_path or not os.path.exists(d.file_path):
                stats["file_missing"] += 1
                continue
            try:
                read = ocr.extract(d.document_type_code, d.file_path) or {}
            except Exception as exc:  # noqa: BLE001
                stats["failed"] += 1
                failures.append(f"#{d.id} {d.document_type_code}: {exc}")
                continue
            guess = _as_date(read.get("expiry_date"))
            if not guess:
                stats["no_date_found"] += 1
                continue
            stats["filled"] += 1
            if apply:
                d.expiry_date = guess
                before = db.scalar(select(models.Permit).where(
                    models.Permit.employee_id == d.entity_id))
                _sync_permit_from_document(db, d)
                if before is None:
                    stats["permits_synced"] += 1
        if apply:
            db.commit()
    finally:
        db.close()

    mode = "APPLIED" if apply else "DRY-RUN (لم يُكتب شيء)"
    print(f"\n=== Backfill تواريخ الانتهاء — {mode} ===")
    for k, v in stats.items():
        print(f"  {k:16} {v}")
    if failures:
        print("\n  إخفاقات القراءة:")
        for f in failures[:20]:
            print(f"    - {f}")
        if len(failures) > 20:
            print(f"    ... و{len(failures) - 20} أخرى")
    if not apply and stats["filled"]:
        print(f"\n  أعد التشغيل بـ--apply لكتابة {stats['filled']} تاريًخا.")
    return stats


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="اكتب التواريخ فعلًا (الافتراضي: تقرير فقط)")
    run(apply=ap.parse_args().apply)
