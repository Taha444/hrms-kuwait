# -*- coding: utf-8 -*-
"""ترقيٌة تُعتمد ولا يتغيّر راتب — ومفتاٌح لا يطابق نوًعا.

**العطل الأول**: سجلّ الآثار ``FIELD_EFFECTS`` يحمل ``REQPROM``، وكوُد
النوع في الكتالوج ``REQPROMO``. والطلب يُخزَّن **بكود الكتالوج المُحَل**
(``request_type_code=rt.code``) لا بالكنية المرسَلة — فأثٌر مسجٌَّل تحت
كنية **لا يُستدعى قط**.

وكانت ثلاثة بالحرف نفسه:

=============  =============  ==========================
مسجٌَّل تحت      والكود الحقيقي  النوع
=============  =============  ==========================
``REQPROM``    ``REQPROMO``   ترقية أو تعديل راتب
``REQCIVIL``   ``REQCID``     تحديث البطاقة المدنية
``REQTRANS``   ``REQTRF``     نقل داخلي
=============  =============  ==========================

فبقيت ترقيٌة تُعتمد ولا يتغيّر راتب، وبطاقٌة تُجدَّد ولا يتغيّر رقمها،
ونقٌل يُعتمد ولا ينتقل أحد — وكلّها تُغلَق «مكتملة». ولم يمسكه حارٌس لأن
لا شيء كان يقابل مفاتيح السجلّ بالكتالوج.

**والعطل الثاني أدقّ**: الأثر كان يُطبَّق فوًرا، ويُقرأ ``effective_date``
**لكتابة ملاحظة فقط** — «تاريخ السريان المعلن: …». أي أن النظام يعرف أن
التاريخ في المستقبل، ويطبّق، **ثم يسجّل القاعدة التي خالفها**.

فترقيٌة تُعتمد في يناير بنفاٍذ في أبريل ترفع الراتب في يناير: ثلاثُة أشهر
فرًقا في الأجر، وفي كل ما يُحسب منه — نهاية الخدمة وأجر الإضافي وخصم
الغياب.

**وبإذٍن صريح من المالك** (القاعدة 20).
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models, request_effects
from app.clock import today as kuwait_today
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
SUP = ("100000000005", "sup12345")
MGR = ("100000000001", "manager123")


def _emp_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()


def _salary() -> float:
    db = SessionLocal()
    try:
        return float(db.get(models.Employee, _emp_id()).basic_salary or 0)
    finally:
        db.close()


def _purge(rid: int, restore: float | None = None) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.AuditLog).where(
            models.AuditLog.entity_type == "request",
            models.AuditLog.entity_id == rid))
        for tbl in (models.RequestDocument, models.RequestApproval):
            db.execute(sa_delete(tbl).where(tbl.request_id == rid))
        db.execute(sa_delete(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid))
        db.execute(sa_delete(models.Request).where(models.Request.id == rid))
        if restore is not None:
            db.get(models.Employee, _emp_id()).basic_salary = restore
        db.commit()
    finally:
        db.close()


def _promote(client, new_salary: float, effective: str) -> int:
    r = client.post("/api/requests", headers=auth_headers(login(client, *EMP)),
                    json={"request_type_code": "REQPROMO",
                          "payload_json": {"new_title": "أخصائي أول",
                                           "new_salary": new_salary,
                                           "effective_date": effective,
                                           "reason": "قياس تاريخ النفاذ"}})
    assert r.status_code in (200, 201), r.text[:300]
    rid = r.json()["id"]
    for who in (SUP, MGR):
        d = client.post(f"/api/requests/{rid}/decide",
                        headers=auth_headers(login(client, *who)),
                        json={"decision": "approved"})
        assert d.status_code == 200, (who[0], d.text[:200])
    return rid


# ---------------------------------------------------------------------------
# المفتاح يطابق نوًعا
# ---------------------------------------------------------------------------

def test_every_declared_effect_names_a_real_request_type():
    """**الحارس الذي كان غائًبا**: مفتاٌح لا يطابق نوًعا لا يعمل أبًدا.

    ولم يكن شيٌء يقابل مفاتيح ``FIELD_EFFECTS`` بالكتالوج، فعاش ثلاثة
    منها سنًة بلا أن يُستدعى واحد.
    """
    from app import workflow

    types = {rt["code"] for rt in workflow.DEFAULT_REQUEST_TYPES}
    ghosts = [c for c in request_effects.FIELD_EFFECTS if c not in types]
    assert not ghosts, f"أثٌر مسجٌَّل لنوٍع لا وجود له: {ghosts}"


def test_a_promotion_effective_today_changes_the_salary(client):
    """وترقيٌة نافذٌة اليوم تغيّر الراتب فعًلا — لا تُغلَق «مكتملة» وحدها."""
    was = _salary()
    rid = _promote(client, was + 50, kuwait_today().isoformat())
    try:
        assert _salary() == pytest.approx(was + 50), (was, _salary())
        db = SessionLocal()
        try:
            emp = db.get(models.Employee, _emp_id())
            assert emp.job_title == "أخصائي أول", emp.job_title
        finally:
            db.close()
    finally:
        _purge(rid, restore=was)


# ---------------------------------------------------------------------------
# ولا يقع أثٌر قبل تاريخ نفاذه
# ---------------------------------------------------------------------------

def test_a_future_promotion_does_not_raise_the_salary_yet(client):
    """**جوهر البند**: ترقيٌة بنفاٍذ مستقبلي لا ترفع الراتب اليوم.

    وكان النظام يعرف أن التاريخ في المستقبل، ويطبّق، ثم يسجّل ملاحظًة
    بالتاريخ الذي خالفه.
    """
    was = _salary()
    later = (kuwait_today() + timedelta(days=90)).isoformat()
    rid = _promote(client, was + 100, later)
    try:
        assert _salary() == pytest.approx(was), \
            f"رُفع الراتب قبل نفاذه: {was} ← {_salary()}"
        db = SessionLocal()
        try:
            req = db.get(models.Request, rid)
            # **والتأجيل نجاٌح لا فشل**: الطلب يكتمل والأثر ينتظر يومه.
            assert req.status == "completed", req.status
        finally:
            db.close()
    finally:
        _purge(rid, restore=was)


def test_the_deferred_effect_is_not_counted_as_applied(client):
    """ولا يُحتسَب المؤجَّل مطبًَّقا — وإلا ضاع إلى الأبد."""
    was = _salary()
    later = (kuwait_today() + timedelta(days=30)).isoformat()
    rid = _promote(client, was + 10, later)
    try:
        db = SessionLocal()
        try:
            req = db.get(models.Request, rid)
            assert not request_effects.already_applied(db, req)
        finally:
            db.close()
    finally:
        _purge(rid, restore=was)


def test_when_the_day_comes_the_daily_sweep_applies_it(client):
    """**وتأجيٌل بلا يوٍم يحلّ فيه تسويٌف لا تأجيل.**

    فالمسح اليومي هو ما يجعل «مؤجَّل» وعًدا يُوفى.
    """
    was = _salary()
    later = (kuwait_today() + timedelta(days=5)).isoformat()
    rid = _promote(client, was + 75, later)
    try:
        db = SessionLocal()
        try:
            assert rid not in [r.id for r in
                               request_effects.due_deferred_effects(db)], \
                "عُدّ مستحًقا قبل يومه"
        finally:
            db.close()

        # يحلّ اليوم: يُقدَّم تاريخ النفاذ بدل انتظار خمسة أيام.
        db = SessionLocal()
        try:
            req = db.get(models.Request, rid)
            req.payload_json = {**(req.payload_json or {}),
                                "effective_date": kuwait_today().isoformat()}
            db.commit()
        finally:
            db.close()

        db = SessionLocal()
        try:
            out = request_effects.apply_due_effects(db)
        finally:
            db.close()
        assert out["applied"] >= 1, out
        assert _salary() == pytest.approx(was + 75), (was, _salary())
    finally:
        _purge(rid, restore=was)


def test_the_sweep_never_applies_the_same_change_twice(client):
    """ومسٌح يومّي يعيد التطبيق كل يوم يضاعف الراتب — فيُحرَس بالبصمة."""
    was = _salary()
    rid = _promote(client, was + 20, kuwait_today().isoformat())
    try:
        db = SessionLocal()
        try:
            first = request_effects.apply_due_effects(db)
            second = request_effects.apply_due_effects(db)
        finally:
            db.close()
        assert _salary() == pytest.approx(was + 20), (was, _salary())
        assert second["applied"] == 0, second
        assert first["failed"] == 0, first
    finally:
        _purge(rid, restore=was)


def test_the_audit_records_the_salary_before_and_after(client):
    """**والتاريخ يُقرأ من التدقيق**: رفٌع بلا سجٍل لا يُفسَّر بعد سنة."""
    was = _salary()
    rid = _promote(client, was + 35, kuwait_today().isoformat())
    try:
        db = SessionLocal()
        try:
            # **وسطُر الأثر لا آخُر سطر**: للطلب أسطٌر أخرى («اكتمل»
            # مثًلا) وأحدثُها ليس أصدقَها. فيُنتقى بفعله باسمه.
            row = db.scalar(select(models.AuditLog).where(
                models.AuditLog.entity_type == "request",
                models.AuditLog.entity_id == rid,
                models.AuditLog.action == "request_effect_applied:REQPROMO",
            ).order_by(models.AuditLog.id.desc()))
        finally:
            db.close()
        assert row is not None, "تغيّر الراتب بلا سطر تدقيق"
        assert (row.before_json or {}).get("basic_salary") == pytest.approx(was)
        assert (row.after_json or {}).get("basic_salary") == pytest.approx(was + 35)
    finally:
        _purge(rid, restore=was)
