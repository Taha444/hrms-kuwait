# -*- coding: utf-8 -*-
"""M22 #3 — لا يُسجَّل «نجاح» على حدثٍ اسمُه فشلٌ أو رفض.

القاعدة في مكانٍ واحد (``deps.FAILURE_ACTIONS`` / ``result_for``). والحارس يستخرج أسماء الأحداث من
**الشيفرة نفسها**، فحدثُ فشلٍ يُضاف غدًا بلا تسجيلٍ هنا يسقط الاختبار لا أن يمرّ صامتًا.
"""
import re
from pathlib import Path

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.deps import FAILURE_ACTIONS, audit, result_for

APP = Path(__file__).resolve().parents[1] / "app"
FAILURE_NAME = re.compile(r"^(FORBIDDEN\w*|\w+_fail|\w+_failed)$")


def test_every_failure_named_action_in_the_code_is_registered_as_failure():
    actions = set()
    for f in APP.rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        actions |= set(re.findall(r"audit\(\s*[\w.]+\s*,\s*[\w.]+\s*,\s*\"([A-Za-z_]+)\"", text))
        actions |= set(re.findall(r"action=\"([A-Za-z_]+)\"", text))
    failing = {a for a in actions if FAILURE_NAME.match(a)}
    assert failing, "لم يُستخرج أيُّ حدث فشل — الاستخراج معطوب"
    assert not (failing - FAILURE_ACTIONS), f"أحداثُ فشلٍ تُسجَّل نجاحًا: {sorted(failing - FAILURE_ACTIONS)}"


def test_audit_writes_failure_for_a_denial_and_success_otherwise():
    assert result_for("FORBIDDEN_SCOPE_ACCESS") == "failure"
    assert result_for("totp_login_fail") == "failure"
    assert result_for("download_document") == "success"
    assert result_for("anything", "conflict") == "conflict"
    db = SessionLocal()
    try:
        audit(db, None, "totp_fail", "user", 0, detail="m22-result-probe")
        audit(db, None, "download_document", "user", 0, detail="m22-result-probe")
        db.flush()
        rows = {r.action: r.result for r in db.scalars(select(models.AuditLog).where(
            models.AuditLog.detail == "m22-result-probe")).all()}
        assert rows == {"totp_fail": "failure", "download_document": "success"}
    finally:
        db.rollback()
        db.close()
