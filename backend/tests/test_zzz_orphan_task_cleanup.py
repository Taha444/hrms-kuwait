# -*- coding: utf-8 -*-
"""المسح اليومي يُغلق المهام والتصعيدات اليتيمة (SW-007، 2026-09-23).

على الإنتاج: 112 عنصرًا على حساب HR بينها 69 تصعيد SLA «حرج» لطلباتٍ غير موجودة
(``GET /requests/{id}`` = 404) وصندوق الطلبات صفر. لا صفّ يُحذف: يُغلق بحالة
``dismissed`` وسببٍ مكتوب.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models, task_cleanup
from app.database import SessionLocal
from app.notifications import daily_scan
from tests.conftest import purge

GONE = 987654321          # رقم طلبٍ لا وجود له


def _t(db, **kw):
    t = models.Task(status="open", severity="critical", title="x", **kw)
    db.add(t)
    db.flush()
    return t


def test_daily_scan_closes_orphans_and_escalations_of_closed_tasks_but_not_live_ones():
    db = SessionLocal()
    orphan = _t(db, type="request_stage", related_entity_type="request", related_entity_id=GONE,
                dedup_key="orph:1")
    closed_src = models.Task(type="request_stage", title="src", status="dismissed")
    live_src = models.Task(type="config_gap", title="live", status="open", severity="info")
    db.add_all([closed_src, live_src])
    db.flush()
    esc_dead = _t(db, type="sla_escalation", dedup_key=f"sla_escalation:{closed_src.id}:u1")
    esc_gone = _t(db, type="sla_escalation", dedup_key="sla_escalation:999999999:u1")
    esc_live = _t(db, type="sla_escalation", dedup_key=f"sla_escalation:{live_src.id}:u1")
    esc_orphan_req = _t(db, type="sla_escalation", related_entity_type="request",
                        related_entity_id=GONE, dedup_key="sla_escalation:not-a-task")
    db.commit()
    ids = [orphan.id, closed_src.id, live_src.id, esc_dead.id, esc_gone.id, esc_live.id,
           esc_orphan_req.id]
    try:
        res = daily_scan(db)
        assert res["cleaned"] >= 4, res
        db.expire_all()
        st = {i: db.get(models.Task, i).status for i in ids}
        assert st[orphan.id] == "dismissed", "مهمة طلبٍ غير موجود بقيت مفتوحة"
        assert st[esc_dead.id] == "dismissed", "تصعيد مهمةٍ مُغلقة بقي مفتوحًا"
        assert st[esc_gone.id] == "dismissed", "تصعيد مهمةٍ زالت بقي مفتوحًا"
        assert st[esc_orphan_req.id] == "dismissed", "تصعيدٌ لطلبٍ غير موجود بقي مفتوحًا"
        assert st[esc_live.id] == "open", "أُغلق تصعيدُ مهمةٍ ما زالت مفتوحة"
        assert st[live_src.id] == "open"
        assert "أُغلقت آلًيا" in (db.get(models.Task, esc_dead.id).detail or ""), "بلا سبب مكتوب"
        # وإعادة التشغيل لا تجد شيئًا آخر.
        assert task_cleanup.run(db, apply=False, only=task_cleanup.AUTOMATIC_BUCKETS
                                )["orphan_escalations"]["count"] == 0
    finally:
        db.rollback()
        purge(db, "tasks", ids)
        db.commit()
        db.close()


def test_a_branch_gap_task_closes_once_the_branch_has_coordinates_or_is_gone():
    import secrets

    db = SessionLocal()
    co = models.Company(name="شركة اختبار الفجوات")
    db.add(co)
    db.flush()
    fixed = models.Branch(company_id=co.id, name="a", code="A", latitude=29.3, longitude=47.9,
                          qr_secret=secrets.token_hex(8))
    missing = models.Branch(company_id=co.id, name="b", code="B", qr_secret=secrets.token_hex(8))
    db.add_all([fixed, missing])
    db.flush()
    mk = lambda key: _t(db, type="config_gap", company_id=co.id, dedup_key=key)  # noqa: E731
    t_fixed = mk(f"branch_no_coords:{fixed.id}:u8")
    t_still = mk(f"branch_no_coords:{missing.id}:u8")
    t_gone = mk("branch_no_coords:987654321:u8")
    db.commit()
    ids = [t_fixed.id, t_still.id, t_gone.id]
    cid, bids = co.id, [fixed.id, missing.id]
    try:
        task_cleanup.run(db, apply=True, only=task_cleanup.AUTOMATIC_BUCKETS)
        db.expire_all()
        assert db.get(models.Task, t_fixed.id).status == "dismissed"
        assert db.get(models.Task, t_gone.id).status == "dismissed"
        assert db.get(models.Task, t_still.id).status == "open", "أُغلقت علّةٌ قائمة"
    finally:
        purge(db, "tasks", ids)
        purge(db, "branches", bids)
        purge(db, "companies", [cid])
        db.commit()
        db.close()
