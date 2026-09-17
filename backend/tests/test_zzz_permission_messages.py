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
