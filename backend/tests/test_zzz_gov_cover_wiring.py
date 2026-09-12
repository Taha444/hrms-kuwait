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


def test_a_failing_cover_does_not_stop_the_departure():
    """**ومستنٌد مساعٌد يُسقِط مرحلًة حكومية عطٌل أسوأ من غيابه.**

    فالمندوُب يمضي بالمعاملة، والفشُل يُسجَّل ليراه من يُصلحه.
    """
    helper = inspect.getsource(W._generate_stage_output)
    assert "logger.warning" in helper, "الفشُل صامت"
    assert "raise" not in helper.split("except")[-1], \
        "فشُل الغلاف يُسقِط المرحلة"
    assert hasattr(W, "logger"), "ال سجّل في الوحدة — الفرُع ينفجر بـNameError"


# ---------------------------------------------------------------------------
# ومستندان بجسٍم واحد يقرأ أحدُهما كأنه اآلخر
# ---------------------------------------------------------------------------

def test_the_cover_has_its_own_body_not_the_leave_decision_s():
    """**جوهر عطٍل أحدثتُه ثم أصلحتُه.**

    الغالُف كان يُرسَم بأسطر ``_body_lines`` نفسها — نوُع اإلجازة وتاريخاها
    وسببُها — فيبدو **قراَر إجازٍة بترويسة غلاف**. والسجلُّ يشترط له غير
    ذلك: نوَع المعاملة والجهَة والمرجع.

    فيُقاس أن الجسَم يتبع **هويَّة المستند** ال نوَع الطلب وحده.
    """
    src = inspect.getsource(W.generate_document)
    assert "_gov_cover_lines" in src, "الغالُف يُرسَم بجسم قرار اإلجازة"
    assert 'od_code == "OD-013"' in src, "الجسُم ال يتبع الهويّة"

    cover = inspect.getsource(W._gov_cover_lines)
    assert "نوع المعاملة" in cover and "المرجع الداخلي" in cover


def test_the_cover_never_invents_a_government_entity():
    """**وغالٌف ال يسمّي الجهَة أهوُن من غالٍف يسمّي جهًة خاطئة.**

    فورقٌة تُقدَّم إلى الهيئة وعليها اسُم وزارٍة أخرى تُردّ وتُقرأ
    استخفاًفا. و``GovernmentPortal`` موجوٌد في النظام — يُقرأ منه إن مُلئ
    ويُسكَت عنه إن لم يُملأ، **وال يُكتَب اسٌم في الشيفرة**.
    """
    cover = inspect.getsource(W._gov_cover_lines)
    assert "GovernmentPortal" in cover, "ال يُقرأ سجلُّ الجهات"
    for invented in ("الهيئة العامة للقوى العاملة", "المعلومات المدنية",
                     "الجنسية والجوازات", "وزارة الداخلية"):
        assert invented not in cover, f"اسُم جهٍة مكتوٌب في الشيفرة: {invented}"


def test_the_cover_says_the_original_comes_from_the_authority():
    """**والورقُة تقول ما هي** — فال تُقرأ بديًلا عن األصل.

    وهي عيُن الملاحظة القانونية في السجلّ: «األصُل يُرفع من الجهة».
    """
    cover = inspect.getsource(W._gov_cover_lines)
    assert "غلاُف متابعٍة داخلي" in cover or "غلاف متابعة داخلي" in cover
    assert "الأصُل" in cover or "الأصل" in cover


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
