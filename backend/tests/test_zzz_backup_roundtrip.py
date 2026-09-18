# -*- coding: utf-8 -*-
"""النسخة التي لا تُسترجَع ليست نسخة — ذهاٌب وإياٌب على قاعدة الاختبار.

قرار المالك (2026-09-19): نسخٌة ليلية مشفَّرة خارج الخادم **باسترجاٍع
مُختبَر**. فهنا تُنسخ قاعدُة الاختبار كلُّها ومجلُد ملفات، وتُسترجع في قاعدٍة
فارغة، ويُطابَق عدُد صفوف كل جدول وبصمُة كل ملف وصفوٌف بعينها.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from app import backup as B
from app.database import engine


def _files(tmp: Path) -> Path:
    up = tmp / "uploads"
    (up / "selfies").mkdir(parents=True)
    (up / "selfies" / "a.jpg").write_bytes(b"\xff\xd8selfie-bytes")
    (up / "forms").mkdir()
    (up / "forms" / "doc.html").write_text("<p>مستند</p>", encoding="utf-8")
    return up


def test_backup_restores_every_row_and_every_file(tmp_path):
    key = B.new_key()
    up = _files(tmp_path)
    arc = tmp_path / "b.bkp"
    manifest = B.create_archive(engine, str(up), arc, key, {"commit": "test"})
    assert manifest["tables"]["employees"]["rows"] > 0
    assert manifest["files"]["count"] == 2
    # مشفَّرة: لا يُقرأ منها اسٌم ولا رقم.
    blob = arc.read_bytes()
    assert blob.startswith(B.MAGIC) and b"employees" not in blob

    target = tmp_path / "restored.db"
    url = f"sqlite:///{target.as_posix()}"
    report = B.restore_archive(arc, key, url, str(tmp_path / "files_out"), schema="metadata")
    assert report["ok"], report["problems"]
    assert report["files"] == 2 and report["rows"] == sum(
        t["rows"] for t in manifest["tables"].values())

    # وصفوٌف بعينها كما هي، بتواريخها.
    q = 'SELECT id, name, hire_date FROM employees ORDER BY id'
    with engine.connect() as a, create_engine(url).connect() as b:
        assert a.execute(text(q)).all() == b.execute(text(q)).all()


def test_the_wrong_key_restores_nothing(tmp_path):
    arc = tmp_path / "b.bkp"
    B.create_archive(engine, None, arc, B.new_key())
    with pytest.raises(ValueError):
        B.restore_archive(arc, B.new_key(), f"sqlite:///{(tmp_path / 'x.db').as_posix()}",
                          None, schema="metadata")


def test_it_never_writes_over_a_database_with_data(tmp_path):
    key = B.new_key()
    arc = tmp_path / "b.bkp"
    B.create_archive(engine, None, arc, key)
    url = f"sqlite:///{(tmp_path / 'r.db').as_posix()}"
    assert B.restore_archive(arc, key, url, None, schema="metadata")["ok"]
    with pytest.raises(RuntimeError):
        B.restore_archive(arc, key, url, None, schema="metadata")


def test_retention_keeps_the_newest_seven_and_drops_only_the_old():
    now = dt.datetime(2026, 9, 19)
    keys = [(f"k{i}", now - dt.timedelta(days=i)) for i in range(60)]
    gone = set(B.expired(keys, now, retention_days=30))
    assert gone == {f"k{i}" for i in range(31, 60)}
    few = [(f"old{i}", now - dt.timedelta(days=100 + i)) for i in range(5)]
    assert B.expired(few, now, retention_days=30) == [], "لا يُحذف آخر ما بقي"


def test_it_is_off_until_configured(monkeypatch):
    monkeypatch.delenv("BACKUP_S3_BUCKET", raising=False)
    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY", raising=False)
    assert B.BackupConfig.from_env() is None
    monkeypatch.setenv("BACKUP_S3_BUCKET", "b")
    assert B.BackupConfig.from_env() is None, "حاويٌة بلا مفتاح تشفير = نسخٌة مكشوفة"
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", B.new_key())
    cfg = B.BackupConfig.from_env()
    assert cfg and cfg.prefix.endswith("/") and cfg.retention_days == 30


def test_a_failed_job_reaches_the_company_owner():
    """لا super_admin عند العميل — فتنبيُه فشل النسخ يصل صاحب الشركات."""
    from sqlalchemy import select

    from app import models
    from app.database import SessionLocal
    from app.scheduler import _alert_job_failure

    _alert_job_failure("backup", RuntimeError("guard"))
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Task).where(
            models.Task.type == "job_failure",
            models.Task.dedup_key.like("job_fail:backup:%"))).all()
        roles = {db.get(models.User, t.assignee_user_id).role for t in rows}
        assert "company_owner" in roles, roles
        for t in rows:
            db.delete(t)
        db.commit()
    finally:
        db.close()


def test_an_empty_database_is_not_backed_up(tmp_path):
    """رابٌط خاطئ يفتح قاعدًة فارغة — ونسخٌة «ناجحة» فارغة أخطُر من لا نسخة."""
    empty = create_engine(f"sqlite:///{(tmp_path / 'empty.db').as_posix()}")
    with pytest.raises(RuntimeError):
        B.create_archive(empty, None, tmp_path / "e.bkp", B.new_key())
    assert not B.verify_restore({"tables": {}, "files": {"sha256": {}}},
                                f"sqlite:///{(tmp_path / 'empty.db').as_posix()}", None)["ok"]
