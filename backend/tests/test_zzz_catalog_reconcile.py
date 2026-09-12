# -*- coding: utf-8 -*-
"""الكتالوُج في موضعين، والذي يعمل هو القاعدة — ال الشيفرة.

**أخطُر ما وُجد في هذه الجولة.** ``ensure_default_catalog`` كانت **تُدرِج
الناقَص وال تُحدِّث القائم**::

    if rt["code"] in existing_rt:
        continue

فكلُّ تغييٍر في ``DEFAULT_REQUEST_TYPES`` بعد أوّل نشرٍة **ال يبلغ النظاَم
العامل**: الشيفرُة تُعلن أن نوًعا يُنتج مستنًدا، و``get_request_type`` تقرأ
صَّف القاعدة الذي يقول غير ذلك. وقيس على قاعدٍة حقيقية: **خمسٌة وثالثون
نوًعا** غيُر متزامن — منها ما وُصِل في دفعاٍت سابقة (``advance`` و``loan``
و``REQPER`` و``REQATT`` و``REQOT``) فبقي صامًتا.

**ولم يُمسَك ألن الاختبار يبذر من جديد**: ``conftest`` ينفّذ
``Base.metadata.drop_all`` ثم ``seed.run()`` — فيعمل على كتالوٍج طازٍج
دائًما. «أخضٌر في الاختبار وصامٌت في الإنتاج»، وهو الصنُف نفسه الذي كُنس
في هذه الجولة (ترويسٌة ال تُكشَف، وساعُة مضيف).

**فيُقاس اآلليُة ال الحالة**: صٌّف يُفسَد بيًدا، ثم تُشغَّل المصالحة،
ويُقاس أنه عاد. فحاٌرس يقيس حالًة على قاعدٍة طازجٍة يمرّ دائًما وال يحرس
شيًئا.

**والمزامنُة آمنٌة بالقياس**: ال مساَر ``PUT``/``PATCH`` لأنواع الطلبات في
النظام كلّه، فالصفوُف العامّة نسخٌة من الكتالوج ال عمٌل بشرّي.

**وسلسلُة الاعتماد تُستثنى بشرط**: ``Request.current_stage`` فهٌرس فيها،
فتغييُر طولها يُزيح معنى المراحل على طلٍب جاٍر.
"""
from __future__ import annotations

import inspect

from sqlalchemy import select

from app import models
from app.catalog_seed import ensure_default_catalog
from app.database import SessionLocal


def test_reconciliation_restores_a_drifted_row():
    """**جوهر البند**: صٌّف يخالف الكتالوَج يُصالَح ال يُترَك."""
    db = SessionLocal()
    try:
        row = db.scalar(select(models.RequestType).where(
            models.RequestType.code == "REQPASS",
            models.RequestType.company_id.is_(None)))
        assert row is not None, "ال نوَع REQPASS في القاعدة"
        was_produces = row.produces_document
        was_tpl = row.default_template_code

        # نُفسده كما تفسده نشرٌة قديمة
        row.produces_document = False
        row.default_template_code = "HRMS-PR-024"
        db.commit()

        report = ensure_default_catalog(db)
        db.expire_all()
        row = db.scalar(select(models.RequestType).where(
            models.RequestType.code == "REQPASS",
            models.RequestType.company_id.is_(None)))

        assert row.produces_document is True, "لم تُصالَح الرايُة"
        assert row.default_template_code == "HRMS-PR-034", \
            f"لم يُصالَح القالُب: {row.default_template_code}"
        assert report["request_types_updated"] >= 1, report
        assert any(d.startswith("REQPASS:") for d in
                   report["request_types_updated_detail"]), report
        assert was_produces is True and was_tpl == "HRMS-PR-034", \
            "افتراُض القياس: الصفُّ كان مصالًحا قبل اإلفساد"
    finally:
        db.close()


def test_reconciliation_is_idempotent():
    """ومصالحٌة تُبلِّغ عن تغييٍر كلَّ مرة ال يُصدَّق تقريرُها."""
    db = SessionLocal()
    try:
        ensure_default_catalog(db)
        second = ensure_default_catalog(db)
        assert second["request_types_updated"] == 0, \
            second["request_types_updated_detail"]
    finally:
        db.close()


def test_the_approval_chain_is_not_shifted_under_a_live_request():
    """**وسلسلٌة تُغيَّر تحت طلٍب جاٍر تُزيح معنى مراحله.**

    ``current_stage`` فهٌرس في السلسلة: فلو قُصِّرت أو طُوِّلت، صارت
    المرحلُة الثالثُة غيَر التي قُرِّرت. فتُؤجَّل حين يوجد طلٌب جاٍر ويختلف
    الطول، ويُقال ذلك في التقرير.
    """
    src = inspect.getsource(ensure_default_catalog)
    assert "in_flight" in src, "ال يُفحَص وجوُد طلٍب جاٍر"
    assert "same_length" in src, "ال يُقاس فرُق الطول"
    assert "chain_deferred" in src, "التأجيُل ال يُقال"


