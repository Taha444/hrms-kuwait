# -*- coding: utf-8 -*-
"""تقريرُ ما تركه الماضي يرى ما تركه — لا يمرّ أعمى.

``scripts/ended_service_leftovers.py`` يُشغَّل على قاعدة الإنتاج ليسمّي حساباتٍ
نشطةً لمن انتهت خدمته، ومهامَّ مفتوحةً في صناديقهم. وتقريرٌ لا يرى الحالةَ
التي كُتب لها يقول «لا شيء يُعالَج» وهناك ما يُعالَج — فتُصنَع الحالةُ هنا
كما هي هناك، ويُشترط أن يراها.
"""
from __future__ import annotations

import importlib.util
import pathlib

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal

_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "ended_service_leftovers.py"


def _load():
    spec = importlib.util.spec_from_file_location("ended_service_leftovers", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_report_sees_a_legacy_ended_account_and_its_open_task():
    mod = _load()
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == "100000000002"))
        e = db.get(models.Employee, u.employee_id)
        old = e.status
        e.status = "terminated"          # ملفٌّ منتهٍ، والحسابُ نشطٌ كما كان
        t = models.Task(company_id=u.company_id, assignee_user_id=u.id,
                        type="document", title="مهمةُ قياسٍ عالقة", status="open")
        db.add(t)
        db.commit()
        uid, tid, eid = u.id, t.id, e.id
    finally:
        db.close()
    try:
        out = mod.report()
        assert any(a[0] == uid for a in out["accounts"]), out["accounts"]
        assert any(x[0] == tid for x in out["tasks"]), out["tasks"]
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.Task).where(models.Task.id == tid))
            db.get(models.Employee, eid).status = old
            db.commit()
        finally:
            db.close()


def test_the_report_is_quiet_on_a_clean_base():
    out = _load().report()
    assert set(out) == {"accounts", "tasks", "delegations"}
