# -*- coding: utf-8 -*-
"""R9 §15 — Idempotent seed of the default catalog (request types + templates).

يشتغل من bootstrap عند كل startup: يمر على DEFAULT_REQUEST_TYPES (53) و
DEFAULT_TEMPLATES (42) ويحقن أي عنصر مفقود في DB بلا مساس بالموجود.

سبب فصله عن migration:
- migration الأصلي (j3c4d5e6f7g) شغّال، لكن لو حصل خطأ في السلسلة قبله على
  Railway (أو الـcontainer ما اتنشر لسبب) هيفضل الـcatalog فاضي
- bootstrap يشتغل يوميًا مع كل deploy، يكفل ملء الفراغ حتى لو migration فشل
- ما فيه ضرر من التشغيل المزدوج: SELECT قبل INSERT يضمن idempotency

يستخدَم من:
1. bootstrap.py — كل startup
2. app/routers/admin.py — POST /admin/ensure-catalog (تشغيل يدوي)
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


logger = logging.getLogger("hrms.catalog_seed")


def ensure_default_catalog(db: Session) -> dict:
    """يحقن أي request types أو document templates ناقصة (company_id=NULL).

    Idempotent — كل عنصر يُدرج فقط لو كوده مش موجود.

    Returns:
        {"request_types_added": N, "templates_added": M,
         "request_types_total": X, "templates_total": Y}
    """
    from .workflow import DEFAULT_REQUEST_TYPES
    from .seed import DEFAULT_TEMPLATES

    # ─── Request Types ──────────────────────────────────────────────
    existing_rt = set(db.scalars(select(models.RequestType.code).where(
        models.RequestType.company_id.is_(None)
    )).all())

    rt_added = 0
    for rt in DEFAULT_REQUEST_TYPES:
        if rt["code"] in existing_rt:
            continue
        row = models.RequestType(
            company_id=None,
            code=rt["code"],
            name=rt["name"],
            category=rt.get("category") or "عام",
            requires_physical_signature=bool(rt.get("requires_physical_signature", False)),
            produces_document=bool(rt.get("produces_document", False)),
            approval_chain_json=rt.get("approval_chain_json") or [],
            template_html=rt.get("template_html"),
            visible_to_employee=bool(rt.get("visible_to_employee", True)),
            default_template_code=rt.get("default_template_code"),
            is_active=True,
        )
        db.add(row)
        rt_added += 1

    # ─── Document Templates ─────────────────────────────────────────
    existing_tpl = set(db.scalars(select(models.DocumentTemplate.code).where(
        models.DocumentTemplate.company_id.is_(None),
        models.DocumentTemplate.code.is_not(None),
    )).all())

    tpl_added = 0
    for entry in DEFAULT_TEMPLATES:
        # (code, name, name_en, category, body_html)
        code, name, name_en, category, body = entry
        if code in existing_tpl:
            continue
        row = models.DocumentTemplate(
            company_id=None, code=code, name=name, name_en=name_en,
            category=category, body_html=body, is_active=True, version=1,
        )
        db.add(row)
        tpl_added += 1

    if rt_added or tpl_added:
        db.commit()
        logger.info("catalog_seed: +%d request_types, +%d templates",
                   rt_added, tpl_added)

    # totals for reporting
    rt_total = db.scalar(select(models.RequestType.id).where(
        models.RequestType.company_id.is_(None)).limit(1))
    tpl_total = db.scalar(select(models.DocumentTemplate.id).where(
        models.DocumentTemplate.company_id.is_(None)).limit(1))

    rt_count = len(db.scalars(select(models.RequestType.code).where(
        models.RequestType.company_id.is_(None))).all())
    tpl_count = len(db.scalars(select(models.DocumentTemplate.code).where(
        models.DocumentTemplate.company_id.is_(None))).all())

    return {
        "request_types_added": rt_added,
        "templates_added": tpl_added,
        "request_types_total": rt_count,
        "templates_total": tpl_count,
    }
