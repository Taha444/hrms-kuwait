# -*- coding: utf-8 -*-
"""كتابٌة تعبُر الشركات — صنُف عطٍل تكرّر، فيُحرَس بالكنس لا بالحالة.

**ثلاث مرات في جولٍة واحدة** كان العطل **نسخًة ثانية من قاعدٍة صحيحة،
والعاملُة هي المعطوبة**:

1. ``_warn_no_impartial_approver`` يستعلم مقيًَّدا بالشركة، والمالك
   ``company_id = None`` — فيُصعَّد إلى لا أحد.
2. بصمٌة واحدٌة لعدّة مستقبلين تحجب كلَّ من بعد الأول.
3. و``POST /documents`` يحدّث مهامّ الانتهاء **بلا قيٍد على مستنٍد ولا
   على شركة**، والدالُة المقيَّدة اثنَي عشر سطًرا فوقه.

فبُني ``scripts/unscoped_writes.py`` يكنس الصنف كلَّه: كتابٌة جماعية لا
تسمّي صًفّا ولا شركة. **ولا يُمسَك هذا الشكل باختبار وظيفي** — تركيُب
حالٍة تُثبته يعني إفساد بيانات السويت كلّها. فيُمسَك بقراءة الشيفرة.

**والعطُل الرابع وجده الكنس**: ``POST /tasks/cleanup-orphans`` كان يكنس
المهامّ اليتيمة بلا قيد شركة، و``manage_tasks`` يحملها
``company_manager`` و``delegate`` — وكلاهما مقيٌَّد بشركته. فمديُر الشركة
الأولى يكنس مهامّ الثانية: الفعُل صحيٌح في كل صّف، **والفاعل يتخطّى
نطاقه**.
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

MGR1 = ("100000000001", "manager123")
ADMIN = ("000000000000", "admin123")


# ---------------------------------------------------------------------------
# الكنس نفسه
# ---------------------------------------------------------------------------

def test_no_bulk_write_crosses_the_company_boundary():
    """**الحارس الدائم**: لا ``update``/``delete`` جماعية بلا نطاق.

    ويستثني الجداول العامّة التي لا تحمل شركًة أصًلا (الرموز المنتهية،
    سجلّ تشغيل المهام) — فالحذف الدوري فيها مشروع.
    """
    import importlib.util
    import pathlib

    path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "unscoped_writes.py"
    spec = importlib.util.spec_from_file_location("unscoped_writes", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    found = mod.bulk_writes()
    assert not found, "كتابٌة جماعية بلا نطاق:\n" + "\n".join(
        f"  {p}:{ln}\n      " + stmt.splitlines()[0].strip()
        for p, ln, stmt in found)


def test_the_document_upload_no_longer_closes_every_expiry_task():
    """**والموضع الذي وُجد فيه العطل يُحرَس باسمه.**

    فكنٌس عامٌّ قد يُخضَّر بحيلة، وهذا يسمّي الدالة.
    """
    import inspect

    from app.routers import documents as D

    assert "update(models.Task)" not in inspect.getsource(D.upload_document)


# ---------------------------------------------------------------------------
# وكنُس المهام اليتيمة لا يتخطّى شركته
# ---------------------------------------------------------------------------

def _orphan_task(company_id: int, req_id: int) -> int:
    db = SessionLocal()
    try:
        t = models.Task(company_id=company_id, type="request_stage",
                        title="مهمٌة يتيمة للقياس",
                        related_entity_type="request", related_entity_id=req_id,
                        status="open", severity="info",
                        dedup_key=f"orphan_probe:{company_id}:{req_id}")
        db.add(t)
        db.commit()
        return t.id
    finally:
        db.close()


def _closed_request(company_id: int) -> int:
    """طلٌب منتٍه — فمهمتُه المفتوحة يتيمٌة بحّق."""
    db = SessionLocal()
    try:
        emp_id = db.scalar(select(models.Employee.id).where(
            models.Employee.company_id == company_id))
        req = models.Request(company_id=company_id, employee_id=emp_id,
                             request_type_code="REQLV", status="completed",
                             payload_json={})
        db.add(req)
        db.commit()
        return req.id
    finally:
        db.close()


def _status(task_id: int) -> str:
    db = SessionLocal()
    try:
        return db.get(models.Task, task_id).status
    finally:
        db.close()


def _cleanup(ids: list[int], req_ids: list[int]) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Task).where(models.Task.id.in_(ids)))
        db.execute(sa_delete(models.Request).where(models.Request.id.in_(req_ids)))
        db.commit()
    finally:
        db.close()


def test_cleanup_orphans_does_not_touch_another_company(client):
    """**جوهر العطل الرابع**: مديُر الشركة الأولى لا يكنس مهامّ الثانية."""
    r1, r2 = _closed_request(1), _closed_request(2)
    t1, t2 = _orphan_task(1, r1), _orphan_task(2, r2)
    try:
        resp = client.post("/api/tasks/cleanup-orphans",
                           headers=auth_headers(login(client, *MGR1)))
        assert resp.status_code == 200, resp.text[:300]
        assert _status(t1) == "dismissed", "لم يكنس مهمَة شركته"
        assert _status(t2) == "open", \
            "كنَس مهمًة في شركٍة أخرى — الفاعل تخطّى نطاقه"
    finally:
        _cleanup([t1, t2], [r1, r2])


def test_an_overseer_may_still_sweep_every_company(client):
    """ومن هو فوق الشركات يكنس الكلّ — الحارس لا يُلغي القدرة."""
    r1, r2 = _closed_request(1), _closed_request(2)
    t1, t2 = _orphan_task(1, r1), _orphan_task(2, r2)
    try:
        resp = client.post("/api/tasks/cleanup-orphans",
                           headers=auth_headers(login(client, *ADMIN)))
        assert resp.status_code == 200, resp.text[:300]
        assert _status(t1) == "dismissed" and _status(t2) == "dismissed", \
            (_status(t1), _status(t2))
    finally:
        _cleanup([t1, t2], [r1, r2])


def test_the_scope_comes_from_the_one_helper():
    """والنطاُق من ``scope_company_id`` لا من شرٍط مكتوٍب بالي;د."""
    import inspect

    from app.routers import tasks as T

    src = inspect.getsource(T.cleanup_orphan_tasks)
    assert "scope_company_id" in src, "نطاٌق مكتوٌب بالي;د في الكنس"
