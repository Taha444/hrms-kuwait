# -*- coding: utf-8 -*-
"""V1.5 Phase 5 — Feature Flags (V1.5 §3 الترحيل الآمن: Feature Flags per company).

كل feature flag يمثّل تحوّلًا سلوكيًا للنظام يمكن تفعيله لشركة واحدة أو كل الشركات
لتجربة السلوك الجديد قبل النشر النهائي. القيمة المتقدّمة (الأخصّ) تعلو على العام:

    شركة X: قيمة صريحة  >>  العام (company_id NULL)  >>  default الكود

استخدام نموذجي:
    from app.feature_flags import is_enabled, V15_CANONICAL_DISPLAY
    if is_enabled(db, company_id, V15_CANONICAL_DISPLAY):
        return canonical_response()
    return legacy_response()
"""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


# ==============================================================================
# سجل الـ flags المعروفة — الاسم + الوصف + القيمة الافتراضية (إذا لم توجد صف قاعدة)
# ==============================================================================
V15_CANONICAL_DISPLAY = "v15_canonical_display"
V15_STATUS_LABELS = "v15_status_labels"
V15_DOCUMENT_LIFECYCLE = "v15_document_lifecycle"
V15_STEP_TYPE_ACTIONS = "v15_step_type_actions"
V15_LEGACY_CATALOG_HIDDEN = "v15_legacy_catalog_hidden"

REGISTRY: dict[str, dict] = {
    V15_CANONICAL_DISPLAY: {
        "description_ar": "يُعرض كود canonical WF-* في الواجهة بدل الكود القديم (leave, salary_certificate...)",
        "default": False,
    },
    V15_STATUS_LABELS: {
        "description_ar": "يُعرض label V1.5 (IN_REVIEW/NEEDS_INFO/...) كأساسي بدل labels V1.3",
        "default": False,
    },
    V15_DOCUMENT_LIFECYCLE: {
        "description_ar": "يُعرض lifecycle_status الجديد (GENERATED/SIGNED/...) بدل print_status القديم",
        "default": False,
    },
    V15_STEP_TYPE_ACTIONS: {
        "description_ar": "الواجهة تُظهر الأزرار حسب step_type (DECISION/VALIDATION/EXECUTION)",
        "default": False,
    },
    V15_LEGACY_CATALOG_HIDDEN: {
        "description_ar": "يخفي أكواد PRN-* وREQ-* القديمة من كتالوج الطلبات — يعرض canonical فقط",
        "default": False,
    },
}


def _parse_value(v: str | None) -> bool:
    """يحوّل قيمة نصية إلى bool. القيم المفعّلة: on/true/1/yes."""
    if v is None:
        return False
    return str(v).strip().lower() in ("on", "true", "1", "yes", "enabled")


def is_enabled(db: Session, company_id: int | None, key: str) -> bool:
    """يقرأ قيمة الـ flag لشركة معيّنة مع fallback للعام ثم لـ default الكود.

    القراءة مباشرة بلا cache — الجداول صغيرة جدًا والقيم تُغيَّر نادرًا؛ ولو استُدعيت
    في hot-path يمكن إضافة LRU لاحقًا. لا نستخدم LRU الآن لأنه يخفي تغييرات الإدارة
    في الوقت الحقيقي.
    """
    # 1) قيمة خاصة بالشركة
    if company_id is not None:
        row = db.scalar(
            select(models.FeatureFlag).where(
                models.FeatureFlag.key == key,
                models.FeatureFlag.company_id == company_id,
            )
        )
        if row:
            return _parse_value(row.value)
    # 2) قيمة عامة
    row = db.scalar(
        select(models.FeatureFlag).where(
            models.FeatureFlag.key == key,
            models.FeatureFlag.company_id.is_(None),
        )
    )
    if row:
        return _parse_value(row.value)
    # 3) default الكود
    meta = REGISTRY.get(key, {})
    return bool(meta.get("default", False))


def set_flag(db: Session, key: str, value: str, *,
             company_id: int | None = None, note: str | None = None,
             updated_by_user_id: int | None = None) -> models.FeatureFlag:
    """يضبط قيمة flag لشركة (أو للجميع إن كان company_id=None). Upsert."""
    if key not in REGISTRY:
        raise ValueError(f"مفتاح flag غير معروف: {key!r}")
    row = db.scalar(
        select(models.FeatureFlag).where(
            models.FeatureFlag.key == key,
            models.FeatureFlag.company_id == company_id if company_id is not None
            else models.FeatureFlag.company_id.is_(None),
        )
    )
    if row:
        row.value = value
        row.note = note
        row.updated_at = datetime.utcnow()
        row.updated_by_user_id = updated_by_user_id
    else:
        row = models.FeatureFlag(
            key=key, company_id=company_id, value=value, note=note,
            updated_at=datetime.utcnow(), updated_by_user_id=updated_by_user_id,
        )
        db.add(row)
    db.commit()
    return row


def list_effective(db: Session, company_id: int | None) -> dict[str, dict]:
    """يعيد الحالة الفعّالة لكل الـ flags للشركة (للـ dashboard). كل مدخل يبيّن:
    - value: القيمة الفعّالة (bool)
    - source: 'company' / 'global' / 'default'
    - description_ar
    """
    out: dict[str, dict] = {}
    for key, meta in REGISTRY.items():
        source = "default"
        value = meta.get("default", False)
        # global
        g = db.scalar(select(models.FeatureFlag).where(
            models.FeatureFlag.key == key, models.FeatureFlag.company_id.is_(None)
        ))
        if g:
            value = _parse_value(g.value)
            source = "global"
        # company-specific
        if company_id is not None:
            c = db.scalar(select(models.FeatureFlag).where(
                models.FeatureFlag.key == key, models.FeatureFlag.company_id == company_id
            ))
            if c:
                value = _parse_value(c.value)
                source = "company"
        out[key] = {
            "value": value, "source": source,
            "description_ar": meta.get("description_ar", ""),
            "default": meta.get("default", False),
        }
    return out
