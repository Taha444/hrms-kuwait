# -*- coding: utf-8 -*-
"""P6-28 — لا خروج بلا حدث على ملف الموظف نفسه.

**ما ظهر بالقياس:**

سُقتُ حالة نهاية خدمة كاملة إلى الصرف. ملف الموظف بعدها ``terminated``
وتاريخ خروجه مكتوب وتسويته محفوظة — و**صفر حدث تدقيق على كيان
``employee``**. ستة أحداث، كلها على ``eos_case``.

والفارق ليس شكلًيا: الملف يصير عندئذٍ مجمًَّدا
(``BLOCKED_EMPLOYEE_STATUSES``) فلا يُفتح له طلب. فمن يفتح ملف الموظف
ويسأل «متى أُغلق ومن أغلقه وبأي سند؟» لا يجد سطًرا واحًدا — والأثر
موجود، لكن تحت رقم حالة يجب أن يعرفه سلًفا ليصل إليه. ومن لا يعرفه
يقرأ ملًفا أُغلق بلا سبب ظاهر.

**والطريقان الآخران كانا سليمين** (``set_status`` و``terminate/execute``
يدقّقان على الموظف)، فالعطل في هذا الطريق وحده — ولذلك الحارس يقيس
**كل** موضع يكتب حالة خروج، لا الموضع الذي أصلحته.
"""
from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import delete as sa_delete, select

from app import exit_guard, models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
MGR = ("100000000001", "manager123")
ACC = ("100000000007", "account123")
OWNER = ("111111111111", "owner123")   # الرقابة: يملك view_audit


def _drive_to_settled(client, emp_id: int, emp_login: tuple[str, str]):
    """يسوق حالة نهاية خدمة كاملة حتى الصرف، ويعيد رقم الحالة."""
    # P6-27 — الشرط المسبق يُثبَّت لا يُفترَض: «لا خروج آخر مفتوح».
    #
    # هذا الاختبار يقيس **أثر الصرف على سجلّ الموظف**، لا قاعدة الخروج
    # الواحد. واختبار آخر يترك طلب خروج مفتوًحا على موظف البذرة نفسه —
    # فكان يسقط هنا بسبب ليس ما يقيسه.
    db = SessionLocal()
    try:
        for ex in exit_guard.open_exits(db, emp_id):
            if ex["kind"] == "request":
                db.execute(sa_delete(models.Task).where(
                    models.Task.related_entity_type == "request",
                    models.Task.related_entity_id == ex["id"]))
                db.execute(sa_delete(models.Request).where(
                    models.Request.id == ex["id"]))
        db.commit()
    finally:
        db.close()

    hdr = auth_headers(login(client, *HR))
    r = client.post("/api/eos/cases", headers=hdr, params={
        "employee_id": emp_id, "termination_date": "2026-10-01",
        "reason": "resignation"})
    assert r.status_code == 201, f"تعذّر فتح الحالة: {r.text[:200]}"
    cid = r.json()["id"]

    steps = [
        ("calculate", {"used_leave_days": 0}, ACC),
        ("approve", {}, MGR),
        ("clearance", {"notes": "لا عهدة"}, HR),
        # الإقرار يوقّعه الموظف بنفسه — لا يقبله HR نيابًة عنه.
        ("acknowledge", {}, emp_login),
        ("settle", {"payment_reference": "TRX-9911"}, ACC),
    ]
    for path, params, who in steps:
        h = auth_headers(login(client, *who))
        rr = client.post(f"/api/eos/cases/{cid}/{path}", headers=h, params=params)
        assert rr.status_code == 200, f"{path}: {rr.status_code} {rr.text[:200]}"
    return cid


