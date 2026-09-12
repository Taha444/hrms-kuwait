# -*- coding: utf-8 -*-
"""الغالُف الداخلي لأربعة — قراُر المالك (2026-09-12).

**والغالُف ليس المستنَد الحكومي**: ``OD-013`` معلٌَن في السجلّ «غلاف متابعة
**داخلي** — النظام ال يُصدر مستنًدا حكومًيا مزيًفا؛ األصُل يُرفع من الجهة».
والنظاُم يُنتجه **فعًلا** لتجديد اإلقامة (``REQRESE`` · ``REQRESN``) بقالب
``HRMS-PR-034`` — فكان غياُبه عن األربعة عدَم اتّساٍق ال حماية.

**وثالٌث منها كانت رايًة، والرابعُة بنية:**

- ``REQWP`` · ``REQPASS`` · ``REQCID``: مسارُ كلٍّ منها يعلن ``OD-013``
  وحده، فالهويُّة محلولة. وُصِلت برفع ``produces_document``.
- **والسفُر ال يُحيل إليه شيء**: ``leave`` يبقى ``WF-001`` ويُرقَّى إلى
  ``WF-002`` بالحمولة، ومرحلُة المندوب شرطيٌة بـ``travel_required``. فمخرُج
  الغالف **مخرُج مرحلٍة ال مخرُج نوع** — وأُعلن في ``STAGE_EXTRA_OUTPUTS``.

**وخطٌر وُقف عنده قبل الوصل**: قوالُب الثالثة كانت تشير إلى مستنداٍت أخرى —
تحديُث الجواز إلى «محضر تحقيق إداري»، وإذُن العمل والبطاقُة إلى «قرار إنذار
/ مخالفة». والقالُب ال يُرسَم منه جسُم المستند، **لكنه يُختَم على األثر**
(``template_code``) — فكان أرشيُف تجديد الجواز سيحمل «محضر تحقيق». وهو عيُن
ما وقع في ``ADMLIC`` وأُصلح بـ«أُزيل التصنيف الخاطئ أوًّلا». فصُوِّبت إلى
``HRMS-PR-034``.

**وما لم يُمَسّ**: اإلذُن نفسه ال يولّده النظام، والمندوُب يرفع المستنَد
الرسمي (``upload_exit_permit``). والفرُق بين الغالف واإلذن هو الفرُق بين
ورقٍة تقول «هذه معاملُتنا ومرجعُها كذا» وورقٍة تقول «هذا إذُن عمل».
"""
from __future__ import annotations

import inspect

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models, v15_registry as R, workflow as W
from app.database import SessionLocal

_TYPES = {rt["code"]: rt for rt in W.DEFAULT_REQUEST_TYPES}


# ---------------------------------------------------------------------------
# الثالثة: رايٌة وهويٌَّة وقالب
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("code", ["REQWP", "REQPASS", "REQCID"])
def test_the_three_produce_the_internal_cover(code):
    """**جوهر القرار**: الثالثُة تُنتج الغالَف كما تُنتجه الإقامة."""
    rt = _TYPES[code]
    assert rt.get("produces_document") is True, code
    od = R.canonical_od_for(code, rt.get("default_template_code"))
    assert od == "OD-013", (code, od)


@pytest.mark.parametrize("code", ["REQWP", "REQPASS", "REQCID"])
def test_the_template_no_longer_points_at_another_document(code):
    """**وقالٌب خاطٌئ يُختَم على األثر وإن لم يُرسَم منه شيء.**

    فكان تحديُث الجواز على «محضر تحقيق إداري»، وإذُن العمل والبطاقُة على
    «قرار إنذار / مخالفة». وهو عيُن ما وقع في ``ADMLIC``.
    """
    tpl = _TYPES[code].get("default_template_code")
    assert R.LEGACY_PRN_ALIASES.get(tpl) == "OD-013", (code, tpl)