def test_the_report_names_what_changed():
    """**ومصالحٌة ال يُعرَف أنها وقعت ال تُصدَّق** — فتُسمّى بما تغيّر."""
    db = SessionLocal()
    try:
        report = ensure_default_catalog(db)
    finally:
        db.close()
    for key in ("request_types_updated", "request_types_updated_detail",
                "approval_chains_deferred"):
        assert key in report, key


def test_the_reason_it_was_missed_is_recorded():
    """**والعلُّة تُكتَب حيث يُقرأ الملف**: الاختباُر يبذر من جديد.

    فمن ال يعرف ذلك يظنّ أن السويَت الخضراء تُثبت أن الإنتاج مصالَح.
    """
    src = inspect.getsource(ensure_default_catalog)
    assert "conftest" in src or "يبذر من جديد" in src, \
        "ال يُقال لماذا لم يُمسَك هذا"


def test_the_deploy_log_says_what_was_reconciled():
    """**ومصالحٌة تقع صامتًة ال يُعرَف أنها وقعت.**

    ``bootstrap`` يُشغِّل المصالحَة في كل نشرة (``python -m app.bootstrap``
    في أمر التشغيل). وكانت طباعتُه مشروطًة بـ«المُضاف» وحده — **فأوُل
    نشرٍة بعد المصالحة أضافت صفًرا وصالحت خمسًة وثالثين نوًعا، ولم يقل
    سجلُّ النشر شيًئا**. ومن يقرأ السجل يستنتج أن شيًئا لم يقع.
    """
    import inspect

    import app.bootstrap as B

    src = inspect.getsource(B._ensure_catalog)
    assert "request_types_updated" in src, "المُصالَح ال يُطبَع"
    assert "approval_chains_deferred" in src, "المؤجَّل ال يُطبَع"
    # وال تبقى الطباعُة مشروطًة بالمُضاف وحده.
    assert src.count("print(") >= 3, src[-400:]


# ---------------------------------------------------------------------------
# وثالثُة كتالوجات، ولكلٍّ منطقُه بحسب قابليّته للتحرير
# ---------------------------------------------------------------------------

def test_a_missing_notification_template_is_inserted():
    """**وقالٌب ناقٌص = إشعاٌر ال يصل، بال خطٍأ يُرى.**

    ``notify_from_template`` تُسقِط بصمت ما ال قالَب له (تُسجِّل تحذيًرا
    وتُعيد ``None``)، وشرحُها يقول: «الصمت هنا هو ما أخفى العطل… فكانت كل
    اإلشعارات المبنية على قوالب تختفي بال أثر».

    وقوالُب اإلشعارات تُبذَر في ``seed.py`` **المحظور في اإلنتاج** — فكلُّ
    قالٍب يُضاف بعد أوّل نشرٍة ال يدخل القاعدَة. وقيس: ``NTF-075`` (إشعاُر
    اتفاقية القرض المبنّي في هذه الجولة) **لم يكن فيها**.
    """
    from app.notification_templates import DEFAULT_NOTIFICATION_TEMPLATES as NT

    db = SessionLocal()
    try:
        row = db.scalar(select(models.NotificationTemplate).where(
            models.NotificationTemplate.code == "NTF-075"))
        assert row is not None, "NTF-075 غائٌب — إشعاُر القرض ال يصل"
        db.delete(row)
        db.commit()

        report = ensure_default_catalog(db)
        assert report["notification_templates_added"] >= 1, report
        back = db.scalar(select(models.NotificationTemplate).where(
            models.NotificationTemplate.code == "NTF-075"))
        assert back is not None, "لم يُعَد إدخالُه"
        spec = next(t for t in NT if t["code"] == "NTF-075")
        assert back.body_text == spec["body_text"]
    finally:
        db.close()


def test_notification_templates_are_reconciled_because_they_are_not_editable():
    """**واملزامنُة تتبع قابليَة التحرير ال الرغبة.**

    ال مساَر كتابٍة لقوالب اإلشعارات (قراءٌة فقط) — فالصفوُف نسخٌة من
    الشيفرة، ومصالحُتها ال تطمس عمَل أحد.
    """
    import pathlib

    router = (pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"
              / "notification_settings.py").read_text(encoding="utf-8")
    for verb in ("@router.put", "@router.patch"):
        assert f'{verb}("/templates' not in router, \
            "صار القالُب يُحرَّر — تُراجَع املزامنة"

    src = inspect.getsource(ensure_default_catalog)
    assert "NotificationTemplate" in src, "ال تُصالَح قوالُب اإلشعارات"


