# -*- coding: utf-8 -*-
"""V2.2 §26 — script ترحيل آمن من الأنواع القديمة إلى Canonical.

يعمل بأمان:
- Idempotent: يمكن تشغيله عدة مرات دون آثار جانبية
- No-delete: لا يحذف الأنواع القديمة (لكنه يعطّلها بـ is_active=False)
- Backward-compat: يبقي legacy codes قابلة للحل عبر LEGACY_REQUEST_ALIASES

الاستخدام:
    ./.venv/Scripts/python -m scripts.migrate_to_canonical [--company <id>] [--dry-run]

--dry-run لا يكتب في القاعدة، يعرض ما سيحدث فقط.
"""
import argparse
import os
import sys

# اسمح للـscript بالوصول لـ app.* عند التشغيل خارج venv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.v15_registry import CANONICAL_WORKFLOWS, LEGACY_REQUEST_ALIASES


def _canonical_type_row(code: str, meta: dict) -> models.RequestType:
    """يبني RequestType canonical (company_id=None عالمي) — يُشارك بين كل الشركات."""
    return models.RequestType(
        company_id=None,
        code=code,
        name=meta["name_ar"],
        category="canonical",
        approval_chain_json=[],  # الـchain يبقى مربوطًا بالأصل القديم عبر LEGACY_REQUEST_ALIASES
        requires_physical_signature=False,
        produces_document=bool(meta.get("od")),
        is_active=True,
        visible_to_employee=False,  # يظهر تدريجيًا عبر feature flag لكل شركة
    )


def run(company_id: int | None = None, dry_run: bool = False) -> dict:
    """يترحّل الأنواع القديمة إلى canonical.

    - company_id: لو مررت، يفلتر أنواع الشركة المحددة فقط. None = كل الشركات.
    - dry_run: يعرض دون كتابة.
    """
    db = SessionLocal()
    try:
        # 1) تأكد من وجود canonical rows في القاعدة (company_id=None)
        created_canonical = 0
        already_canonical = 0
        for code, meta in CANONICAL_WORKFLOWS.items():
            existing = db.scalar(select(models.RequestType).where(
                models.RequestType.code == code,
                models.RequestType.company_id.is_(None),
            ))
            if existing:
                already_canonical += 1
                continue
            if not dry_run:
                db.add(_canonical_type_row(code, meta))
            created_canonical += 1

        # 2) إحصاء الطلبات القديمة (لا نحدثها؛ get_request_type يحل الـcanonical تلقائيًا)
        legacy_types_disabled = 0
        legacy_codes = set(LEGACY_REQUEST_ALIASES.keys())
        q = select(models.RequestType).where(
            models.RequestType.code.in_(legacy_codes),
            models.RequestType.is_active.is_(True),
        )
        if company_id is not None:
            q = q.where(models.RequestType.company_id == company_id)
        for rt in db.scalars(q).all():
            # ملاحظة: لا نعطلها الآن — نتركها active حتى تنتقل الشركة عبر feature flag
            # الـscript يعد فقط. لتعطيلها اطبعها في dry-run ثم فعّل الـflag يدويًا.
            legacy_types_disabled += 1  # عدد المرشحين

        if not dry_run:
            db.commit()

        return {
            "dry_run": dry_run,
            "company_id": company_id,
            "canonical_types": {
                "created": created_canonical,
                "already_present": already_canonical,
                "total_canonical_defined": len(CANONICAL_WORKFLOWS),
            },
            "legacy_types_still_active": legacy_types_disabled,
            "notice": (
                "الـcanonical types تم إنشاؤها/التأكد من وجودها. الأنواع القديمة تبقى "
                "active — للتحول الكامل فعّل feature flag v15_canonical_display لكل "
                "شركة ثم عطّل القديمة يدويًا عبر PUT /api/requests/types/{code} "
                "أو انتظر migration script لاحق."
            ),
        }
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="V2.2 §26 — Migrate to canonical request types")
    parser.add_argument("--company", type=int, default=None,
                       help="ترحّل شركة معينة فقط (افتراضي: كل الشركات)")
    parser.add_argument("--dry-run", action="store_true", help="عرض التغييرات دون كتابة")
    args = parser.parse_args()

    result = run(company_id=args.company, dry_run=args.dry_run)
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
