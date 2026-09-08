# -*- coding: utf-8 -*-
"""طابوران بُنيا ليُقرآ، وبقيا بلا من يقرؤهما.

**١ · تغييرات الحقول الحرجة** — النقطة بُنيت بنصّها: «القائمة الوحيدة
كانت داخل ملف الموظف، فمن يملك القرار لا يجد ما ينتظره إلا بفتح الملفات
واحًدا واحًدا». ثم بقيت بلا طريق من الواجهة — **فالبلاغ يقول إن هناك
عمًلا ولا يقول أين هو**، والحال هي الحال.

**٢ · حسابات بلا سجل موظف** — كل دور داخلي يجب أن يُربَط بموظف (شرط
المالك: الحساب والموظف رابٌط واحد). والربط الآلي يطابق بالرقم المدني
**ويُخلّف من لا مطابق له**، ويقول في تقريره «يحتاج إنشاء Employee
record» — ثم لا شيء في الشاشة يربط. **وإنشاء موظف وهمي ممنوع**، فالمخرج
الوحيد الربط بسجل قائم، ولم يكن له باب.

وكانت القائمة لا تُرى إلا بعد ضغط زرّ الربط الآلي: من لم يضغطه لا يعرف
أن في شركته حساًبا مكسوًرا أصًلا.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login, purge

HR = ("100000000002", "hr12345")
MANAGER = ("100000000001", "manager123")
FRONT = Path(__file__).resolve().parents[2] / "frontend" / "src"


# ---------------------------------------------------------------------------
# طابور تغييرات الحقول الحرجة
# ---------------------------------------------------------------------------

@pytest.fixture
def proposal(client):
    """اقتراٌح معلَّق من الموارد البشرية على راتب موظف."""
    db = SessionLocal()
    try:
        emp = db.scalars(select(models.Employee).where(
            models.Employee.status == "active",
            models.Employee.basic_salary > 0).limit(1)).first()
        eid = emp.id
    finally:
        db.close()

    hdr = auth_headers(login(client, *HR))
    eff = (date.today() + timedelta(days=30)).isoformat()
    r = client.post(f"/api/employees/{eid}/salary-change-request", headers=hdr,
                    params={"field_name": "basic_salary", "new_value": "777",
                            "effective_date": eff, "reason": "قياس الطابور"})
    assert r.status_code in (200, 201), r.text
    yield eid

    db = SessionLocal()
    try:
        db.execute(sa_delete(models.SalaryChangeRequest).where(
            models.SalaryChangeRequest.employee_id == eid))
        db.commit()
    finally:
        db.close()


def test_the_approver_sees_what_waits_gathered(client, proposal):
    """**جوهر الطابور**: ما ينتظر قراري مجموًعا، لا ملًفا ملًفا."""
    hdr = auth_headers(login(client, *MANAGER))
    r = client.get("/api/employees/salary-change-requests/pending", headers=hdr)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert any(x["employee_id"] == proposal for x in rows), "الاقتراح ليس في الطابور"
    row = next(x for x in rows if x["employee_id"] == proposal)
    # واسٌم لا رقم: من يقرأ الطابور يقرّر، ولا يقرّر على أرقام.
    assert row["employee_name"] and row["proposed_by_name"], row


def test_the_queue_has_a_screen(client, proposal):
    """وطابوٌر لا يُقرأ من شاشة طابوٌر لم يُبنَ."""
    page = (FRONT / "pages" / "Employees.tsx").read_text(encoding="utf-8")
    assert "salary-change-requests/pending" in page, "لا طريق إلى الطابور"
    assert "salary-change-requests/${reqId}/decide" in page or "/decide" in page, (
        "يُعرَض ولا يُقرَّر فيه"
    )


def test_the_field_name_is_written_once(client):
    """**واسم الحقل في مصدر واحد**: كانت خريطة عربية محلّية داخل ملف
    الموظف، فلمّا لزمت شاشًة ثانية كان الخيار نسخها أو نقلها."""
    labels = (FRONT / "labels.ts").read_text(encoding="utf-8")
    assert "export const fieldAr" in labels, "التسمية ليست في مصدرها"
    profile = (FRONT / "pages" / "EmployeeProfile.tsx").read_text(encoding="utf-8")
    assert "FIELD_LABEL" not in profile, "بقيت النسخة المحلّية — موضعان لتسمية واحدة"


# ---------------------------------------------------------------------------
# حسابات بلا سجل موظف
# ---------------------------------------------------------------------------

@pytest.fixture
def orphan():
    """حساٌب داخلي بلا سجل موظف — وهو ما يحظره شرط الربط الواحد."""
    db = SessionLocal()
    try:
        emp = db.scalars(select(models.Employee).where(
            models.Employee.company_id == 1,
            models.Employee.status == "active").limit(1)).first()
        u = models.User(
            civil_id="244400110022", full_name="حساب بلا موظف",
            role="accountant", company_id=1, is_active=True,
            must_change_password=False, password_hash="x" * 40)
        db.add(u)
        db.commit()
        made = {"uid": u.id, "eid": emp.id}
    finally:
        db.close()
    yield made
    db = SessionLocal()
    try:
        purge(db, "users", [made["uid"]])
        db.commit()
    finally:
        db.close()


def test_the_broken_accounts_are_listed_without_pressing_anything(client, orphan):
    """**والقائمة تُرى دائًما**: من لم يضغط «ربط تلقائي» لا يعرف بالكسر."""
    hdr = auth_headers(login(client, *MANAGER))
    r = client.get("/api/users/orphaned", headers=hdr)
    assert r.status_code == 200, r.text
    assert any(x["id"] == orphan["uid"] for x in r.json()), "الحساب المكسور لا يُعرَض"

    page = (FRONT / "pages" / "Users.tsx").read_text(encoding="utf-8")
    assert "/users/orphaned" in page, "الشاشة لا تقرأ القائمة"
    assert "link-employee" in page, "تُعرَض ولا تُربَط"


def test_linking_by_hand_closes_it(client, orphan):
    """والمخرج **ربٌط بسجل قائم** — لا إنشاء موظف وهمي لأجل الربط."""
    hdr = auth_headers(login(client, *MANAGER))

    # الموظف المختار قد يكون مربوًطا بحساب آخر؛ نبحث عن سجل حرّ.
    db = SessionLocal()
    try:
        taken = {u.employee_id for u in db.scalars(select(models.User)).all()
                 if u.employee_id}
        free = db.scalars(select(models.Employee).where(
            models.Employee.company_id == 1)).all()
        free_id = next((e.id for e in free if e.id not in taken), None)
    finally:
        db.close()
    if free_id is None:
        pytest.skip("كل الموظفين مربوطون — لا سجل حرّ للقياس")

    r = client.post(f"/api/users/{orphan['uid']}/link-employee",
                    headers=hdr, params={"employee_id": free_id})
    assert r.status_code == 200, r.text

    left = client.get("/api/users/orphaned", headers=hdr).json()
    assert not any(x["id"] == orphan["uid"] for x in left), "بقي في قائمة المكسور"


def test_one_employee_is_not_linked_to_two_accounts(client, orphan):
    """**ورابٌط واحد يعني واحًدا**: سجٌل مربوط بحسابين يُفسد كل نسبة."""
    hdr = auth_headers(login(client, *MANAGER))
    r = client.post(f"/api/users/{orphan['uid']}/link-employee",
                    headers=hdr, params={"employee_id": orphan["eid"]})
    # سجل البذرة مربوط بحسابه — فالربط الثاني يُردّ ويسمّي صاحبه.
    assert r.status_code == 409, r.text
    assert "حساب آخر" in r.json()["detail"], r.json()
