# -*- coding: utf-8 -*-
"""مصفوفة الصلاحيات (DLV-46) تطابق الشيفرة — أو يسقط هذا.

الوثيقُة تُسلَّم للعميل وصًفا لمن يفعل ماذا. ووصٌف يشيخ مع أوّل صلاحيٍة
تُضاف يُقرأ على أنه النظام وهو ماضيه. فمن يغيّر صلاحيًة أو يحرس نقطًة
يُعيد التوليد::

    backend/.venv/Scripts/python.exe backend/scripts/permissions_matrix.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


def test_the_matrix_document_matches_the_code():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "permissions_matrix", root / "backend" / "scripts" / "permissions_matrix.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    doc = (root / "docs" / "PERMISSIONS_MATRIX.md").read_text(encoding="utf-8")
    assert doc == mod.render(), (
        "docs/PERMISSIONS_MATRIX.md لا يطابق الشيفرة — أعد التوليد بـ"
        "backend/scripts/permissions_matrix.py")