def test_they_use_the_same_template_as_residency_renewal():
    """والغالُف واحٌد — فقالبُه واحد، ال نسخٌة لكل نوع."""
    cover = {c: _TYPES[c].get("default_template_code")
             for c in ("REQWP", "REQPASS", "REQCID", "REQRESN", "REQRESE")}
    assert len(set(cover.values())) == 1, cover


def test_the_permit_itself_is_still_not_generated():
    """**واإلذُن نفسه ال يولّده النظام** — والمندوُب يرفع األصل.

    فالقراُر وصَل الغالَف ال اإلذن، والفرُق بينهما هو جوهُر القاعدة 12.
    """
    from app.request_actions import EXECUTION_ACTIONS_BY_STATUS as E

    assert E["awaiting_delegate"]["doc_kind"] == "exit_permit"
    assert E["awaiting_delegate"]["via"] == "upload"
    # **وتُقاس البنيُة لا العبارة**: مطابقُة نٍّص عربّي بالتشكيل عثرت
    # ثالَث مرٍة («لا» مقابل «ال»). فالحقيقُة البنيوية: ما يُولَّد غلاٌف
    # تخطيطُه LAY-07 «أغلفة متابعة حكومية» — لا وثيقُة هويٍّة ولا إذن.
    # ويُقرأ من السجلّ، لا يُعاد كتابتُه هنا.
    cover = R.CANONICAL_DOCUMENTS["OD-013"]
    assert cover["layout"] == "LAY-07", cover
    assert cover.get("legal_note_ar"), "ذهبت الملاحظُة القانونية للغلاف"
    for code in ("REQWP", "REQPASS", "REQCID"):
        tpl = _TYPES[code].get("default_template_code")
        assert R.canonical_od_for(code, tpl) == "OD-013", code


# ---------------------------------------------------------------------------
# والرابعة: مخرُج مرحلٍة ال مخرُج نوع
# ---------------------------------------------------------------------------

def test_travel_maps_to_no_type_of_its_own():
    """**افتراُض القياس**: ال شيَء يُحيل إلى ``WF-002`` بكوده.

    فلو أُضيف نوٌع لها، صار الغالُف مخرَج نوٍع ال مخرَج مرحلة — ويُراجَع
    هذا الملف.
    """
    refs = [k for k, v in R.LEGACY_REQUEST_ALIASES.items()
            if isinstance(v, dict) and v.get("canonical") == "WF-002"]
    assert not refs, refs


def test_the_cover_is_counted_as_the_travel_workflow_output():
    """والغالُف مخرُج ``WF-002`` ال ``WF-001`` — فالمرحلُة شرطيٌة بالسفر."""
    produced = R.produced_outputs()
    assert "OD-013" in (produced.get("WF-002") or set())
    assert "OD-013" not in (produced.get("WF-001") or set()), \
        "حُسِب غالُف السفر مخرًجا لإلجازة العادية"


def test_the_declared_stage_output_is_actually_generated():
    """**وسجٌل يقول «يُنتَج» وال يُنتَج هو العطُل نفسه.**

    فـ``STAGE_EXTRA_OUTPUTS`` تُحتسب في ``produced_outputs`` — فإن لم
    يُولَّد المستنُد في المرحلة صار السجلُّ يكذب.
    """
    src = inspect.getsource(W.enter_stage)
    assert "_generate_stage_output" in src, "المرحلُة ال تولّد مخرَجها"
    helper = inspect.getsource(W._generate_stage_output)
    assert "STAGE_EXTRA_OUTPUTS" in helper, "ال يُقرأ السجلّ"
    assert 'kind="gov_cover"' in helper, \
        "صنٌف مشترٌك مع قرار الإجازة — يُعَدّ أحدُهما تكراًرا للآخر"


