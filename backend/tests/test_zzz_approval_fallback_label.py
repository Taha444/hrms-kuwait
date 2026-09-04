# -*- coding: utf-8 -*-
"""P8-31 — بديل اعتماد الفرع: السلوك رسمي، والتسمية تقول الحقيقة.

**ما ظهر عند القياس، لا ما افترضته:**

بدأت أفحص مسار السقوط ``direct_manager → branch_supervisor`` فوجدته
**شيفرة ميتة**: لا سلسلة واحدة في الكتالوج تستعمل الدور
``direct_manager``. الأدوار المستعملة خمسة، وليس فيها هذا.

وستّ عشرة مرحلة تحمل تسمية «اعتماد المسؤول المباشر» ودورها
``branch_supervisor``. **ولم أغيّرها**: مسؤول الفرع *هو* المسؤول المباشر
في نموذج هذا النظام — بدليل أن ``resolve_stage_approvers`` تسقط إليه
حين لا يوجد مدير مباشر مسجَّل. والتسمية موجَّهة للناس لا للشيفرة،
وتغييرها بناًء على قراءة لغوية هو ما تحذّر منه قواعد الحماية.

**والعطل الحقيقي**: مرحلة جارية **بلا معتمِد يُحلّ** كانت تُعرض كغيرها.
فيقرأ الموظف «بانتظار اعتماد مسؤول الفرع» وينتظر من لا وجود له — ولا
يسأل أحد عمّا يبدو ماضًيا في طريقه. والتنبيه يذهب لشؤون الموظفين وحدهم
(``_warn_unassigned_stage``)، فيبقى صاحب الطلب خارج القصة.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")

LEAVE_PAYLOAD = {
    "start_date": "2026-11-01", "end_date": "2026-11-03", "days": 3,
    "leave_type": "annual", "reason": "فحص تسمية المرحلة",
}


def _supervisor_stage_type():
    """نوع طلب مرحلته الأولى بدور مسؤول الفرع — يُقرأ من الكتالوج."""
    for rt in workflow.DEFAULT_REQUEST_TYPES:
        chain = rt.get("approval_chain_json") or []
        if chain and chain[0].get("role") == "branch_supervisor":
            return rt
    return None


def test_the_catalogue_uses_branch_supervisor_not_direct_manager():
    """توثيق ما ظهر: لا سلسلة تستعمل ``direct_manager``.

    ولو أُضيفت غًدا يسقط هذا الاختبار — وهو الوقت الصحيح لمراجعة مسار
    السقوط الذي يبقى اليوم بلا مستدعٍ.
    """
    roles = {st.get("role")
             for rt in workflow.DEFAULT_REQUEST_TYPES
             for st in (rt.get("approval_chain_json") or [])}
    assert "branch_supervisor" in roles, "لا مرحلة لمسؤول الفرع"
    assert "direct_manager" not in roles, (
        "دخل direct_manager الكتالوج — راجع مسار السقوط في "
        "resolve_stage_approvers، فقد صار حًيا"
    )


@pytest.fixture
def employee_with_no_supervisor():
    """موظف بلا فرع: مرحلة مسؤول الفرع لا تجد أحًدا.

    وهو السبب الذي توثّقه الشيفرة نفسها: «الموظف بلا فرع، أو الفرع بلا
    مسؤول مربوط».
    """
    db = SessionLocal()
    made = None
    try:
        hr = db.scalar(select(models.User).where(
            models.User.civil_id == HR[0]))
        emp = models.Employee(
            company_id=hr.company_id, name="موظف بلا فرع",
            civil_id="233300110055", job_title="فني", basic_salary=300,
            status="active", nationality="مصري", branch_id=None)
        db.add(emp)
        db.commit()
        made = emp.id
        yield emp.id
    finally:
        if made:
            # التنظيف على ما أنشأه هذا الاختبار وحده.
            #
            # أول كتابة حذفت **كل** مهام الطلبات، فسقط اختبار في ملف آخر
            # يقيس بقاء مهام ما بعد الإغلاق. وتنظيف يتجاوز ما أنشأه
            # صاحبه يُفسد قياس غيره ويبدو عطًلا في شيفرة سليمة.
            mine = [r for (r,) in db.execute(select(models.Request.id).where(
                models.Request.employee_id == made)).all()]
            if mine:
                db.execute(sa_delete(models.Task).where(
                    models.Task.related_entity_type == "request",
                    models.Task.related_entity_id.in_(mine)))
            db.execute(sa_delete(models.Request).where(
                models.Request.employee_id == made))
            db.execute(sa_delete(models.Employee).where(
                models.Employee.id == made))
            db.commit()
        db.close()


def test_the_stage_really_has_no_approver(employee_with_no_supervisor):
    """خطّ الأساس: الحالة مبنيّة فعًلا، وإلا كان ما بعدها فارًغا."""
    rt_def = _supervisor_stage_type()
    assert rt_def, "لا نوع مرحلته الأولى لمسؤول الفرع"

    db = SessionLocal()
    try:
        emp = db.get(models.Employee, employee_with_no_supervisor)
        req = models.Request(
            company_id=emp.company_id, employee_id=emp.id,
            request_type_code=rt_def["code"], status="pending", current_stage=0)
        db.add(req)
        db.commit()
        approvers = workflow.resolve_stage_approvers(
            db, req, rt_def["approval_chain_json"][0])
        rid = req.id
    finally:
        db.execute(sa_delete(models.Request).where(models.Request.id == rid))
        db.commit()
        db.close()
    assert approvers == [], f"وُجد معتمِد رغم غياب الفرع: {approvers}"


def test_a_stage_with_no_approver_says_so(client, employee_with_no_supervisor):
    """**جوهر البند**: الشاشة تقول إن الطلب واقف، لا «بانتظار فلان»."""
    rt_def = _supervisor_stage_type()
    hdr = auth_headers(login(client, *HR))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": employee_with_no_supervisor,
        "request_type_code": rt_def["code"],
        "payload_json": LEAVE_PAYLOAD,
    })
    if r.status_code != 201:
        pytest.fail(f"تعذّر إنشاء الطلب: {r.status_code} {r.text[:200]}")

    body = client.get(f"/api/requests/{r.json()['id']}", headers=hdr).json()
    current = [s for s in body.get("stages", []) if s.get("state") == "current"]
    assert current, "لا مرحلة جارية"
    st = current[0]
    assert st.get("blocked_reason"), (
        "مرحلة بلا معتمِد تُعرض كأن أحًدا سيتصرّف: "
        f"{ {k: st.get(k) for k in ('label', 'role', 'state')} }"
    )
    assert "معتمِد" in st["blocked_reason"], st["blocked_reason"]


def test_a_normal_stage_is_not_marked_blocked(client):
    """ولا تُوسَم مرحلة سليمة: وسم على كل شيء يعني لا شيء."""
    hdr = auth_headers(login(client, *HR))
    mine = client.get("/api/requests/mine", headers=hdr).json()
    if not mine:
        return
    body = client.get(f"/api/requests/{mine[0]['id']}", headers=hdr).json()
    for st in body.get("stages", []):
        if st.get("state") != "current" and st.get("blocked_reason"):
            pytest.fail(f"مرحلة غير جارية موسومة متوقّفة: {st}")


def test_hr_is_told_too_not_only_the_screen(client, employee_with_no_supervisor):
    """والشاشة لا تُغني عن التنبيه: من يُصلح الإعداد غير من ينتظر."""
    rt_def = _supervisor_stage_type()
    hdr = auth_headers(login(client, *HR))
    client.post("/api/requests", headers=hdr, json={
        "employee_id": employee_with_no_supervisor,
        "request_type_code": rt_def["code"],
        "payload_json": LEAVE_PAYLOAD,
    })

    db = SessionLocal()
    try:
        gaps = db.scalars(select(models.Task).where(
            models.Task.type == "config_gap",
            models.Task.status.in_(("open", "in_progress")))).all()
    finally:
        db.close()
    assert gaps, "لا تنبيه لشؤون الموظفين بالفجوة في الإعداد"
