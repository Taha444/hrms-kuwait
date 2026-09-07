# -*- coding: utf-8 -*-
"""البند 27 — «إسناد مسؤولي الفروع» ليس بيانات وحده: للإسناد فخّ.

قُيّد البند على أنه عمل بيانات: اربط كل فرع بمسؤوله. ثم قِستُ **مسار
الربط نفسه** فإذا فيه انقسام:

سؤال «من يشرف على هذا الفرع؟» له في النظام جوابان مكتوبان في موضعين:

1. ``branch_supervisors`` — تقرأه ``resolve_stage_approvers`` لتوجيه
   مرحلة «اعتماد مسؤول الفرع».
2. ``users.scope_branch_id`` — يقرأه ``resolve_scope`` ليحدّد ما يراه.

و``/users/{id}/scope`` يكتب في الأول **عند المستوى ``multi`` وحده**؛
وعند المستوى ``branch`` يمسح صفوفه ولا يكتب شيًئا. فمن يُسند مسؤول فرع
إلى فرع واحد من شاشة المستخدمين — وهو الاختيار الطبيعي لمسؤول فرع
واحد — يحصل على مشرف **يرى فرعه ولا يصله منه طلب أبًدا**.

**وهذا أسوأ من غياب الإسناد**: لو لم يُسنَد أحد لبقيت المهمة الحرجة
تقول «لا مسؤول مرتبط بفرع الموظف» وهي صادقة. أما هنا فالشاشة تُظهره
مسنًدا إلى الفرع، والمهمة تطلب إسناًدا تمّ — فيُقرأ التنبيه على أنه خطأ
في النظام لا نقٌص في الإعداد، ويُهمَل.

**والقاعدة المخالَفة هي قاعدة المشروع**: مصدر واحد للحقيقة. فالإصلاح
ليس إضافة قراءة ثالثة، بل جعل الكتابة واحدة: أي إسناد لمسؤول فرع إلى
فروع — واحد أو أكثر — يترك الجوابين متطابقين.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models, workflow
from app.database import SessionLocal
from app.security import hash_password
from tests.conftest import auth_headers, login

MANAGER = ("100000000001", "manager123")


@pytest.fixture
def supervisor():
    """مسؤول فرع جديد على فرع قائم — ويُزال هو وأثره بعد القياس."""
    db = SessionLocal()
    try:
        branch = db.scalars(select(models.Branch).limit(1)).first()
        emp = db.scalars(select(models.Employee).where(
            models.Employee.branch_id == branch.id).limit(1)).first()
        assert emp is not None, "الفرع بلا موظف — لا يُقاس التوجيه"
        u = models.User(
            civil_id="277700110099", password_hash=hash_password("Sup12345"),
            full_name="مسؤول فرع للقياس", role="branch_supervisor",
            company_id=branch.company_id, is_active=True,
            must_change_password=False)
        db.add(u)
        db.commit()
        made = {"uid": u.id, "bid": branch.id, "eid": emp.id,
                "cid": branch.company_id}
    finally:
        db.close()

    yield made

    db = SessionLocal()
    try:
        db.execute(sa_delete(models.BranchSupervisor).where(
            models.BranchSupervisor.user_id == made["uid"]))
        db.execute(sa_delete(models.AuditLog).where(
            models.AuditLog.user_id == made["uid"]))
        db.execute(sa_delete(models.User).where(models.User.id == made["uid"]))
        db.commit()
    finally:
        db.close()


def _request_for(db, made) -> models.Request:
    req = models.Request(
        company_id=made["cid"], employee_id=made["eid"],
        request_type_code="leave", status="pending", current_stage=0,
        payload_json={"leave_type": "annual", "days": 1})
    db.add(req)
    db.flush()
    return req


def _routed_user_ids(made) -> set[int]:
    """من يصله فعًلا طلب على موظف هذا الفرع في مرحلة مسؤول الفرع."""
    db = SessionLocal()
    try:
        req = _request_for(db, made)
        stage = {"order": 0, "role": "branch_supervisor",
                 "label": "اعتماد مسؤول الفرع"}
        ids = {u.id for u in workflow.resolve_stage_approvers(db, req, stage)}
        db.rollback()
    finally:
        db.close()
    return ids


def _set_scope(client, made, **params):
    hdr = auth_headers(login(client, *MANAGER))
    q = "&".join(f"{k}={v}" for k, v in params.items())
    return client.post(f"/api/users/{made['uid']}/scope?{q}", headers=hdr)


def test_scoping_a_supervisor_to_one_branch_routes_requests_to_them(client, supervisor):
    """**جوهر العطل**: مشرف على فرع واحد يرى فرعه ولا يصله منه طلب.

    وهو الاختيار الطبيعي لمن يشرف على فرع واحد — أي أن الحالة الشائعة
    هي المعطوبة، لا الحالة النادرة.
    """
    r = _set_scope(client, supervisor, level="branch", branch_id=supervisor["bid"])
    assert r.status_code == 200, r.text
    assert supervisor["uid"] in _routed_user_ids(supervisor), (
        "أُسنِد إلى الفرع في الشاشة ولا يصله منه طلب"
    )


def test_the_two_answers_to_who_supervises_this_branch_agree(client, supervisor):
    """**ولا موضعان لقاعدة واحدة**: ما يُعرض مسنًدا هو ما يُوجَّه إليه.

    الشاشة تقرأ ``branch_supervisors``، والتوجيه يقرأها. فاختلافهما عن
    نيّة الإسناد هو الانقسام نفسه.
    """
    assert _set_scope(client, supervisor, level="branch",
                      branch_id=supervisor["bid"]).status_code == 200
    hdr = auth_headers(login(client, *MANAGER))
    listed = client.get("/api/org/structure", headers=hdr)
    assert listed.status_code == 200, listed.text
    row = next(b for b in listed.json()["branches"] if b["id"] == supervisor["bid"])
    assert "مسؤول فرع للقياس" in row["supervisors"], row["supervisors"]


def test_multi_scope_still_routes_as_before(client, supervisor):
    """والمستوى الذي كان يعمل يبقى كما هو — لا إصلاح يكسر طرًفا سليًما."""
    assert _set_scope(client, supervisor, level="multi",
                      branch_ids=supervisor["bid"]).status_code == 200
    assert supervisor["uid"] in _routed_user_ids(supervisor)


def test_widening_the_scope_back_to_the_company_unassigns_them(client, supervisor):
    """**وللإسناد باب خروج**: إسناٌد لا يُفكّ يتراكم بلا مراجعة.

    ومن نُقل عن الفرع يبقى معتمًِدا له إلى الأبد لو لم يُفكّ الربط.
    """
    assert _set_scope(client, supervisor, level="branch",
                      branch_id=supervisor["bid"]).status_code == 200
    assert supervisor["uid"] in _routed_user_ids(supervisor)

    assert _set_scope(client, supervisor, level="company").status_code == 200
    assert supervisor["uid"] not in _routed_user_ids(supervisor), (
        "بقي معتمًِدا لفرع لم يعد مسؤوًلا عنه"
    )


def test_an_unlinked_branch_still_has_no_approver(client, supervisor):
    """**ولا يُصلَح العطل بفتح الباب**: فرع بلا إسناد يبقى بلا معتمِد.

    السقوط الصامت للمدير هو ما أنتج البندين QA-01/QA-02 أصًلا — فالإصلاح
    يوصل من أُسنِد، ولا يخترع من لم يُسنَد.
    """
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.BranchSupervisor).where(
            models.BranchSupervisor.branch_id == supervisor["bid"])).all()
        kept = [(r.company_id, r.branch_id, r.user_id) for r in rows]
        for r in rows:
            db.delete(r)
        db.commit()
    finally:
        db.close()
    try:
        assert _routed_user_ids(supervisor) == set(), "معتمِد من حيث لا إسناد"
    finally:
        db = SessionLocal()
        try:
            for cid, bid, uid in kept:
                db.add(models.BranchSupervisor(
                    company_id=cid, branch_id=bid, user_id=uid))
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# والنقص يُعرَض قبل أن يوقف طلًبا — لا بعده
# ---------------------------------------------------------------------------

def test_a_branch_without_a_supervisor_says_so_on_the_screen():
    """**وغياب الإسناد كان لا يُرى**: سطر المسؤولين يُخفى عند الفراغ.

    فيستوي على شاشة الهيكل الفرعُ المُسنَد وغيرُ المُسنَد، ولا يُكتشف
    النقص إلا حين يقف طلب عند مرحلة بلا معتمِد — أي **بعد** الضرر.
    وبند «إسناد مسؤولي الفروع» عمل بيانات، ولا يُنجَز عمل بيانات لا
    تدلّ الشاشة على موضعه.
    """
    from pathlib import Path

    front = Path(__file__).resolve().parents[2] / "frontend" / "src"
    page = (front / "pages" / "CompanyStructure.tsx").read_text(encoding="utf-8")
    i18n = (front / "i18n.tsx").read_text(encoding="utf-8")

    assert "no_supervisor" in page, "الشاشة لا تذكر غياب المسؤول"
    assert "no_supervisor" in i18n and "assign_supervisor" in i18n, "مفاتيح ناقصة"
    # ورسالة تدلّ على عمل: طريق إلى موضع الإسناد لا وصٌف للحال.
    assert 'to="/users"' in page, "لا طريق من التنبيه إلى موضع الإسناد"


def test_linking_a_non_supervisor_to_a_branch_is_refused(client, supervisor):
    """**ولا إسناد صامت بلا أثر**: من ليس دوره مسؤول فرع يُردّ صراحًة.

    كان الربط يُكتب ويعود ``ok`` ثم لا يصل صاحبَه طلب — نجاٌح ظاهر بلا
    أثر، وهو أسوأ من رفض مفهوم.
    """
    db = SessionLocal()
    try:
        other = db.scalar(select(models.User).where(
            models.User.company_id == supervisor["cid"],
            models.User.role == "accountant"))
        oid = other.id
    finally:
        db.close()

    hdr = auth_headers(login(client, *MANAGER))
    r = client.post(f"/api/branches/{supervisor['bid']}/supervisors/{oid}", headers=hdr)
    assert r.status_code == 400, r.text
    assert "مسؤول فرع" in r.json()["detail"], r.json()
