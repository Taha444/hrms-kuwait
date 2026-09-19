# -*- coding: utf-8 -*-
"""كشف الشركة — يجد المحلَّ المكرر وموظفي الاختبار، ولا يكتب شيًئا."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "company_audit.py"


def _mod():
    spec = importlib.util.spec_from_file_location("company_audit", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_it_flags_the_same_shop_under_old_and_new_codes_and_qa_staff():
    m = _mod()
    branches = [
        {"id": 6, "code": "GUF6", "name": "معرض ريم فاشن", "address": "القبلة"},
        {"id": 30, "code": "GU06", "name": "معرض ريم فاشن للأقمشة",
         "address": "العاصمة — سوق الصفاة — الرقم الآلي للعنوان: 10229888"},
        {"id": 31, "code": "GU07", "name": "سلفر فاشن",
         "address": "العاصمة — الرقم الآلي للعنوان: 10234492"},
        {"id": 41, "code": "GUF41", "name": "QA Branch41", "address": None},
    ]
    employees = [
        {"id": 1, "name": "QA Branch41 NoSupervisor Test", "job_title": "QA Tester", "branch_id": 41},
        {"id": 2, "name": "أحمد", "job_title": "بائع", "branch_id": 6},
        {"id": 3, "name": "سالم", "job_title": "بائع", "branch_id": None},
    ]
    rep = m.audit(branches, employees)
    pairs = [{x["id"] for x in members} for _r, members in rep["duplicates"]]
    assert {6, 30} in pairs, rep["duplicates"]
    assert not any({30, 31} <= p for p in pairs)
    assert [e["id"] for e in rep["qa"]] == [1]
    assert [e["id"] for e in rep["unassigned"]] == [3]


def test_it_never_writes():
    src = SCRIPT.read_text(encoding="utf-8")
    writes = re.findall(r"\.(post|put|patch|delete)\(", src)
    assert writes == ["post"], writes          # الدخول وحده
    assert '"/auth/login"' in src
