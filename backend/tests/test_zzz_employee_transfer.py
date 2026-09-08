# -*- coding: utf-8 -*-
"""نقل موظف بين الشركات: ينتقل السجل ويبقى ما يشير إليه في مكانه.

**نقطٌة بلا طريق، وبلا اختبار واحد.** ولمّا جئتُ أبني لها مدخًلا قِستُ
ما تفعله فإذا هي تنقل ``employees.company_id`` وحده وتُفرّغ الفرع، وتترك
ثلاثة معلَّقة:

1. **حساب المستخدم يبقى في الشركة القديمة.** والموظف وحسابه رابطٌ واحد
   لا يفترق — وهو شرط المالك نفسه (``Atomic``). فبعد النقل: سجٌل في
   شركة، ودخوٌل إلى أخرى، ونطاُق بيانات لا يطابق ملفه.
2. **القسم والوردية يبقيان.** وكلاهما مملوٌك لشركة المصدر: فموظف في
   شركة يعمل بوردية شركة أخرى، وحضوره يُقاس عليها.
3. **يُنقَل وله خروج مفتوح.** والتسوية محسوبة على مدة خدمته في الشركة
   الأولى، فتُنفَّذ من الثانية بأرقام لا تخصّها.

**وبناء مدخل فوق هذه الحال يوسّع الضرر لا يكشفه** — فقُيست أوًلا، ثم
أُغلقت، ثم بُني المدخل.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

SUPER = ("000000000000", "admin123")


@pytest.fixture
def moving():
    """موظف بحسابه وقسمه ووردِيته في شركة، وشركٌة أخرى ينتقل إليها."""
    db = SessionLocal()
    try:
        src = db.scalars(select(models.Company).limit(1)).first()
        dst = db.scalars(select(models.Company).where(
            models.Company.id != src.id).limit(1)).first()
        assert dst is not None, "لا شركة ثانية — لا يُقاس النقل"
        dept = db.scalar(select(models.Department).where(
            models.Department.company_id == src.id))
        shift = db.scalar(select(models.Shift).where(
            models.Shift.company_id == src.id))
        branch = db.scalar(select(models.Branch).where(
            models.Branch.company_id == src.id))

        emp = models.Employee(
            company_id=src.id, name="موظف قياس النقل", civil_id="266600110044",
            branch_id=branch.id if branch else None,
            department_id=dept.id if dept else None,
            shift_id=shift.id if shift else None,
            status="active", basic_salary=400, nationality="مصري")
        db.add(emp)
        db.flush()
        acct = models.User(
            civil_id="266600110044", full_name="موظف قياس النقل",
            role="employee", company_id=src.id, employee_id=emp.id,
            is_active=True, must_change_password=False,
            password_hash="x" * 40)
        db.add(acct)
        db.commit()
        made = {"eid": emp.id, "uid": acct.id, "src": src.id, "dst": dst.id}
    finally:
        db.close()

    yield made

    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Transfer).where(
            models.Transfer.employee_id == made["eid"]))
        db.execute(sa_delete(models.User).where(models.User.id == made["uid"]))
        db.execute(sa_delete(models.Employee).where(
            models.Employee.id == made["eid"]))
        db.commit()
    finally:
        db.close()


def _transfer(client, moving, **extra):
    hdr = auth_headers(login(client, *SUPER))
    q = f"to_company_id={moving['dst']}"
    for k, v in extra.items():
        q += f"&{k}={v}"
    return client.post(f"/api/employees/{moving['eid']}/transfer?{q}", headers=hdr)


def test_the_account_moves_with_the_person(client, moving):
    """**الموظف وحسابه رابٌط واحد لا يفترق** — وهو شرط مكتوب لا استحسان.

    وبقاء الحساب في الشركة القديمة يعني دخوًلا إلى شركة وملًفا في أخرى.
    """
    assert _transfer(client, moving).status_code == 200

    db = SessionLocal()
    try:
        emp = db.get(models.Employee, moving["eid"])
        acct = db.get(models.User, moving["uid"])
    finally:
        db.close()
    assert emp.company_id == moving["dst"]
    assert acct.company_id == moving["dst"], (
        "السجل انتقل والحساب بقي — رابٌط واحد افترق"
    )


def test_nothing_of_the_old_company_stays_attached(client, moving):
    """**والقسم والوردية مملوكان للشركة القديمة** — لا يُحملان معه.

    ووردية شركة أخرى تُقاس عليها بصمات هذا الموظف وتقارير حضوره.
    """
    assert _transfer(client, moving).status_code == 200
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, moving["eid"])
        stale = {"branch_id": emp.branch_id, "department_id": emp.department_id,
                 "shift_id": emp.shift_id}
    finally:
        db.close()
    assert all(v is None for v in stale.values()), f"بقي معلًَّقا: {stale}"


def test_the_move_is_written_in_its_own_history(client, moving):
    """ويبقى السجل التاريخي كما هو: من أين وإلى أين ومن نقله."""
    assert _transfer(client, moving, note="إعادة توزيع").status_code == 200
    db = SessionLocal()
    try:
        row = db.scalar(select(models.Transfer).where(
            models.Transfer.employee_id == moving["eid"]))
    finally:
        db.close()
    assert row and row.from_company_id == moving["src"]
    assert row.to_company_id == moving["dst"] and row.transferred_by


def test_an_employee_on_his_way_out_is_not_moved(client, moving):
    """**ولا نقٌل فوق خروج مفتوح**: التسوية محسوبة على الشركة الأولى.

    فتُنفَّذ من الثانية بأرقام لا تخصّها — والمنع يسمّي الخروج المفتوح.
    """
    db = SessionLocal()
    try:
        emp = db.get(models.Employee, moving["eid"])
        emp.pending_termination_json = '{"total_settlement": 1}'
        db.commit()
    finally:
        db.close()

    r = _transfer(client, moving)
    assert r.status_code == 409, r.text
    body = r.json()["detail"]
    text = body if isinstance(body, str) else str(body)
    assert "خروج" in text, text

    db = SessionLocal()
    try:
        emp = db.get(models.Employee, moving["eid"])
        assert emp.company_id == moving["src"], "نُقل رغم الرفض"
        emp.pending_termination_json = None
        db.commit()
    finally:
        db.close()


def test_the_screen_can_actually_move_him():
    """وبعد أن أُغلقت الثغرات، صار للنقل مدخل — لا قبلها."""
    from pathlib import Path

    page = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
            / "EmployeeProfile.tsx").read_text(encoding="utf-8")
    assert "/transfer" in page, "لا طريق إلى النقل"
    assert "emp_transfer" in page, "لا نصّ يشرح ما يفعله"
