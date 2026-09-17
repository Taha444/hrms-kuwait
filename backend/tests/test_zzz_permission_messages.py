# -*- coding: utf-8 -*-
"""زرٌّ لا يملكه المستخدم لا يُعرض — والرفضُ يُسمّي الصلاحية لا رمزها.

**القياس** (لقطة المالك على حساب المحاسب): «موظفون بلا سياسة حضور» تُعرض
للمحاسب بأزرار التثبيت، فيضغط فيُردّ بـ«ليس لديك صلاحية: manage_attendance».
العرضُ صحيح (``view_attendance`` — هؤلاء يوقفون إقفال المسيّر)، والأزرارُ
بلا بوّابة، والرسالةُ تكشف الرمزَ الداخليّ للمستخدم.
"""
from __future__ import annotations

import pathlib
import re

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.permissions import PERMISSIONS
from tests.conftest import auth_headers, login

ACC = ("100000000007", "account123")
REVIEW = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
          / "AttendanceReview.tsx")


def test_a_refusal_names_the_permission_not_its_code(client):
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(models.Employee.company_id == 1))
    finally:
        db.close()
    r = client.post(f"/api/employees/{eid}/attendance-policy",
                    headers=auth_headers(login(client, *ACC)), params={"mode": "qr"})
    assert r.status_code == 403, r.text[:200]
    detail = r.json()["detail"]
    assert "manage_attendance" not in detail, detail
    assert PERMISSIONS["manage_attendance"] in detail, detail


def test_no_refusal_template_prints_a_raw_code():
    src = (pathlib.Path(__file__).resolve().parents[1] / "app" / "deps.py").read_text(encoding="utf-8")
    assert 'detail=f"ليس لديك صلاحية: {perm}"' not in src
    assert "{page}.{action}" not in src


def test_the_policy_buttons_are_gated_by_the_permission_the_server_checks():
    src = REVIEW.read_text(encoding="utf-8")
    block = src[src.index("gaps.map("):src.index("ATT-07 / DLV-01")]
    assert 'can("manage_attendance")' in block
    first_button = block.index("setPolicy(")
    assert block.index('can("manage_attendance")') < first_button


# ---------------------------------------------------------------------------
# معالجُ تسجيل الموظف — نفسُ النمط، ومعه بابُ كلمة المرور
# ---------------------------------------------------------------------------

WIZARD = REVIEW.parent / "EmployeeOnboarding.tsx"


def test_an_account_cannot_be_created_with_a_chosen_password(client):
    """قاعدة المالك: «أنشئ كلمة مرور مؤقتة عشوائية ومختلفة لكل شخص».

    كان ``POST /users`` يقبل ``password`` — والمعالجُ يولّدها في المتصفّح
    (``Math.random``) ويرسلها. فصار الخادمُ يرفضها ويولّد الكلمة بنفسه.
    """
    admin = auth_headers(login(client, "000000000000", "admin123"))
    r = client.post("/api/users", headers=admin, json={
        "civil_id": "474700000001", "full_name": "قياس", "role": "hr",
        "company_id": 1, "password": "SamePass#2026x"})
    assert r.status_code == 400, r.text[:200]
    db = SessionLocal()
    try:
        assert not db.scalar(select(models.User).where(
            models.User.civil_id == "474700000001"))
    finally:
        db.close()

    ok = client.post("/api/users", headers=admin, json={
        "civil_id": "474700000002", "full_name": "قياس", "role": "hr", "company_id": 1})
    assert ok.status_code == 201, ok.text[:200]
    assert ok.json().get("temporary_password")
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == "474700000002"))
        assert u.must_change_password
        db.delete(u)
        db.commit()
    finally:
        db.close()


def test_the_wizard_takes_the_password_from_the_server():
    src = WIZARD.read_text(encoding="utf-8")
    assert "Math.random" not in src and "genPassword" not in src
    assert "temporary_password" in src
    assert "password: pw" not in src


def test_the_wizard_offers_only_what_the_user_may_do():
    """موظفُ الموارد البشرية لا يملك manage_users ولا manage_permits افتراضًا —
    وكان خيارُ «أنشئ حسابًا» مُفعَّلًا له فيفشل دائمًا بعد حفظ الموظف."""
    from app.permissions import has_permission
    assert not has_permission("hr", set(), "manage_users")
    assert not has_permission("hr", set(), "manage_permits")
    src = WIZARD.read_text(encoding="utf-8")
    assert 'can("manage_users")' in src and 'can("manage_permits")' in src
    assert "createUserAccount && canCreateAccount" in src
    assert "canAddPermits ?" in src or "!canAddPermits ?" in src