def test_the_cover_is_really_generated_at_the_delegate_stage():
    """**وحاٌرس يقرأ الشيفرَة ال يُثبت أن ورقًة وُجدت.**

    كُتب هذا الملُّف أوًّلا بحارٍس يقيس أن ``enter_stage`` **تنادي**
    المولِّد — ومرَّ أخضَر وال مستنَد يُولَّد. فالنداُء كان يفشل ويُسجَّل في
    السجلّ بثالث عّلٍل متعاقبة:

    1. التحقُّق من الهويّة يقرأ ``WF-001`` وحده، والغالُف مخرُج
       ``WF-002`` المُرقَّى.
    2. ``actor=None`` و``uploaded_by`` يقرأ ``actor.id``.
    3. وعمُد المعتمِد ``approver_user_id`` ال ``decided_by``.

    **فيُقاس األثر**: صٌّف مستنٍد بصنفه وهويّته وحالته وملٍّف على التخزين
    ومن يُنسَب إليه.
    """
    db = SessionLocal()
    rid = None
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1))
        hr = db.scalar(select(models.User).where(
            models.User.role == "hr", models.User.company_id == 1))
        rt = W.get_request_type(db, 1, "leave")
        if rt is None or emp is None or hr is None:
            pytest.skip("ال بياناِت أساٍس في هذه القاعدة")

        chain = W._chain(rt, type("P", (), {"payload_json": {"travel_required": True}})())
        stage_idx = next(i for i, st in enumerate(chain)
                         if st.get("kind") == "delegate_exit")

        req = models.Request(
            company_id=1, employee_id=emp.id, request_type_code="leave",
            status="pending", current_stage=stage_idx,
            payload_json={"travel_required": True,
                          "start_date": "2031-06-01", "end_date": "2031-06-10"})
        db.add(req)
        db.flush()
        rid = req.id
        db.add(models.RequestApproval(
            request_id=rid, stage_order=stage_idx - 1, stage_label="الشؤون",
            approver_role="hr", approver_user_id=hr.id, decision="approved"))
        db.flush()

        W.enter_stage(db, req, rt)
        db.commit()

        docs = db.scalars(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid)).all()
        covers = [d for d in docs if d.kind == "gov_cover"]
        assert covers, ("لم يُولَّد غلاُف المتابعة — والسجلُّ يحتسبه: "
                        f"{[(d.kind, d.od_code) for d in docs]}")
        cover = covers[0]
        assert cover.od_code == "OD-013", cover.od_code
        assert cover.lifecycle_status == "GENERATED", cover.lifecycle_status
        assert cover.file_path, "سجٌّل بال ملّف — ورقٌة لا تُطبَع"
        assert cover.uploaded_by == hr.id, (cover.uploaded_by, hr.id)
    finally:
        if rid:
            for tbl in (models.RequestDocument, models.RequestApproval):
                db.execute(sa_delete(tbl).where(tbl.request_id == rid))
            db.execute(sa_delete(models.Task).where(
                models.Task.related_entity_type == "request",
                models.Task.related_entity_id == rid))
            db.execute(sa_delete(models.Request).where(models.Request.id == rid))
            db.commit()
        db.close()


def test_a_cover_is_never_attributed_to_nobody():
    """**وورقٌة تُنسَب إلى مجهول أسوأ من ورقٍة تتأخّر.**

    فبال فاعٍل يُنسَب إليه ال يُولَّد المستند، ويُسجَّل السبب.
    """
    helper = inspect.getsource(W._generate_stage_output)
    assert "actor_user_id()" in helper, "ال يُقرأ الفاعُل من سياق التدقيق"
    assert "approver_user_id" in helper, "ال يُقرأ آخُر معتمِد"
    assert "return" in helper.split("بال فاعٍل")[-1][:200] or            "لم يُولَّد" in helper, "يُولَّد بال فاعل"


def test_the_identity_override_cannot_invent_a_class():
    """**والتجاوُز مقيٌَّد بما يعلنه المسار** — وإال عاد ما أُصلح في P1-02."""
    db = SessionLocal()
    rid = None
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1))
        rt = W.get_request_type(db, 1, "leave")
        if rt is None:
            pytest.skip("ال نوَع إجازٍة في هذه القاعدة")
        req = models.Request(company_id=1, employee_id=emp.id,
                             request_type_code="leave", status="pending",
                             payload_json={"travel_required": True})
        db.add(req)
        db.flush()
        rid = req.id
        with pytest.raises(ValueError):
            W.generate_document(db, req, rt, kind="gov_cover",
                                actor=None, od_override="OD-099")
        db.rollback()
    finally:
        if rid:
            db2 = SessionLocal()
            try:
                db2.execute(sa_delete(models.RequestDocument).where(
                    models.RequestDocument.request_id == rid))
                db2.execute(sa_delete(models.Request).where(
                    models.Request.id == rid))
                db2.commit()
            finally:
                db2.close()
        db.close()


