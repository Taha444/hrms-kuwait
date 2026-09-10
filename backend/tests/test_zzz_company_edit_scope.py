# -*- coding: utf-8 -*-
"""بياٌن يُقرأ ولا يُصحَّح — وتعديُله لا يتعدّى شركته.

**العطل المقيس**: ``PUT /companies/{id}`` كان محروًسا بـ
``require_super_admin`` وحده. وقاعدة المالك المعلَنة: «لا تمنح أي مستخدم
Super Admin». فالنتيجة أن **بيانات الشركة لا يعدّلها أحٌد في الإنتاج** —
لا المالك ولا مدير الشركة — ومنها رقم الملف الذي أُضيف مع حزمة البيانات
الرسمية. فتُحمَل البيانات ولا تُصحَّح، وأيّ خطٍأ فيها يبقى.

وظهر بمسح ``ui_permission_gaps``: ``can("manage_company")`` شرٌط في
الشاشة لا يحمله دور — قفٌل بلا مفتاح.

**قرار المالك (2026-09-11)**: ``manage_company`` للمالك ومدير الشركة.
والإنشاء والتعطيل يبقيان للإدارة العليا — بقرار المالك نفسه، فلا يوسّعهما
هذا التغيير.

**وحرُس النطاق هو نصف الإصلاح**: المعرّف في المسار لا في الاستعلام، فلا
يمرّ عليه ``scope_company_id`` الذي يُجبِر غير العابرين على شركتهم. وبلا
فحٍص صريح يصير مدير شركٍة قادًرا على تعديل شركٍة أخرى بتبديل رقٍم في
العنوان — سلطٌة أوسع مما طُلب، تُمنَح سهًوا مع الصلاحية.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import models, permissions
from app.database import SessionLocal
from tests.conftest import auth_headers, login

MGR = ("100000000001", "manager123")
HR = ("100000000002", "hr12345")


# ---------------------------------------------------------------------------
# المفتاح موجود
# ---------------------------------------------------------------------------

def test_the_permission_is_held_by_a_real_role():
    """قفٌل بلا مفتاح لا يُقفِل شيًئا — يُعطّله."""
    holders = [r for r, perms in permissions.ROLE_DEFAULT_PERMS.items()
               if "manage_company" in perms and r != "super_admin"]
    assert "company_owner" in holders, holders
    assert "company_manager" in holders, holders


def test_creating_and_suspending_stay_with_top_management():
    """**وقرار المالك محدود بما قاله**: التعديل وحده انتقل.

    الإنشاء والتعطيل يبقيان ``require_super_admin`` — وتوسيعهما مع
    التعديل لأنهما في الملف نفسه يكون منًحا لم يُطلَب.
    """
    import inspect

    from app.routers import companies as C

    for fn, name in ((C.create_company, "الإنشاء"), (C.set_status, "التعطيل")):
        src = inspect.getsource(fn)
        assert "require_super_admin" in src, f"{name} لم يبق للإدارة العليا"


# ---------------------------------------------------------------------------
# ويعدّل شركته
# ---------------------------------------------------------------------------

@pytest.fixture
def own_company(client):
    """رقُم ملّف شركة المدير — يُعاد إلى ما كان بعد القياس."""
    db = SessionLocal()
    try:
        user = db.scalar(select(models.User).where(models.User.civil_id == MGR[0]))
        cid = user.company_id
        was = db.get(models.Company, cid).file_number
    finally:
        db.close()
    yield cid
    db = SessionLocal()
    try:
        # **يُعاد إلى ما كان لا إلى الفراغ**: افتراُض أن الحقل كان خالًيا
        # يُلوّث ما بعده، وقد أوقعني ذلك في جولٍة سابقة.
        db.get(models.Company, cid).file_number = was
        db.commit()
    finally:
        db.close()


def test_the_manager_can_correct_his_own_company(client, own_company):
    """**والبيان يُصحَّح**: من يقرأ الخطأ يملك تصحيحه."""
    r = client.put(f"/api/companies/{own_company}",
                   headers=auth_headers(login(client, *MGR)),
                   json={"file_number": "QA-EDIT-001"})
    assert r.status_code == 200, r.text[:250]
    assert r.json()["file_number"] == "QA-EDIT-001"


def test_a_partial_edit_still_does_not_wipe_the_rest(client, own_company):
    """وما لا يُرسَل لا يُمسّ — والأرقام تُحسب بها مستحقات نهاية الخدمة."""
    db = SessionLocal()
    try:
        c = db.get(models.Company, own_company)
        before = (c.eos_day_divisor, c.eos_max_months, c.name)
    finally:
        db.close()

    client.put(f"/api/companies/{own_company}",
               headers=auth_headers(login(client, *MGR)),
               json={"file_number": "QA-EDIT-002"})

    db = SessionLocal()
    try:
        c = db.get(models.Company, own_company)
        after = (c.eos_day_divisor, c.eos_max_months, c.name)
    finally:
        db.close()
    assert after == before, f"{before} → {after}"


def test_the_manager_cannot_reach_another_company(client, own_company):
    """**ولا يتعدّى شركته** — والمعرّف في المسار يُبدَّل بيٍد واحدة."""
    db = SessionLocal()
    try:
        other = db.scalar(select(models.Company.id).where(
            models.Company.id != own_company))
    finally:
        db.close()
    if other is None:
        pytest.skip("شركٌة واحدة في البذرة — لا يُقاس التعدّي")

    r = client.put(f"/api/companies/{other}",
                   headers=auth_headers(login(client, *MGR)),
                   json={"file_number": "QA-INTRUSION"})
    assert r.status_code == 403, r.text[:250]

    db = SessionLocal()
    try:
        assert db.get(models.Company, other).file_number != "QA-INTRUSION"
    finally:
        db.close()


def test_a_role_without_the_permission_is_still_refused(client, own_company):
    """ومن لا يحملها يُردّ — التوسيع للدورين لا للجميع."""
    r = client.put(f"/api/companies/{own_company}",
                   headers=auth_headers(login(client, *HR)),
                   json={"file_number": "QA-NO-PERM"})
    assert r.status_code == 403, r.text[:250]