def test_settling_closes_the_file_and_says_so(client):
    """**جوهر البند**: الملف يُغلق، والإغلاق يُكتب على الملف."""
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.civil_id == "100000000003"))
        eid = emp.id
        before = db.scalars(select(models.AuditLog).where(
            models.AuditLog.entity_type == "employee",
            models.AuditLog.entity_id == eid)).all()
        before_ids = {a.id for a in before}
    finally:
        db.close()

    case_id = _drive_to_settled(client, eid, ("100000000003", "deleg123"))

    db = SessionLocal()
    try:
        emp = db.get(models.Employee, eid)
        rows = [a for a in db.scalars(select(models.AuditLog).where(
            models.AuditLog.entity_type == "employee",
            models.AuditLog.entity_id == eid)).all() if a.id not in before_ids]
    finally:
        db.close()

    assert emp.status == "terminated", f"لم تُغلق الخدمة: {emp.status}"
    assert rows, (
        "أُغلق ملف الموظف بلا حدث تدقيق عليه — الأثر كله تحت رقم الحالة"
    )
    ev = [a for a in rows if a.action == "employee_terminated"]
    assert ev, f"لا حدث خروج على الملف: {[a.action for a in rows]}"

    # والحدث يقول بأي سند: من يقرأ الملف يصل منه إلى الحالة، لا العكس.
    detail = ev[0].detail or ""
    assert str(case_id) in detail or "EOS/" in detail, (
        f"الحدث بلا مرجع الحالة: {detail}"
    )
    assert ev[0].user_id, "حدث خروج بلا منفذ — «من أغلقه» بلا جواب"


def test_the_event_records_what_changed(client):
    """وقبل/بعد يُميّز الإغلاق عن إعادة كتابة حالة مغلقة أصًلا."""
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.civil_id == "100000000004"))
        eid = emp.id
    finally:
        db.close()

    _drive_to_settled(client, eid, ("100000000004", "deleg123"))

    db = SessionLocal()
    try:
        ev = db.scalars(select(models.AuditLog).where(
            models.AuditLog.entity_type == "employee",
            models.AuditLog.entity_id == eid,
            models.AuditLog.action == "employee_terminated")).all()
    finally:
        db.close()
    assert ev, "لا حدث خروج"
    row = ev[-1]
    after = row.after_json if isinstance(row.after_json, dict) else {}
    before = row.before_json if isinstance(row.before_json, dict) else {}
    assert after.get("status") == "terminated", after
    assert before.get("status") and before["status"] != "terminated", (
        f"«قبل» لا يُظهر تغيًُّرا: {before}"
    )
    assert after.get("eos_case_id"), f"الحدث لا يصل إلى الحالة: {after}"


def test_the_exit_is_readable_from_the_employee_filter(client):
    """ومن يقرأ الملف بالفلتر العادي يراه — لا من يعرف رقم الحالة وحده."""
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.civil_id == "100000000005"))
        eid = emp.id
    finally:
        db.close()

    _drive_to_settled(client, eid, ("100000000005", "sup12345"))

    # سجلّ التدقيق دور رقابي لا تشغيلي: المالك يملك ``view_audit`` والمدير
    # لا يملكها بقرار تصميم (FIX-010). قياسه بحساب المدير كان يفحص بوّابة
    # الصلاحية لا وجود الحدث.
    hdr = auth_headers(login(client, *OWNER))
    r = client.get("/api/audit", headers=hdr,
                   params={"entity_type": "employee", "entity_id": eid})
    assert r.status_code == 200, r.text
    actions = [x["action"] for x in r.json()]
    assert "employee_terminated" in actions, (
        f"الخروج غير مقروء من ملف الموظف: {actions}"
    )


def test_no_exit_status_is_written_without_an_employee_event():
    """**الحارس الجامع**: كل موضع يكتب حالة خروج يكتب حدًثا على الموظف.

    القياس على المصدر كله لا على الموضع الذي أُصلح: طريق رابع يُضاف
    غًدا ويُجمّد ملًفا بصمت يسقط هنا يوم يُكتب، لا يوم يسأل أحد عن ملف
    أُغلق بلا سبب.
    """
    root = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in root.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        for m in re.finditer(r'\w*emp\w*\.status\s*=\s*"(terminated|archived)"', src):
            # النافذة بعد الكتابة: هل يُدقَّق على كيان employee قريًبا منها؟
            window = src[m.start():m.start() + 2500]
            if not re.search(r'audit\([^)]*"employee"', window, re.S):
                line = src[:m.start()].count("\n") + 1
                offenders.append(f"{path.name}:{line}")
    assert not offenders, (
        "حالة خروج تُكتب بلا حدث تدقيق على ملف الموظف: " + ", ".join(offenders)
    )
