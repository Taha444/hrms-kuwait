# -*- coding: utf-8 -*-
"""قراران (2026-09-18): فكُّ قفل 2FA لصاحب الشركة، والنقلُ بطلبه لا بالتعديل.

**القفلُ بلا مخرج**: من يفقد هاتفه ورموزَ الاسترداد معًا لا يدخل، وكلُّ
نقاط 2FA تستلزم جلسًة تستلزم الدخول. والمخرجُ كان محصوًرا في
``super_admin`` — وقاعدُة المالك «لا تمنح أي مستخدم Super Admin»، فالمخرجُ
بلا فاعل، ولا يبقى إلا تعديٌل يدويٌّ في قاعدة البيانات.

**والبابُ الجانبي**: ``PUT /employees/{id}`` كان يكتب ``branch_id`` و
``license_id`` بصلاحية التعديل وحدها — وهما ما يكتبه طلبُ النقل بعد
اعتماد. فمن يعدّل اسًما ينقل موظًفا بين الفروع والتراخيص بلا عينٍ ثانية.
و«الفعليّ» يبقى تحريريًّا: رصدُ واقعٍ لا قرارُ نقل.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

OWNER = ("111111111111", "owner123")
HR = ("100000000002", "hr12345")
MGR = ("100000000001", "manager123")


def _a_user_with_2fa():
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == HR[0]))
        snap = (u.totp_secret, u.totp_confirmed, u.totp_recovery_hashes)
        u.totp_secret, u.totp_confirmed = "ZZZZQAZZ", True
        db.commit()
        return u.id, snap
    finally:
        db.close()


def _restore(uid, snap):
    db = SessionLocal()
    try:
        u = db.get(models.User, uid)
        u.totp_secret, u.totp_confirmed, u.totp_recovery_hashes = snap
        db.commit()
    finally:
        db.close()


def test_the_owner_can_unlock_a_user_who_lost_the_device(client):
    uid, snap = _a_user_with_2fa()
    try:
        r = client.post(f"/api/users/{uid}/2fa/reset",
                        headers=auth_headers(login(client, *OWNER)),
                        params={"reason": "فقد الهاتف ورموز الاسترداد"})
        assert r.status_code == 200, r.text[:250]
        db = SessionLocal()
        try:
            u = db.get(models.User, uid)
            assert u.totp_secret is None and u.totp_confirmed is False
            # والإجراءُ يُقرأ في التدقيق بسببه بعد شهور.
            row = db.scalar(select(models.AuditLog).where(
                models.AuditLog.action == "totp_admin_reset",
                models.AuditLog.entity_id == uid))
            assert row is not None and "فقد الهاتف" in (row.detail or "")
        finally:
            db.close()
    finally:
        _restore(uid, snap)


def test_a_manager_still_cannot_unlock(client):
    uid, snap = _a_user_with_2fa()
    try:
        r = client.post(f"/api/users/{uid}/2fa/reset",
                        headers=auth_headers(login(client, *MGR)),
                        params={"reason": "محاولة"})
        assert r.status_code == 403, r.status_code
    finally:
        _restore(uid, snap)


def test_the_reason_is_required(client):
    uid, snap = _a_user_with_2fa()
    try:
        r = client.post(f"/api/users/{uid}/2fa/reset",
                        headers=auth_headers(login(client, *OWNER)),
                        params={"reason": "   "})
        assert r.status_code == 400
    finally:
        _restore(uid, snap)


def test_the_screen_offers_the_unlock_to_the_owner():
    import pathlib
    page = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
            / "Users.tsx").read_text(encoding="utf-8")
    assert "2fa/reset" in page, "المخرجُ مبنيٌّ بلا باب"
    assert "company_owner" in page


# ---------------------------------------------------------------------------
# النقل بطلبه
# ---------------------------------------------------------------------------

def _employee():
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1, models.Employee.branch_id.isnot(None)))
        other = db.scalar(select(models.Branch).where(
            models.Branch.company_id == 1, models.Branch.id != emp.branch_id))
        return emp.id, emp.civil_id, emp.name, emp.branch_id, (other.id if other else None)
    finally:
        db.close()


def test_a_branch_change_through_the_plain_edit_is_refused(client):
    eid, civil_id, name, branch_id, other = _employee()
    assert other, "لا فرعَ ثانٍ — لا يُقاس النقل"
    r = client.put(f"/api/employees/{eid}", headers=auth_headers(login(client, *HR)),
                   json={"civil_id": civil_id, "name": name, "branch_id": other})
    assert r.status_code == 409, (r.status_code, r.text[:200])
    assert "طلب نقل" in r.text
    db = SessionLocal()
    try:
        assert db.get(models.Employee, eid).branch_id == branch_id, "نُقل الموظف رغم الرفض"
    finally:
        db.close()


def test_the_same_branch_is_not_treated_as_a_move(client):
    eid, civil_id, name, branch_id, _ = _employee()
    r = client.put(f"/api/employees/{eid}", headers=auth_headers(login(client, *HR)),
                   json={"civil_id": civil_id, "name": name, "branch_id": branch_id})
    assert r.status_code == 200, r.text[:200]


def test_the_actual_workplace_stays_editable(client):
    """و«الفرع الفعلي» رصٌد لا نقل — وعليه يقوم تنبيه العمل على غير الترخيص."""
    eid, civil_id, name, branch_id, other = _employee()
    db = SessionLocal()
    try:
        before = db.get(models.Employee, eid).actual_branch_id
    finally:
        db.close()
    try:
        r = client.put(f"/api/employees/{eid}", headers=auth_headers(login(client, *HR)),
                       json={"civil_id": civil_id, "name": name, "actual_branch_id": other})
        assert r.status_code == 200, r.text[:200]
    finally:
        db = SessionLocal()
        try:
            db.get(models.Employee, eid).actual_branch_id = before
            db.commit()
        finally:
            db.close()