def _delegate_stage_request(db):
    """طلُب إجازِة سفٍر واقٌف عند مرحلة المندوب — سّقالُة القياس السلوكي.

    وتُعيد ``(req, rt, hr)`` أو ``None`` إن لم تكن بيانات األساس موجودة.
    """
    emp = db.scalar(select(models.Employee).where(models.Employee.company_id == 1))
    hr = db.scalar(select(models.User).where(
        models.User.role == "hr", models.User.company_id == 1))
    rt = W.get_request_type(db, 1, "leave")
    if rt is None or emp is None or hr is None:
        return None
    chain = W._chain(rt, type("P", (), {"payload_json": {"travel_required": True}})())
    stage_idx = next(i for i, st in enumerate(chain)
                     if st.get("kind") == "delegate_exit")
    req = models.Request(
        company_id=1, employee_id=emp.id, request_type_code="leave",
        status="pending", current_stage=stage_idx,
        payload_json={"travel_required": True,
                      "start_date": "2031-06-01", "end_date": "2031-06-10"})
    db.add(req)
    db.flush()
    db.add(models.RequestApproval(
        request_id=req.id, stage_order=stage_idx - 1, stage_label="الشؤون",
        approver_role="hr", approver_user_id=hr.id, decision="approved"))
    db.flush()
    return req, rt, hr


def _scrub(db, rid: int) -> None:
    for tbl in (models.RequestDocument, models.RequestApproval):
        db.execute(sa_delete(tbl).where(tbl.request_id == rid))
    db.execute(sa_delete(models.Task).where(
        models.Task.related_entity_type == "request",
        models.Task.related_entity_id == rid))
    db.execute(sa_delete(models.Request).where(models.Request.id == rid))
    db.commit()


def test_a_failing_cover_does_not_stop_the_departure(caplog):
    """**وورقٌة تتعّطل ال تحبس موظًفا في البلد.**

    الغالُف أثٌر إداري، ومرحلُة المندوب فعٌل قائم بنفسه. فلو انفجر التوليُد
    داخل معاملٍة واحدة سقط انتقاُل الطلب معه — واإلجازُة تُعلَّق بسبب ورقة.

    **وهذا يُقاس بإسقاط المولِّد ال بقراءة ``except``**: الحارُس كان يبحث
    عن ``logger.warning`` ويؤكّد غياَب ``raise`` — ونصٌّ كهذا يبقى صحيًحا
    وال شيَء يُمسَك (ولو غاب ``logger`` من الوحدة انفجر الفرُع نفسه
    بـ``NameError`` — وقد غاب فعًال وأُضيف).
    """
    import logging

    db = SessionLocal()
    rid = None
    try:
        got = _delegate_stage_request(db)
        if got is None:
            pytest.skip("ال بياناِت أساٍس في هذه القاعدة")
        req, rt, _hr = got
        rid = req.id

        original = W._gov_cover_lines

        def _explode(*a, **k):
            raise RuntimeError("تعّطل رسُم الغالف — مقصوٌد في القياس")

        W._gov_cover_lines = _explode
        try:
            with caplog.at_level(logging.WARNING):
                W.enter_stage(db, req, rt)   # ال يرفع
            db.commit()
        finally:
            W._gov_cover_lines = original

        # **والخروُج مضى**: الحالُة انتقلت ومهمُّة المندوب أُنشئت.
        assert req.status == "awaiting_delegate", req.status
        tasks = db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid)).all()
        assert tasks, "مهمُّة المندوب لم تُنشأ — فشُل الغالف أوقف المرحلة"

        # **وال يُسجَّل نجاُح توليٍد لم يقع.** والصفُّ يبقى بقصٍد مكتوٍب في
        # ``generate_document``: «القراُر قراٌر والمستنُد مستند» — فيُقيَّد
        # ``FAILED`` بال ملٍّف وبسببه، ليُعاد توليده. وهذا ما يُقاس: ال
        # غياُب الصّف، بل **أن الصفَّ ال يكذب**.
        covers = db.scalars(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid,
            models.RequestDocument.kind == "gov_cover")).all()
        assert len(covers) == 1, covers
        cover = covers[0]
        assert cover.lifecycle_status == "FAILED", cover.lifecycle_status
        assert not cover.file_path, "صٌّف فاشٌل يشير إلى ملّف"
        assert (cover.reference_no or "").startswith("FAILED-"), cover.reference_no

        # **ومهمٌَّة تُخرِج من الفشل** — وإال بقيت ورقٌة ناقصٌة ال أحَد يعلمها.
        fail_tasks = [t for t in tasks if t.type == "document"]
        assert fail_tasks, ("ال مهمَّة إعادِة توليد — الفشُل مقيٌَّد وال أحَد "
                            f"مسؤوٌل عنه: {[(t.type, t.title) for t in tasks]}")
        assert any(t.severity == "critical" for t in fail_tasks), \
            [t.severity for t in fail_tasks]

        # **والفشُل ال يُدفَن**: أثٌر في السجّل يذكر الطلب.
        assert any(str(rid) in r.getMessage()
                   for r in caplog.records if r.levelno >= logging.WARNING), \
            f"فشٌل صامت: {[r.getMessage() for r in caplog.records]}"
    finally:
        if rid:
            _scrub(db, rid)
        db.close()


