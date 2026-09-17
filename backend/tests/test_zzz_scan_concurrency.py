# -*- coding: utf-8 -*-
"""المسحُ اليدويُّ لا يتزامن مع جولةٍ جارية — قفلٌ للمهمة لا للجولة وحدها.

``run_once`` يمنع **تكرارَ الجولة** (مفتاحُها اليوم) لا **التزامنَ** بين
جولتين بمفتاحين. و``POST /tasks/run-scan`` كان يُشغّل ``daily_scan`` بلا قفلٍ
أصلًا — فإن تزامن مع المجدوَل تسابقا على مفاتيح المهام نفسها، فيسقط أحدُهما
بتصادم ``uq_tasks_open_dedup``.
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete, select

from app import models
from app.clock import now as kuwait_now
from app.database import SessionLocal
from tests.conftest import auth_headers, login

MGR = ("100000000001", "manager123")


def _running(key: str) -> None:
    db = SessionLocal()
    try:
        db.add(models.JobRun(job="daily_scan", run_key=key, status="running",
                             started_at=kuwait_now().replace(tzinfo=None), holder="قياس"))
        db.commit()
    finally:
        db.close()


def _drop(prefix: str) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.JobRun).where(
            models.JobRun.job == "daily_scan", models.JobRun.run_key.like(prefix + "%")))
        db.commit()
    finally:
        db.close()


def test_a_manual_scan_waits_for_a_running_one(client):
    _running("zzz-scheduled-probe")
    try:
        r = client.post("/api/tasks/run-scan", headers=auth_headers(login(client, *MGR)))
        assert r.status_code == 409, (r.status_code, r.text[:200])
    finally:
        _drop("zzz-scheduled-probe")


def test_a_manual_scan_runs_and_is_recorded_when_nothing_else_runs(client):
    r = client.post("/api/tasks/run-scan", headers=auth_headers(login(client, *MGR)))
    assert r.status_code == 200, (r.status_code, r.text[:200])
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.JobRun).where(
            models.JobRun.job == "daily_scan",
            models.JobRun.run_key.like("manual:%"))).all()
        assert rows and all(x.status == "done" for x in rows), [(x.run_key, x.status) for x in rows]
    finally:
        db.close()
        _drop("manual:")


def test_a_stale_running_row_does_not_block_forever(client):
    """والجولةُ العالقة (أقدم من المهلة) لا تحجب المسحَ إلى الأبد."""
    from datetime import timedelta

    from app.job_lock import STALE_AFTER

    db = SessionLocal()
    try:
        db.add(models.JobRun(job="daily_scan", run_key="zzz-stale-probe", status="running",
                             started_at=(kuwait_now() - STALE_AFTER - timedelta(minutes=5)
                                         ).replace(tzinfo=None), holder="قياس"))
        db.commit()
    finally:
        db.close()
    try:
        r = client.post("/api/tasks/run-scan", headers=auth_headers(login(client, *MGR)))
        assert r.status_code == 200, (r.status_code, r.text[:200])
    finally:
        _drop("zzz-stale-probe")
        _drop("manual:")
