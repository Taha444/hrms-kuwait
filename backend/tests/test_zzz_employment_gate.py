# -*- coding: utf-8 -*-
"""P0 — بوابة حالة التوظيف على الأعمال الذاتية الجديدة.

**العطل**: كان كل باب يحرس نفسه. فأُغلق باب إنشاء الطلبات أمام الموظف
المؤرشَف، وبقي باب **استبدال التوقيع** مفتوًحا — فيستطيع من انتهت خدمته
أن يبدأ معاملة موارد بشرية جديدة، ويُستبدَل توقيعه المستعمَل في مستندات
رسمية سابقة.

**والقاعدة صارت في موضع واحد** (``assert_employment_active``): قاعدة
موزَّعة على أبواب تُنسى في الباب التالي — وهذا بالضبط ما وقع.

ولا تمسّ القراءة: الملف والمستندات تبقى متاحة بحسب السياسة. الممنوع أن
**يبدأ** معاملة جديدة.
"""
from __future__ import annotations

import io as _io
from pathlib import Path

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.deps import INACTIVE_EMPLOYMENT
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")

_PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)


def _set_status(value: str) -> int:
    db = SessionLocal()
    try:
        e = db.scalar(select(models.Employee).where(
            models.Employee.civil_id == EMP[0]))
        e.status = value
        db.commit()
        return e.id
    finally:
        db.close()


def _upload(client, hdr):
    return client.post("/api/me/signature", headers=hdr,
                       files={"file": ("sig.png", _io.BytesIO(_PNG), "image/png")})


def test_an_active_employee_may_still_replace_their_signature(client):
    """أوًلا: العلاج لا يمنع من يحقّ له.

    وحارس يمنع الجميع يبدو ناجًحا وهو يكسر الميزة.
    """
    _set_status("active")
    hdr = auth_headers(login(client, *EMP))
    r = _upload(client, hdr)
    assert r.status_code != 409, r.text[:200]


def test_a_terminated_employee_cannot_start_a_signature_replacement(client):
    """**جوهر العطل**: من انتهت خدمته كان يبدأ معاملة جديدة."""
    hdr = auth_headers(login(client, *EMP))
    _set_status("terminated")
    r = _upload(client, hdr)
    assert r.status_code == 409, f"{r.status_code}: {r.text[:200]}"
    assert "منتهية" in r.text
    _set_status("active")


def test_an_archived_employee_cannot_either(client):
    """والمؤرشَف مثله — الحالتان في قائمة واحدة لا في شرطين."""
    hdr = auth_headers(login(client, *EMP))
    _set_status("archived")
    r = _upload(client, hdr)
    assert r.status_code == 409, f"{r.status_code}: {r.text[:200]}"
    _set_status("active")


def test_reading_is_not_blocked(client):
    """ولا تُقفَل القراءة: الملف والتوقيع القديم يبقيان للاطلاع."""
    hdr = auth_headers(login(client, *EMP))
    _set_status("terminated")
    r = client.get("/api/me/signature", headers=hdr)
    assert r.status_code == 200, f"أُقفلت القراءة: {r.status_code}"
    _set_status("active")


def test_the_rule_lives_in_one_place():
    """**وقاعدة موزَّعة على أبواب تُنسى في الباب التالي** — وهو ما وقع."""
    from app import deps

    assert set(INACTIVE_EMPLOYMENT) == {"archived", "terminated"}, INACTIVE_EMPLOYMENT
    sig = (Path(__file__).resolve().parents[1] / "app" / "routers"
           / "signatures.py").read_text(encoding="utf-8")
    assert "assert_employment_active" in sig, (
        "باب التوقيع لا يقرأ القاعدة المشتركة"
    )
    assert hasattr(deps, "assert_employment_active")


def test_a_user_without_an_employee_file_is_untouched(client):
    """ومستخدم إداري بلا ملف موظف لا حالة توظيف له تُفحَص."""
    hdr = auth_headers(login(client, "100000000002", "hr12345"))
    r = _upload(client, hdr)
    assert r.status_code != 409, r.text[:200]