def test_two_failures_of_the_same_kind_can_both_be_recorded():
    """**والمعالُِج ال يفشل بما يعالجه.**

    ``reference_no`` **فريٌد على الجدول كلّه**، وكان الفشُل يكتب فيه
    ``FAILED-{النوع}`` — ثابًتا. فثاني مستنٍد يفشل بنوع االستثناء نفسه (أيَّ
    شركٍة، أيَّ طلب) يرفع ``IntegrityError`` داخل ``except`` نفسه، فتسقط
    المعاملُة ومعها **قراُر االعتماد** — وهو العطُل الذي كُتب المعالُِج
    ليمنعه.

    **ولم يظهر منفرًدا.** الملُّف كان أخضَر وحده وأحمَر في السويت: مستنٌد
    فاشٌل واحٌد ال يتصادم مع نفسه. فيُقاس بفشلين صريحين.
    """
    db = SessionLocal()
    made = []
    try:
        got = _delegate_stage_request(db)
        if got is None:
            pytest.skip("ال بياناِت أساٍس في هذه القاعدة")
        req, rt, hr = got
        made.append(req.id)

        got2 = _delegate_stage_request(db)
        req2 = got2[0]
        made.append(req2.id)

        original = W._gov_cover_lines

        def _explode(*a, **k):
            raise RuntimeError("تعّطل رسُم الغالف — مقصوٌد في القياس")

        W._gov_cover_lines = _explode
        try:
            W.enter_stage(db, req, rt)
            W.enter_stage(db, req2, rt)
            db.commit()          # **ال تسقط المعاملُة بتصادم مرجٍع**
        finally:
            W._gov_cover_lines = original

        rows = db.scalars(select(models.RequestDocument).where(
            models.RequestDocument.request_id.in_(made),
            models.RequestDocument.kind == "gov_cover")).all()
        assert len(rows) == 2, rows
        refs = {r.reference_no for r in rows}
        assert len(refs) == 2, f"مرجٌع واحٌد لفشلين: {refs}"
        for r in rows:
            assert r.lifecycle_status == "FAILED", r.lifecycle_status
            # **وطوُل العمود ``String(40)``** — وPostgres يرفض الأطول.
            assert len(r.reference_no) <= 40, (len(r.reference_no), r.reference_no)
            assert "RuntimeError" in r.reference_no, r.reference_no
    finally:
        for rid in made:
            _scrub(db, rid)
        db.close()


