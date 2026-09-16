# -*- coding: utf-8 -*-
"""عمالةُ الترخيص تُعَدّ بمن لم تنتهِ خدمته — لا بمن حالتُه «نشط».

**العطل**: موضعان يعدّان (إنذارُ تجاوز السعة في ``daily_scan``، وشاشةُ
التراخيص في ``org``)، وكلاهما ``status == "active"``. فموظفٌ «في إجازة» أو
«موقوف» يُطرح من العدد وهو مسجَّلٌ على الترخيص عند الجهة — فيمرّ ترخيصٌ
ممتلئٌ بلا إنذار، وتُقبَل عليه عمالةٌ جديدة.

**والخطأُ في الاتجاه الخطِر**: عدٌّ ناقصٌ يُسكت الإنذار الذي بُني ليُسمَع.

فصار عدًّا واحدًا (``deps.license_headcount``) يستثني من انتهت خدمته
بالقائمة الموحَّدة ``INACTIVE_EMPLOYMENT``.
"""
from __future__ import annotations

from sqlalchemy import select

from app import deps, models
from app.database import SessionLocal
from tests.conftest import auth_headers, login


def _licensed(db):
    emp = db.scalar(select(models.Employee).where(
        models.Employee.license_id.isnot(None), models.Employee.status == "active"))
    assert emp is not None, "لا موظفَ على ترخيص"
    return emp


def test_a_worker_on_leave_still_occupies_the_license():
    db = SessionLocal()
    try:
        emp = _licensed(db)
        before = deps.license_headcount(db, emp.license_id)
        for st in ("vacation", "suspended"):
            emp.status = st
            db.flush()
            assert deps.license_headcount(db, emp.license_id) == before, (
                f"«{st}» طُرح من عمالة الترخيص — والجهةُ تعدّه")
    finally:
        db.rollback()
        db.close()


def test_an_ended_service_leaves_the_license():
    db = SessionLocal()
    try:
        emp = _licensed(db)
        before = deps.license_headcount(db, emp.license_id)
        for st in deps.INACTIVE_EMPLOYMENT:
            emp.status = st
            db.flush()
            assert deps.license_headcount(db, emp.license_id) == before - 1, st
    finally:
        db.rollback()
        db.close()


def test_the_licenses_screen_counts_the_same_way(client):
    """**ونقطةُ التراخيص والإنذارُ رقمٌ واحد** — يُقاس بالردّ لا بالنصّ."""
    db = SessionLocal()
    try:
        emp = _licensed(db)
        lic_id, emp_id, old = emp.license_id, emp.id, emp.status
        company_id = emp.company_id
        emp.status = "vacation"
        db.commit()
    finally:
        db.close()
    try:
        r = client.get("/api/licenses", params={"company_id": company_id},
                       headers=auth_headers(login(client, "000000000000", "admin123")))
        assert r.status_code == 200, r.text[:200]
        row = next(x for x in r.json() if x["id"] == lic_id)
        db = SessionLocal()
        try:
            assert row["actual_workers"] == deps.license_headcount(db, lic_id), row
        finally:
            db.close()
    finally:
        db = SessionLocal()
        try:
            db.get(models.Employee, emp_id).status = old
            db.commit()
        finally:
            db.close()


def test_no_license_count_reads_the_active_status_alone():
    """ولا يعود عدٌّ ثالثٌ بالحالة وحدها — يُقرأ من الموضع الواحد."""
    import inspect

    from app import notifications
    from app.routers import org

    for mod in (notifications, org):
        src = inspect.getsource(mod)
        assert "license_headcount(" in src, mod.__name__
        assert "models.Employee.license_id == lic.id" not in src, (
            f"{mod.__name__} يعدّ عمالةَ الترخيص بنفسه")
