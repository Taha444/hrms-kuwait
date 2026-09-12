# -*- coding: utf-8 -*-
"""كتابٌة تعبُر الشركات — صنُف عطٍل تكرّر، فيُحرَس بالكنس لا بالحالة.

**ثلاث مرات في جولٍة واحدة** كان العطل **نسخًة ثانية من قاعدٍة صحيحة،
والعاملُة هي المعطوبة**:

1. ``_warn_no_impartial_approver`` يستعلم مقيًَّدا بالشركة، والمالك
   ``company_id = None`` — فيُصعَّد إلى لا أحد.
2. بصمٌة واحدٌة لعدّة مستقبلين تحجب كلَّ من بعد الأول.
3. و``POST /documents`` يحدّث مهامّ الانتهاء **بلا قيٍد على مستنٍد ولا
   على شركة**، والدالُة المقيَّدة اثنَي عشر سطًرا فوقه.

فبُني ``scripts/unscoped_writes.py`` يكنس الصنف كلَّه: كتابٌة جماعية لا
تسمّي صًفّا ولا شركة. **ولا يُمسَك هذا الشكل باختبار وظيفي** — تركيُب
حالٍة تُثبته يعني إفساد بيانات السويت كلّها. فيُمسَك بقراءة الشيفرة.

**والعطُل الرابع وجده الكنس**: ``POST /tasks/cleanup-orphans`` كان يكنس
المهامّ اليتيمة بلا قيد شركة، و``manage_tasks`` يحملها
``company_manager`` و``delegate`` — وكلاهما مقيٌَّد بشركته. فمديُر الشركة
الأولى يكنس مهامّ الثانية: الفعُل صحيٌح في كل صّف، **والفاعل يتخطّى
نطاقه**.
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

MGR1 = ("100000000001", "manager123")
ADMIN = ("000000000000", "admin123")


# ---------------------------------------------------------------------------
# الكنس نفسه
# ---------------------------------------------------------------------------

def test_no_bulk_write_crosses_the_company_boundary():
    """**الحارس الدائم**: لا ``update``/``delete`` جماعية بلا نطاق.

    ويستثني الجداول العامّة التي لا تحمل شركًة أصًلا (الرموز المنتهية،
    سجلّ تشغيل المهام) — فالحذف الدوري فيها مشروع.
    """
    import importlib.util
    import pathlib

    path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "unscoped_writes.py"
    spec = importlib.util.spec_from_file_location("unscoped_writes", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    found = mod.bulk_writes()
    assert not found, "كتابٌة جماعية بلا نطاق:\n" + "\n".join(
        f"  {p}:{ln}\n      " + stmt.splitlines()[0].strip()
        for p, ln, stmt in found)


def test_the_document_upload_no_longer_closes_every_expiry_task():
    """**والموضع الذي وُجد فيه العطل يُحرَس باسمه.**

    فكنٌس عامٌّ قد يُخضَّر بحيلة، وهذا يسمّي الدالة.
    """
    import inspect

    from app.routers import documents as D

    assert "update(models.Task)" not in inspect.getsource(D.upload_document)


# ---------------------------------------------------------------------------
# وكنُس المهام اليتيمة لا يتخطّى شركته
# ---------------------------------------------------------------------------

def _orphan_task(company_id: int, req_id: int) -> int:
    db = SessionLocal()
    try:
        t = models.Task(company_id=company_id, type="request_stage",
                        title="مهمٌة يتيمة للقياس",
                        related_entity_type="request", related_entity_id=req_id,
                        status="open", severity="info",
                        dedup_key=f"orphan_probe:{company_id}:{req_id}")
        db.add(t)
        db.commit()
        return t.id
    finally:
        db.close()


def _closed_request(company_id: int) -> int:
    """طلٌب منتٍه — فمهمتُه المفتوحة يتيمٌة بحّق."""
    db = SessionLocal()
    try:
        emp_id = db.scalar(select(models.Employee.id).where(
            models.Employee.company_id == company_id))
        req = models.Request(company_id=company_id, employee_id=emp_id,
                             request_type_code="REQLV", status="completed",
                             payload_json={})
        db.add(req)
        db.commit()
        return req.id
    finally:
        db.close()


def _status(task_id: int) -> str:
    db = SessionLocal()
    try:
        return db.get(models.Task, task_id).status
    finally:
        db.close()


def _cleanup(ids: list[int], req_ids: list[int]) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Task).where(models.Task.id.in_(ids)))
        db.execute(sa_delete(models.Request).where(models.Request.id.in_(req_ids)))
        db.commit()
    finally:
        db.close()


def test_cleanup_orphans_does_not_touch_another_company(client):
    """**جوهر العطل الرابع**: مديُر الشركة الأولى لا يكنس مهامّ الثانية."""
    r1, r2 = _closed_request(1), _closed_request(2)
    t1, t2 = _orphan_task(1, r1), _orphan_task(2, r2)
    try:
        resp = client.post("/api/tasks/cleanup-orphans",
                           headers=auth_headers(login(client, *MGR1)))
        assert resp.status_code == 200, resp.text[:300]
        assert _status(t1) == "dismissed", "لم يكنس مهمَة شركته"
        assert _status(t2) == "open", \
            "كنَس مهمًة في شركٍة أخرى — الفاعل تخطّى نطاقه"
    finally:
        _cleanup([t1, t2], [r1, r2])


def test_an_overseer_may_still_sweep_every_company(client):
    """ومن هو فوق الشركات يكنس الكلّ — الحارس لا يُلغي القدرة."""
    r1, r2 = _closed_request(1), _closed_request(2)
    t1, t2 = _orphan_task(1, r1), _orphan_task(2, r2)
    try:
        resp = client.post("/api/tasks/cleanup-orphans",
                           headers=auth_headers(login(client, *ADMIN)))
        assert resp.status_code == 200, resp.text[:300]
        assert _status(t1) == "dismissed" and _status(t2) == "dismissed", \
            (_status(t1), _status(t2))
    finally:
        _cleanup([t1, t2], [r1, r2])


def test_the_scope_comes_from_the_one_helper():
    """والنطاُق من ``scope_company_id`` لا من شرٍط مكتوٍب بالي;د."""
    import inspect

    from app.routers import tasks as T

    src = inspect.getsource(T.cleanup_orphan_tasks)
    assert "scope_company_id" in src, "نطاٌق مكتوٌب بالي;د في الكنس"


# ---------------------------------------------------------------------------
# والقراءُة تُحرَس كما تُحرَس الكتابة
# ---------------------------------------------------------------------------

DELEGATE1 = ("100000000004", "deleg123")


def _permit_with_note(company_id: int, note: str) -> tuple[int, int]:
    """إقامٌة في شركٍة وملاحظٌة حكومية عليها — تُعيد ``(permit_id, log_id)``."""
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == company_id))
        assert emp is not None, f"ال موّظف في الشركة {company_id}"
        p = models.Permit(company_id=company_id, employee_id=emp.id,
                          kind="residency", number=f"P{company_id}-عزل")
        db.add(p)
        db.flush()
        log = models.GovLog(company_id=company_id, entity_type="permit",
                            entity_id=p.id, action="note", note=note)
        db.add(log)
        db.commit()
        return p.id, log.id
    finally:
        db.close()


def _drop_permit(permit_id: int, log_id: int) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.GovLog).where(models.GovLog.id == log_id))
        db.execute(sa_delete(models.Permit).where(models.Permit.id == permit_id))
        db.commit()
    finally:
        db.close()


def test_government_notes_do_not_cross_the_company_boundary(client):
    """**والكتابُة كانت محروسًة والقراءُة مكشوفة.**

    ``add_note`` يتحقّق من نوع الكيان ثم
    ``assert_same_company(user, entity.company_id)``. و``list_notes`` كان
    يُرشِّح بـ``entity_type`` و``entity_id`` من الاستعلام وحدهما — والمعرُِّف
    عددٌ متسلسل. فمندوٌب في الشركة الأولى يكتب ``entity_id`` لإقامٍة في
    الثانية فيقرأ ما نقص في معاملتها ومتى رُدّت ومن كتبها.

    وهو الصنُف نفسه الذي كُنس في الكتابة — فيُحرَس في القراءة.
    """
    p1, l1 = _permit_with_note(1, "ملاحظُة الشركة الأولى")
    p2, l2 = _permit_with_note(2, "ملاحظُة الشركة الثانية")
    try:
        h = auth_headers(login(client, *DELEGATE1))

        mine = client.get("/api/pro/notes",
                          params={"entity_type": "permit", "entity_id": p1},
                          headers=h)
        assert mine.status_code == 200, mine.text[:300]
        assert any("الأولى" in (r["note"] or "") for r in mine.json()), mine.json()

        theirs = client.get("/api/pro/notes",
                            params={"entity_type": "permit", "entity_id": p2},
                            headers=h)
        assert theirs.status_code == 200, theirs.text[:300]
        assert theirs.json() == [], \
            f"قرأ ملاحظاِت شركٍة أخرى: {theirs.json()}"
    finally:
        _drop_permit(p1, l1)
        _drop_permit(p2, l2)


def test_an_overseer_still_reads_every_company_s_notes(client):
    """ومن هو فوق الشركات يقرأ الكلّ — الحارُس ال يُلغي القدرة."""
    p2, l2 = _permit_with_note(2, "ملاحظُة الشركة الثانية")
    try:
        r = client.get("/api/pro/notes",
                       params={"entity_type": "permit", "entity_id": p2},
                       headers=auth_headers(login(client, *ADMIN)))
        assert r.status_code == 200, r.text[:300]
        assert any("الثانية" in (x["note"] or "") for x in r.json()), r.json()
    finally:
        _drop_permit(p2, l2)


def test_the_note_type_is_validated_as_it_is_on_write(client):
    """ونوٌع ال يُكتَب أبًدا ال يُستعلَم به — كما في ``add_note``."""
    r = client.get("/api/pro/notes",
                   params={"entity_type": "employee", "entity_id": 1},
                   headers=auth_headers(login(client, *DELEGATE1)))
    assert r.status_code == 400, (r.status_code, r.text[:200])


def test_template_existence_follows_the_one_scope_rule(client):
    """**وقاعدُة نطاق القوالب في أربعة مواضع، وكان الخامُس مكشوًفا.**

    ``list_templates`` بـ``scope_company_id``، و``get``/``generate``
    بـ``assert_same_company``، والمولُّد بـ``company_id IS NULL OR ==``.
    و``/exists`` بال قيد — فقالٌب خاٌصّ بشركٍة أخرى يُقال «موجود»، فيظهر زُر
    توليٍد يسقط بـ404 (وهو ما كُتب النداُء لتجنّبه)، ويُفشى وجودُه بكوده.
    """
    db = SessionLocal()
    tid = None
    code = "ZZZ-SCOPE-C2"
    try:
        row = models.DocumentTemplate(
            company_id=2, code=code, name="قالُب الشركة الثانية",
            category="other", body_html="<p>نصّ</p>", is_active=True)
        db.add(row)
        db.commit()
        tid = row.id
    finally:
        db.close()
    try:
        r = client.get("/api/templates/exists", params={"codes": code},
                       headers=auth_headers(login(client, *MGR1)))
        assert r.status_code == 200, r.text[:300]
        assert r.json().get(code) is False, \
            "قالُب شركٍة أخرى يُقال موجوٌد — فيظهر زٌّر يسقط بـ404"

        # ومن هو فوق الشركات يراه.
        r2 = client.get("/api/templates/exists", params={"codes": code},
                        headers=auth_headers(login(client, *ADMIN)))
        assert r2.json().get(code) is True, r2.json()
    finally:
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.DocumentTemplate).where(
                models.DocumentTemplate.id == tid))
            db.commit()
        finally:
            db.close()


def test_a_global_template_is_visible_to_every_company(client):
    """والعاُم يبقى للكلّ — وإال كسر القيُد ما كان يعمل."""
    db = SessionLocal()
    try:
        glob = db.scalar(select(models.DocumentTemplate).where(
            models.DocumentTemplate.company_id.is_(None),
            models.DocumentTemplate.is_active == True))  # noqa: E712
        if glob is None:
            import pytest
            pytest.skip("ال قالَب عاًما في هذه القاعدة")
        code = glob.code
    finally:
        db.close()
    r = client.get("/api/templates/exists", params={"codes": code},
                   headers=auth_headers(login(client, *MGR1)))
    assert r.json().get(code) is True, r.json()


# ---------------------------------------------------------------------------
# ومعرٌِّف في المسار ال يُغني عن نطاق
# ---------------------------------------------------------------------------

HR1 = ("100000000002", "hr12345")

def _task_of(company_id: int, assignee_login: tuple[str, str] | None = None,
             status: str = "open") -> tuple[int, int]:
    """مهمٌَّة في شركٍة مُسنَدٌة إلى أحد مستخدميها — ``(task_id, assignee_id)``."""
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(
            models.User.company_id == company_id, models.User.role == "hr"))
        assert u is not None, f"ال مستخدَم hr في الشركة {company_id}"
        row = models.Task(company_id=company_id, assignee_user_id=u.id,
                          type="document", severity="info", status=status,
                          title=f"مهمُة عزٍل للشركة {company_id}")
        db.add(row)
        db.commit()
        return row.id, u.id
    finally:
        db.close()


def _task_row(task_id: int):
    db = SessionLocal()
    try:
        r = db.get(models.Task, task_id)
        return (r.status, r.claimed_by_user_id) if r else (None, None)
    finally:
        db.close()


def _drop_task(task_id: int) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Task).where(models.Task.id == task_id))
        db.commit()
    finally:
        db.close()


def test_a_task_cannot_be_claimed_from_another_company(client):
    """**ومعرٌِّف متسلٌسل بال نطاٍق يُعطِّل عمَل شركٍة أخرى.**

    ``claim`` كان ``get_current_user`` وحده: ال شركَة وال إسناد. فمستخدٌم
    في الأولى يلتقط مهمًة في الثانية، فتصير ``in_progress`` باسمه
    **ويُمنَع صاحبُها** بـ409 «ملتقطة من مستخدم آخر».
    """
    t1, _ = _task_of(1)
    t2, _ = _task_of(2)
    try:
        h = auth_headers(login(client, *HR1))
        mine = client.post(f"/api/tasks/{t1}/claim", headers=h)
        assert mine.status_code == 200, mine.text[:300]

        theirs = client.post(f"/api/tasks/{t2}/claim", headers=h)
        assert theirs.status_code in (403, 404), \
            f"التقط مهمًة في شركٍة أخرى: {theirs.status_code} {theirs.text[:200]}"
        status, claimed = _task_row(t2)
        assert claimed is None and status == "open", (status, claimed)
    finally:
        _drop_task(t1)
        _drop_task(t2)


def test_a_colleague_may_still_claim_inside_the_company(client):
    """**والعقُد القائُم ال يُغيَّر بظنّ.**

    أضفتُ شرَط «المهمُّة مُسنَدٌة إليك» على الالتقاط، فأسقط
    ``test_task_claim_blocked_when_another_user_already_claimed``: العقُد أن
    مستخدًما آخَر في الشركة **يصل** إلى الالتقاط، و409 «ملتقطة من مستخدم
    آخر» موجودٌة لهذا بعينه — فلو كان الالتقاُط شخصًيا لما كان لها معنى.

    فيُحرَس العقُد كما هو: زميٌل في الشركة يلتقط، ومن بعده يُردّ بـ409. وأما
    **النطاُق** فيبقى مفروًضا — وهو العطُل المقيس (الحارُس أعاله).
    """
    tid, _ = _task_of(1)
    try:
        first = client.post(f"/api/tasks/{tid}/claim",
                            headers=auth_headers(login(client, *MGR1)))
        assert first.status_code == 200, first.text[:300]
        second = client.post(f"/api/tasks/{tid}/claim",
                             headers=auth_headers(login(client, *HR1)))
        assert second.status_code == 409, (second.status_code, second.text[:200])
    finally:
        _drop_task(tid)


def test_a_finished_task_is_never_reopened_by_release(client):
    """**وإطالٌق بال فحص حالٍة يُعيد فتَح ما أُنجِز.**

    الشرُط كان يسقط كلُّه إن كانت المهمُّة غيَر ملتقَطة، ثم يُكتَب
    ``status = "open"``. فمهمٌَّة ``done`` تُعاد مفتوحًة: عدّاٌد يكذب، وقارٌئ
    يفقد الثقَة بالصندوق فيُهمله كلَّه.
    """
    tid, _ = _task_of(1, status="done")
    try:
        r = client.post(f"/api/tasks/{tid}/release",
                        headers=auth_headers(login(client, *HR1)))
        assert r.status_code == 409, (r.status_code, r.text[:200])
        assert _task_row(tid)[0] == "done", _task_row(tid)
    finally:
        _drop_task(tid)


def test_release_does_not_reach_another_company(client):
    """والإطالُق ال يعبر الشركات — وإن كانت المهمُّة مفتوحًة غيَر ملتقَطة."""
    tid, _ = _task_of(2)
    try:
        r = client.post(f"/api/tasks/{tid}/release",
                        headers=auth_headers(login(client, *HR1)))
        assert r.status_code in (403, 404), (r.status_code, r.text[:200])
    finally:
        _drop_task(tid)


def test_a_notification_is_not_redelivered_into_another_company(client):
    """**وأثٌر يخرج من النظام** — بريٌد أو رسالٌة إلى مستخدٍم في شركٍة أخرى.

    ``manage_tasks`` يحملها ``company_manager`` و``delegate``، وكالهما
    مقيٌَّد بشركته — و``retry-delivery`` كان بال تحقُّق.
    """
    tid, _ = _task_of(2)
    try:
        r = client.post(f"/api/tasks/{tid}/retry-delivery",
                        headers=auth_headers(login(client, *MGR1)))
        assert r.status_code in (403, 404), (r.status_code, r.text[:200])
    finally:
        _drop_task(tid)


def test_a_delivery_failure_does_not_echo_the_exception(client):
    """والسبُب يُحفَظ ال يُفشى — الردُّ يقول ما يُفعل.

    ``str(e)`` يحمل مضيَف المزوّد ورأَس طلٍب ومفتاًحا مقطوًعا.
    """
    import inspect

    from app.routers import tasks as T

    src = inspect.getsource(T.retry_delivery)
    body = src.split("except Exception")[-1]
    assert "str(e)[:120]" not in body, "نصُّ الاستثناء يُرسَل إلى العميل"
    assert "task.last_delivery_error = str(e)" in body, "السبُب ال يُحفَظ"


def test_a_delegation_cannot_be_granted_across_companies(client):
    """**وإنشاُء سلطِة اعتماٍد في شركٍة أخرى.**

    ``_may_manage`` كان ``user.role in ("hr", "super_admin")`` بال شركة،
    و``hr`` دوٌر مقيٌَّد بشركته. والسطُر التالي يشترط أن يكون المفوَّض إليه
    في شركة **المفوِّض** — فالتفويُض يقع صحيًحا داخل الشركة الثانية بيٍد من
    خارجها.
    """
    db = SessionLocal()
    try:
        d_from = db.scalar(select(models.User).where(
            models.User.company_id == 2, models.User.role == "company_manager"))
        d_to = db.scalar(select(models.User).where(
            models.User.company_id == 2, models.User.role == "hr"))
        if d_from is None or d_to is None:
            import pytest
            pytest.skip("ال مستخدمين في الشركة الثانية")
        a, b = d_from.id, d_to.id
    finally:
        db.close()

    r = client.post("/api/delegations", params={"delegator_user_id": a},
                    json={"delegate_user_id": b,
                          "starts_at": "2031-01-01T00:00:00",
                          "ends_at": "2031-01-10T00:00:00"},
                    headers=auth_headers(login(client, *HR1)))
    assert r.status_code in (403, 404, 422), \
        f"منح تفويًضا في شركٍة أخرى: {r.status_code} {r.text[:200]}"
    db = SessionLocal()
    try:
        made = db.scalars(select(models.ApprovalDelegation).where(
            models.ApprovalDelegation.delegator_user_id == a,
            models.ApprovalDelegation.delegate_user_id == b)).all()
        assert not made, "صٌّف تفويٍض أُنشئ في شركٍة أخرى"
    finally:
        db.close()


def test_hr_still_manages_delegations_inside_its_own_company(client):
    """وموارٌد بشرية تُدير تفويضاِت شركتها — التضييُق ال يمنع ما كان يعمل."""
    from app.routers.delegations import _may_manage

    db = SessionLocal()
    try:
        hr1 = db.scalar(select(models.User).where(
            models.User.company_id == 1, models.User.role == "hr"))
        mgr1 = db.scalar(select(models.User).where(
            models.User.company_id == 1, models.User.role == "company_manager"))
        other = db.scalar(select(models.User).where(models.User.company_id == 2))
        assert hr1 is not None and mgr1 is not None and other is not None
        assert _may_manage(hr1, mgr1) is True, "مُنع من شركته"
        assert _may_manage(hr1, other) is False, "وصل إلى شركٍة أخرى"
        assert _may_manage(hr1, hr1) is True, "مُنع من نفسه"
    finally:
        db.close()


def test_company_memberships_are_not_readable_from_another_company(client):
    """**والقراءُة كانت أضعَف من الكتابة عند البيان الواحد.**

    ``DELETE /users/{id}/company-links/{link}`` يشترط ``require_super_admin``؛
    و``GET`` نظيرُه كان ``manage_users`` بال نطاق. فمديُر الشركة الأولى يقرأ
    بمعرٍِّف متسلسل عضوياِت أيِّ مستخدم: أسماَء الشركات وأسماَء سجاّلته.
    """
    db = SessionLocal()
    try:
        mine = db.scalar(select(models.User).where(
            models.User.company_id == 1, models.User.role == "hr"))
        theirs = db.scalar(select(models.User).where(
            models.User.company_id == 2, models.User.role == "hr"))
        assert mine is not None and theirs is not None
        a, b = mine.id, theirs.id
    finally:
        db.close()

    h = auth_headers(login(client, *MGR1))
    ok = client.get(f"/api/users/{a}/company-links", headers=h)
    assert ok.status_code == 200, ok.text[:300]

    out = client.get(f"/api/users/{b}/company-links", headers=h)
    assert out.status_code in (403, 404), \
        f"قرأ عضوياِت مستخدٍم في شركٍة أخرى: {out.status_code} {out.text[:200]}"


def test_an_overseer_still_reads_every_membership(client):
    """ومن هو فوق الشركات يقرأ الكلَّ — الحارُس ال يُلغي القدرة."""
    db = SessionLocal()
    try:
        theirs = db.scalar(select(models.User).where(
            models.User.company_id == 2, models.User.role == "hr"))
        assert theirs is not None
        b = theirs.id
    finally:
        db.close()
    r = client.get(f"/api/users/{b}/company-links",
                   headers=auth_headers(login(client, *ADMIN)))
    assert r.status_code == 200, r.text[:300]