def test_the_success_reference_cannot_collide_between_kinds():
    """ومرجُع النجاح يقطع الصنَف على ستٍّ — فصنفان يتفقان فيها يتصادمان.

    ``REQ-{req:06d}-{KIND[:6]}-v{version}`` — و``gov_cover`` و
    ``generated_pdf`` و``exit_permit`` تفترق في السّت. فيُحرَس أنها تبقى
    كذلك، وإال فشل توليُد المستند الثاني للطلب نفسه بتصادم مرجع.
    """
    kinds = ["generated_pdf", "gov_cover", "exit_permit", "uploaded",
             "signed_scan", "attachment"]
    prefixes = [k.upper()[:6] for k in kinds]
    dupes = {p for p in prefixes if prefixes.count(p) > 1}
    assert not dupes, f"أصناٌف تتفق في ستّة أحرف: {dupes}"


# ---------------------------------------------------------------------------
# وجسُم الغلاف — يُقاس بأسطره لا بشيفرته
# ---------------------------------------------------------------------------

def test_the_cover_has_its_own_body_not_the_leave_decision_s():
    """**ومستندان بجسٍم واحد يقرأ أحدُهما كأنه اآلخر.**

    الغالُف كان يُرسَم بأسطر قرار اإلجازة — نوُعها وتاريخاها وسببُها —
    فيبدو قراَر إجازٍة بترويسٍة أخرى. والسجلُّ يشترط للغالف
    ``transaction_type`` و``reference_no``.

    **ويُقاس باألسطر المولَّدة ال بوجود اسم الدالة في الشيفرة.**
    """
    db = SessionLocal()
    rid = None
    try:
        got = _delegate_stage_request(db)
        if got is None:
            pytest.skip("ال بياناِت أساٍس في هذه القاعدة")
        req, rt, _hr = got
        rid = req.id
        emp = db.get(models.Employee, req.employee_id)

        cover = W._gov_cover_lines(db, rt, req, emp)
        body = W._body_lines(rt, req, emp)
        blob, leave_blob = "\n".join(cover), "\n".join(body)

        assert any("نوع المعاملة" in ln for ln in cover), cover
        assert any(f"طلب رقم {rid}" in ln for ln in cover), cover
        # **وجسمان ال يتقاسمان سطًرا واحًدا.**
        assert not (set(cover) & set(body)), set(cover) & set(body)
        # وتاريُخ اإلجازة وسببُها ليسا من شأن الغالف.
        assert "2031-06-01" in leave_blob and "2031-06-01" not in blob, blob
    finally:
        if rid:
            _scrub(db, rid)
        db.close()


def test_the_cover_names_the_authority_from_the_declared_vocabulary():
    """**والبحُث الذي ال يُصيب أسوأ من غيابه** — لأنه يبدو موصوًال.

    الغالُف كان يطابق ``category == rt.code``، و``create_portal`` يرفض كلَّ
    فئٍة خارج ``CATEGORY_LABELS`` («فئة غير معروفة») والشاشُة ال تعرض
    غيرها. فال سبيَل — بالشاشة ولا بالـAPI — لصٍّف فئتُه ``REQWP``: سطُر
    الجهة كان يُسقَط دائمًا، والحقُل الذي يشترطه السجلّ ال يُملأ أبدًا.

    **ويُقاس بأسطر أنواٍع حقيقية** ال بقراءة الخريطة.
    """
    from app.routers.portals import CATEGORY_LABELS

    db = SessionLocal()
    rid = None
    try:
        got = _delegate_stage_request(db)
        if got is None:
            pytest.skip("ال بياناِت أساٍس في هذه القاعدة")
        req, _rt, _hr = got
        rid = req.id
        emp = db.get(models.Employee, req.employee_id)

        checked = 0
        for code, cat in R.GOV_COVER_CATEGORY.items():
            rt = W.get_request_type(db, 1, code)
            if rt is None:
                continue
            lines = W._gov_cover_lines(db, rt, req, emp)
            want = CATEGORY_LABELS[cat]
            assert any(f"الجهة الحكومية: {want}" in ln for ln in lines), (code, lines)
            checked += 1
        assert checked, "ال نوَع من الخريطة موجوٌد في الكتالوج — القياُس لم يقع"
    finally:
        if rid:
            _scrub(db, rid)
        db.close()


