# -*- coding: utf-8 -*-
"""مخطط قاعدة البيانات (DLV-44) يطابق النماذج — أو يسقط هذا.

ومن يضيف جدوًلا يضيف سطَر وصفه في شرح نموذجه: جدوٌل بلا وصٍف في وثيقة
التسليم يُسأل عنه كاتبُه بعد رحيله.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


def _mod():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("db_schema_doc", root / "scripts" / "db_schema_doc.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_schema_document_matches_the_models():
    mod = _mod()
    assert mod.OUT.read_text(encoding="utf-8") == mod.render(), (
        "docs/DATABASE_SCHEMA.md لا يطابق النماذج — أعد التوليد بـbackend/scripts/db_schema_doc.py")


def test_every_table_has_its_own_description():
    from app.database import Base

    mod = _mod()
    bare = sorted(mp.class_.__name__ for mp in Base.registry.mappers
                  if not mod._first_line(mp.class_))
    assert not bare, f"نماذج بلا سطر وصف: {bare}"
