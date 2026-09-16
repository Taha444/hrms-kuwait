# -*- coding: utf-8 -*-
"""من انتهت خدمته لا يُختار معتمِدًا — وإن بقي حسابُه نشطًا.

**الذيلُ الذي تركه الإصلاحُ السابق**: الإنهاءُ صار يُعطّل الحساب، وبوّابةُ
الدخول ترفض من انتهت خدمته. لكنّ من أُنهيت خدمتُه **قبل** ذلك ما زال
``is_active`` — فلا يدخل، **ويُختار معتمِدًا مع ذلك**: ``users_by_role`` و
مسؤولُ الفرع والمديرُ المباشر والمفوَّضُ إليه كلُّها تفحص ``is_active`` وحده.
فتصله مهمةُ الطلب ولا يستطيع فتحها، ويقف الطلبُ صامتًا.

فصار شرطٌ واحد (``deps.employment_live_clause``) تقرؤه مصادرُ المعتمِدين
الأربعة. ومستخدمٌ بلا ملف موظف لا يُمَسّ.

**وهذه الحالةُ تُصنَع كما هي في الإنتاج**: ملفٌّ ``terminated`` وحسابٌ
``is_active`` — لا بالإنهاء (فهو يُعطّل الحسابَ الآن).
"""
from __future__ import annotations

from sqlalchemy import select

from app import delegation, deps, models, notifications as N
from app.database import SessionLocal

HR = "100000000002"


def _legacy_ended(db, civil_id: str):
    u = db.scalar(select(models.User).where(models.User.civil_id == civil_id))
    e = db.get(models.Employee, u.employee_id)
    e.status = "terminated"
    assert u.is_active, "الحالةُ القديمة تفترض حسابًا نشطًا"
    db.flush()
    return u


def test_a_legacy_ended_account_is_not_routed_role_tasks():
    db = SessionLocal()
    try:
        u = _legacy_ended(db, HR)
        ids = {x.id for x in N.users_by_role(db, u.company_id, ["hr"])}
        assert u.id not in ids, "يُختار معتمِدًا من لا يستطيع الدخول"
    finally:
        db.rollback()
        db.close()


def test_a_live_account_is_still_routed():
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == HR))
        ids = {x.id for x in N.users_by_role(db, u.company_id, ["hr"])}
        assert u.id in ids
    finally:
        db.close()


def test_an_account_without_an_employee_file_is_untouched():
    db = SessionLocal()
    try:
        admin = db.scalar(select(models.User).where(models.User.civil_id == "000000000000"))
        ids = {x.id for x in N.users_by_role(db, None, [admin.role])}
        assert admin.id in ids
    finally:
        db.close()


def test_a_legacy_ended_delegate_is_not_added():
    """**والمفوَّضُ إليه كذلك** — تفويضٌ قائمٌ لا يُحيي معتمِدًا غادر."""
    from datetime import datetime, timedelta, timezone

    db = SessionLocal()
    try:
        mgr = db.scalar(select(models.User).where(models.User.civil_id == "100000000001"))
        hr = _legacy_ended(db, HR)
        now = datetime.now(timezone.utc)
        db.add(models.ApprovalDelegation(
            company_id=mgr.company_id, delegator_user_id=mgr.id,
            delegate_user_id=hr.id, starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=1), is_active=True, scope="all"))
        db.flush()
        got = {u.id for u in delegation.expand_approvers_with_delegates(
            db, [mgr], mgr.company_id)}
        assert hr.id not in got, "أُضيف معتمِدًا مفوَّضٌ انتهت خدمته"
    finally:
        db.rollback()
        db.close()


def test_the_clause_is_read_by_every_approver_source():
    import inspect

    from app import workflow

    assert "employment_live_clause()" in inspect.getsource(N.users_by_role)
    assert "employment_live_clause()" in inspect.getsource(deps.branch_supervisor_users)
    assert "employment_live_clause()" in inspect.getsource(workflow._stage_approvers_by_role)
    assert "employment_ended(" in inspect.getsource(delegation.active_delegates_for)