def test_every_mapped_category_exists_in_the_portals_vocabulary():
    """وفئٌة ال يعرفها المعجُم تُسقِط السطَر صامتًة — فتُحرَس الخريطُة نفسها."""
    from app.routers.portals import CATEGORY_LABELS

    stray = {c: cat for c, cat in R.GOV_COVER_CATEGORY.items()
             if cat not in CATEGORY_LABELS}
    assert not stray, f"فئاٌت ال يعرفها معجُم البوابات: {stray}"


def test_an_unmapped_type_says_nothing_instead_of_guessing():
    """**وما ال أقطع به ال يُسمّى** — ``leave`` و``REQPASS`` بال سطر جهة.

    جواُز الوافد يصدر من سفارة بلده، وإذُن المغادرة بين الداخلية والقوى
    العاملة. وورقٌة تُقدَّم وعليها اسُم جهٍة خاطئة تُردّ وتُقرأ استخفاًفا.
    """
    db = SessionLocal()
    rid = None
    try:
        got = _delegate_stage_request(db)
        if got is None:
            pytest.skip("ال بياناِت أساٍس في هذه القاعدة")
        req, rt_leave, _hr = got
        rid = req.id
        emp = db.get(models.Employee, req.employee_id)

        for code in ("leave", "REQPASS"):
            assert code not in R.GOV_COVER_CATEGORY, \
                f"{code} صار مخّططًا — فيُنقَل إلى الحارس الذي يؤكّد التسمية"
            rt = rt_leave if code == "leave" else W.get_request_type(db, 1, code)
            if rt is None:
                continue
            lines = W._gov_cover_lines(db, rt, req, emp)
            assert not any("الجهة الحكومية" in ln for ln in lines), (code, lines)
            # **والغالُف يبقى يقول من أين يأتي األصل.**
            assert any("متابع" in ln and "داخلي" in ln for ln in lines), lines
            assert any("المختص" in ln for ln in lines), lines
    finally:
        if rid:
            _scrub(db, rid)
        db.close()




def test_the_declared_required_fields_are_not_silently_unmet():
    """**وشرٌط معلٌَن ال يُفرَض في أيّ موضع** — فيُقال ال يُطوى.

    ``CANONICAL_DOCUMENTS[od]["required"]`` قائمٌة معلَنة لكل مستند، **وال
    يقرؤها شيء**. وللغالف أربعة: اسُم الموظف (في شبكة الترويسة)، ونوُع
    المعاملة والمرجُع (في جسمه)، و``government_entity`` — **وهذا بال
    مصدٍر حتى يُملأ سجلُّ الجهات**.

    فهذا الحارس يُثبِّت الحالَة المقيسة: ثالثٌة تُوفى وواحٌد ينتظر بياًنا
    يملؤه صاحبُه. فإن صار الشرُط مفروًضا في الشيفرة سقط معلًنا أن هذه
    الوثيقَة تُحدَّث.
    """
    import pathlib

    required = set(R.CANONICAL_DOCUMENTS["OD-013"]["required"])
    assert required == {"employee_name", "transaction_type",
                        "government_entity", "reference_no"}, required

    app = pathlib.Path(__file__).resolve().parents[1] / "app"
    enforcers = [p.name for p in app.rglob("*.py")
                 if 'CANONICAL_DOCUMENTS' in p.read_text(encoding="utf-8")
                 and '["required"]' in p.read_text(encoding="utf-8")]
    assert not enforcers, (
        "صار الشرُط مفروًضا — تُحدَّث هذه الوثيقة وتُراجَع حقوُل الغلاف: "
        f"{enforcers}")
