# -*- coding: utf-8 -*-
"""M14 #6 — تسويةُ حالة نهاية الخدمة موسومةٌ من الخادم: مبدئيةٌ غير صالحة للصرف حتى مرحلة ``settled``."""
from pathlib import Path

from app import models
from app.routers import eos as eos_router

ROOT = Path(__file__).resolve().parents[2] / "frontend" / "src"


def _serialize(status):
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        emp = db.query(models.Employee).first()
        case = models.EosCase(company_id=emp.company_id, employee_id=emp.id, status=status,
                              termination_reason="termination")
        return eos_router._serialize_case(db, case)
    finally:
        db.close()


def test_only_the_settled_stage_is_final_and_payable():
    for st in ("initiated", "calculated", "approved", "clearance", "acknowledged"):
        d = _serialize(st)
        assert d["is_final"] is False and d["not_for_payment"] is True, st
    d = _serialize("settled")
    assert d["is_final"] is True and d["not_for_payment"] is False


def test_the_screen_shows_the_flag_in_both_languages():
    src = (ROOT / "pages" / "EosCases.tsx").read_text(encoding="utf-8")
    assert "sel.is_final" in src and "eosc_final" in src and "eosc_preliminary" in src
    tr = (ROOT / "i18n_screens.ts").read_text(encoding="utf-8")
    for key in ("eosc_final", "eosc_preliminary"):
        line = next(l for l in tr.splitlines() if l.strip().startswith(key + ":"))
        assert "ar:" in line and "en:" in line
