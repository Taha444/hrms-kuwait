# -*- coding: utf-8 -*-
"""البدُل المعتمد يصدر بقرار مكتوب — قرار المالك (2026-09-18).

كان البدُل يُعتمد ويُصرف فعًلا (``_apply_allowance``) ولا ورقَة به: مٌال
يتغيّر بلا قرار. والقرار: ما يغيّر المال يصدر به «قرار تغيير وظيفي»
(OD-005) على قالب «قرار بدل أو مكافأة» (``HRMS-PR-020``). وتغييُر الوردية
بلا مستند — سجلُّ اعتماده يكفي.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app import v15_registry as R
from app import workflow as W
from app.database import SessionLocal
from tests.test_zzz_allowance_effect import _grant, _purge


def test_the_allowance_type_declares_its_decision():
    rt = {t["code"]: t for t in W.DEFAULT_REQUEST_TYPES}["REQALLOW"]
    assert rt.get("produces_document") is True
    assert rt.get("default_template_code") == "HRMS-PR-020"
    assert R.canonical_od_for("REQALLOW", "HRMS-PR-020") == "OD-005"


def test_the_shift_change_stays_without_a_document():
    rt = {t["code"]: t for t in W.DEFAULT_REQUEST_TYPES}["REQSHIFT"]
    assert not rt.get("produces_document")


def test_an_approved_allowance_leaves_a_decision_in_readable_words(client):
    rid = _grant(client, 25.0, recurring=True)
    try:
        db = SessionLocal()
        try:
            docs = db.scalars(select(models.RequestDocument).where(
                models.RequestDocument.request_id == rid,
                models.RequestDocument.kind == "generated_pdf")).all()
            assert docs, "بدٌل معتمد بلا ورقة قرار"
            req = db.get(models.Request, rid)
            rt = db.scalar(select(models.RequestType).where(
                models.RequestType.code == "REQALLOW",
                models.RequestType.company_id == req.company_id))
            if rt is None:
                rt = db.scalar(select(models.RequestType).where(
                    models.RequestType.code == "REQALLOW"))
            body = "\n".join(W._body_lines(rt, req, db.get(models.Employee, req.employee_id)))
        finally:
            db.close()
        assert "بدل مواصلات" in body, body
        assert "transport" not in body and "True" not in body, body
        assert "25.000" in body, body
    finally:
        _purge(rid)