def test_document_templates_are_named_never_overwritten():
    """**وقالٌب يُحرَّر ال يُكتَب فوقه.**

    ``PUT /templates/{id}`` موجوٌد ويحفظ النسخَة السابقة في سجلّ
    إصدارات — فالتحريُر متوقٌَّع، ومزامنٌة صامتة **تطمس عمَل اإلدارة**.

    لكنّ الفرَق ال يُطوى: قيس خمسُة قوالب ``body_html`` تخالف الشيفرة
    (PR-001 · PR-006 · PR-008 · PR-009 · PR-032) — صُحِّحت في الشيفرة ولم
    يبلغ تصحيحُها القاعدة. فتُسمّى ليُطبِّقها صاحُبها، فيبقى سجلُّ
    اإلصدارات صادًقا.
    """
    src = inspect.getsource(ensure_default_catalog)
    assert "document_templates_drifted" in src, "الفرُق ال يُقال"
    # وال تُكتَب فوقها: ال إسناَد body_html في املصالحة.
    assert "row.body_html =" not in src and ".body_html = body" not in src, \
        "املصالحُة تكتب فوق قالٍب يُحرَّر"

    import pathlib

    router = (pathlib.Path(__file__).resolve().parents[1] / "app" / "routers"
              / "templates.py").read_text(encoding="utf-8")
    assert "@router.put" in router, "افتراُض القياس: القالُب يُحرَّر"
    assert "DocumentTemplateVersion" in router, "ال سجلَّ إصدارات"


def test_the_loan_agreement_notice_actually_reaches_the_employee():
    """**وإشعاٌر بُني وُحرِس واختُبر كان ال يصل أحًدا في اإلنتاج.**

    ``NTF-075`` غاب من القاعدة، و``notify_from_template`` تُسقِط بصمٍت ما
    ال قالَب له. فالحرّاُس السابقة كانت تقيس **أن الوصَل مكتوٌب** —
    ويُقاس هنا **أن الرسالَة تصل**: صُّف مهمٍة بقالبه ونصّه ومستقبِله.
    """
    from sqlalchemy import delete as sa_delete

    from app import workflow as W

    db = SessionLocal()
    rid = None
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1))
        if emp is None:
            import pytest
            pytest.skip("ال موظَف في هذه القاعدة")
        req = models.Request(
            company_id=1, employee_id=emp.id, request_type_code="loan",
            status="pending",
            payload_json={"loan_type": "قرض", "amount": 600, "months": 6,
                          "first_deduction_month": "2031-07", "reason": "قياس"})
        db.add(req)
        db.flush()
        rid = req.id

        ok, note = W._apply_loan(db, req)
        db.commit()
        assert ok, note

        tasks = db.scalars(select(models.Task).where(
            models.Task.dedup_key == f"loan_agreement:{rid}")).all()
        assert tasks, "األثُر وقع واإلشعاُر لم يصل — القالُب مفقود"
        assert all(t.template_code == "NTF-075" for t in tasks), \
            [t.template_code for t in tasks]
        # **ولا تُطابَق عربيٌة في حارس** — رابُع عثرٍة لي في ذلك
        # («شؤون» بلا «ال»). فيُقاس المستقبُِل: حساُب الموظف نفسه.
        emp_user = db.scalar(select(models.User).where(
            models.User.employee_id == emp.id))
        assert emp_user is not None, "لا حساَب للموظف"
        assert {t.assignee_user_id for t in tasks} == {emp_user.id}, (
            [(t.assignee_user_id, emp_user.id) for t in tasks])
        assert all((t.detail or "").strip() for t in tasks), "نٌّص فارغ"
    finally:
        if rid:
            db.execute(sa_delete(models.Task).where(
                models.Task.dedup_key == f"loan_agreement:{rid}"))
            db.execute(sa_delete(models.Deduction).where(
                models.Deduction.request_id == rid))
            db.execute(sa_delete(models.AuditLog).where(
                models.AuditLog.entity_type == "request",
                models.AuditLog.entity_id == rid))
            db.execute(sa_delete(models.Request).where(models.Request.id == rid))
            db.commit()
        db.close()


def test_every_template_the_code_sends_exists_in_the_database():
    """**والقاعدُة العامّة ال الحالُة الواحدة**: كلُّ قالٍب يُنادى بكوده في
    الشيفرة ال بدّ أن يكون في القاعدة — وإال سقط اإلشعاُر بصمت.

    فـ``NTF-075`` لم يكن وحَده مرشًَّحا؛ **أيُّ قالٍب يُضاف غًدا** يقع في
    الحفرة نفسها ما لم تُصالِحه المزامنة.
    """
    import pathlib
    import re

    app = pathlib.Path(__file__).resolve().parents[1] / "app"
    called = set()
    for p in app.rglob("*.py"):
        if p.name == "notification_templates.py":
            continue
        called |= set(re.findall(r'code="(NTF-\d+)"', p.read_text(encoding="utf-8")))

    db = SessionLocal()
    try:
        have = {r for r in db.scalars(
            select(models.NotificationTemplate.code)).all()}
    finally:
        db.close()
    missing = sorted(called - have)
    assert not missing, f"قوالٌب تُنادى في الشيفرة وال وجوَد لها في القاعدة: {missing}"
