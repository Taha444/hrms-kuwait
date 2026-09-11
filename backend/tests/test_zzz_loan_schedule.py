# -*- coding: utf-8 -*-
"""قرٌض يُعتمد ولا يُستقطَع — وثلاثُة حقوٍل تُجمَع ولا تُقرأ.

**العطل المقيس**: نموذج ``REQADV`` يجمع ``amount`` و``months`` و
``first_deduction_month`` — **ولا سطَر في النظام يقرأ واحًدا منها**. فيُعتمد
القرض بمرحلتين (المدير ثم المحاسب) ويُغلَق «مكتمًلا»، ولا جدوَل سداٍد ولا
استقطاع. والموظف يأخذ المال والشركة لا تسترّده — أو تسترّده بورقٍة خارج
النظام لا أثر لها فيه.

وهو النمط نفسه الذي تكرّر في هذه الجولة: حقٌل يُجمَع ولا يُقرأ. لكنه هنا
على **المال**، والسؤال لا يظهر إلا بعد شهور: أين ذهب القرض؟

**ولا جدوٌل ثاٍن للمال**: القسط يُكتب صفَّ خصٍم كبقية الخصومات، فتقرؤه
الرواتب بالآلية نفسها المقيسة في ``test_zzz_deduction_effect``. ولو بُني
له مخزٌن مستقل لصار للالتزام الواحد مصدران — وهي علّة
``EmployeeEvent``/``Deduction`` بعينها.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
MGR = ("100000000001", "manager123")
ACC = ("100000000007", "account123")

FIRST = "2033-01"


def _emp_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()


def _purge(rid: int) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Deduction).where(
            models.Deduction.request_id == rid))
        for tbl in (models.RequestDocument, models.RequestApproval):
            db.execute(sa_delete(tbl).where(tbl.request_id == rid))
        db.execute(sa_delete(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid))
        db.execute(sa_delete(models.Request).where(models.Request.id == rid))
        db.commit()
    finally:
        db.close()


def _loan(client, amount: float, months: int, first: str = FIRST,
          kind: str = "loan") -> int:
    payload = {"loan_type": kind, "amount": amount,
               "first_deduction_month": first, "reason": "قياس جدول السداد"}
    if kind == "loan":
        payload["months"] = months
    r = client.post("/api/requests", headers=auth_headers(login(client, *EMP)),
                    json={"request_type_code": "REQADV", "payload_json": payload})
    assert r.status_code in (200, 201), r.text[:300]
    rid = r.json()["id"]
    for who in (MGR, ACC):
        d = client.post(f"/api/requests/{rid}/decide",
                        headers=auth_headers(login(client, *who)),
                        json={"decision": "approved"})
        assert d.status_code == 200, (who[0], d.text[:200])
    return rid


def _installments(rid: int):
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Deduction).where(
            models.Deduction.request_id == rid
        ).order_by(models.Deduction.date)).all()
        return [(r.date.strftime("%Y-%m"), round(float(r.amount), 3),
                 r.ded_type, r.reason) for r in rows]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# الجدول يُبنى
# ---------------------------------------------------------------------------

def test_an_approved_loan_builds_its_repayment_schedule(client):
    """**جوهر البند**: القرض يُنتج أقساًطا، لا حالًة «مكتمل» وحدها."""
    rid = _loan(client, 300.0, 3)
    try:
        rows = _installments(rid)
        assert [m for m, *_ in rows] == ["2033-01", "2033-02", "2033-03"], rows
        assert [a for _m, a, *_ in rows] == [100.0, 100.0, 100.0], rows
    finally:
        _purge(rid)


def test_the_total_equals_the_principal_exactly(client):
    """**وقسٌط بلا كسٍر ضائع**: المجموع يساوي أصل الدين بالضبط.

    والكسر يُحمَل على القسط الأخير — اصطلاٌح حسابي معلٌَن لا مدفوٌن في
    سطر، فمن يراجع الجدول يعرف لماذا آخر قسط يخالف إخوته بفلوس.
    """
    rid = _loan(client, 100.0, 3)          # 33.333 × 3 = 99.999
    try:
        rows = _installments(rid)
        assert round(sum(a for _m, a, *_ in rows), 3) == 100.0, rows
        assert rows[-1][1] != rows[0][1], "لم يُحمَل الكسر على الأخير"
    finally:
        _purge(rid)


def test_an_advance_is_a_single_installment(client):
    """و«سلفة» تُخصم شهًرا واحًدا — كما يقول النموذج نفسه."""
    rid = _loan(client, 45.0, 0, kind="advance")
    try:
        rows = _installments(rid)
        assert len(rows) == 1, rows
        assert rows[0][1] == 45.0
    finally:
        _purge(rid)


def test_each_installment_explains_itself(client):
    """وكل قسٍط يقول ما هو ومن أين — لا مبلٌغ مجهول في كشف الراتب."""
    rid = _loan(client, 200.0, 2)
    try:
        rows = _installments(rid)
        assert all(t == "loan_installment" for _m, _a, t, _r in rows), rows
        assert "قسط 1 من 2" in rows[0][3], rows[0][3]
        assert str(rid) in rows[0][3], rows[0][3]
    finally:
        _purge(rid)


def test_the_payroll_reads_them_by_the_same_mechanism(client):
    """**ولا جدوٌل ثاٍن للمال**: الأقساط صفوُف خصم تقرؤها الرواتب."""
    rid = _loan(client, 60.0, 2)
    try:
        db = SessionLocal()
        try:
            rows = db.scalars(select(models.Deduction).where(
                models.Deduction.request_id == rid)).all()
            assert all(r.employee_id == _emp_id() for r in rows)
            assert all(r.date.day == 1 for r in rows), \
                "قسٌط بتاريٍخ لا يقع في أول شهره قد يُقرأ في غير موضعه"
        finally:
            db.close()
    finally:
        _purge(rid)


# ---------------------------------------------------------------------------
# ولا يبدأ حيث لا يُقرأ
# ---------------------------------------------------------------------------

def test_a_closed_first_month_refuses_the_schedule(client):
    """قسٌط في شهٍر أُقفل لا يقرؤه أحد — فيبقى الدين والجدول يقول إنه يُسدَّد."""
    closed = "2033-06"
    db = SessionLocal()
    run_id = None
    try:
        emp = db.get(models.Employee, _emp_id())
        run = models.PayrollRun(company_id=emp.company_id, period=closed,
                                status="locked")
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    rid = _loan(client, 50.0, 2, first=closed)
    try:
        db = SessionLocal()
        try:
            req = db.get(models.Request, rid)
            rows = db.scalars(select(models.Deduction).where(
                models.Deduction.request_id == rid)).all()
        finally:
            db.close()
        assert req.status == "apply_failed", req.status
        assert not rows, "بُني جدوٌل يبدأ في شهٍر مقفل"
    finally:
        _purge(rid)
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.PayrollRun).where(
                models.PayrollRun.id == run_id))
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# والدين الباقي يُحسَب ولا يُخزَّن
# ---------------------------------------------------------------------------

def test_the_outstanding_is_computed_from_unconsumed_installments(client):
    """**ورقٌم مخزَّن للدين يشيخ مع كل قسط** — فيُحسَب من أقساطه."""
    # **ويُقاس بالفرق لا بالمجموع المطلق.**
    #
    # الدالة تجمع دين الموظف كلّه، والقاعدة مشتركٌة بين الاختبارات — فشرٌط
    # على رقٍم مطلق يسقط بأثر اختبار آخر لا بعطل. وقد وقع: قُرئ 590 بدل
    # 90 لأن أنواًعا أخرى صارت تبني أقساًطا بعد هذا التغيير.
    db = SessionLocal()
    try:
        base = workflow.outstanding_loan(db, _emp_id())
    finally:
        db.close()

    rid = _loan(client, 90.0, 3)
    try:
        db = SessionLocal()
        try:
            assert workflow.outstanding_loan(db, _emp_id()) == pytest.approx(base + 90.0)
        finally:
            db.close()

        # يُقفل شهُر أول قسط: يصير مستهلًكا فينقص الدين.
        db = SessionLocal()
        run_id = None
        try:
            emp = db.get(models.Employee, _emp_id())
            run = models.PayrollRun(company_id=emp.company_id, period=FIRST,
                                    status="finalized")
            db.add(run)
            db.commit()
            run_id = run.id
            assert workflow.outstanding_loan(db, _emp_id()) == pytest.approx(base + 60.0)
        finally:
            db.close()
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.PayrollRun).where(
                models.PayrollRun.id == run_id))
            db.commit()
        finally:
            db.close()
    finally:
        _purge(rid)


def test_cancelling_removes_only_what_was_not_yet_taken(client):
    """**وجدوٌل نصُفه استُهلك لا يُلغى ولا يبقى كلّه.**

    فتُحذف الأقساط التي لم يقرأها مسيّر، وتبقى التي اقتُطعت — والباقي
    دٌين يُسوّى، لا صفوٌف تُمحى فيختفي أثُر ماٍل خرج.
    """
    rid = _loan(client, 90.0, 3)
    db = SessionLocal()
    run_id = None
    try:
        emp = db.get(models.Employee, _emp_id())
        run = models.PayrollRun(company_id=emp.company_id, period=FIRST,
                                status="finalized")
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    try:
        r = client.post(f"/api/requests/{rid}/cancel",
                        headers=auth_headers(login(client, *MGR)),
                        params={"note": "إلغاء بعد قسٍط واحد"})
        assert r.status_code == 200, (r.status_code, r.text[:250])
        rows = _installments(rid)
        assert len(rows) == 1 and rows[0][0] == FIRST, rows
    finally:
        _purge(rid)
        db = SessionLocal()
        try:
            db.execute(sa_delete(models.PayrollRun).where(
                models.PayrollRun.id == run_id))
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# ودٌين قائٌم لا يختفي بانتهاء الخدمة
# ---------------------------------------------------------------------------

def test_an_outstanding_loan_is_named_when_service_ends(client):
    """**أقساُط ما بعد آخر يوم عمل لا تقرؤها الرواتب.**

    فمن انتهت خدمته وعليه أقساٌط لم تُحتسب يسقط دينُه بصمت: لا شاشة تعرضه
    ولا تقرير. ولا يُقرَّر هنا مصيُره — اقتطاعه من المستحقات حٌد قانوني
    ومسألُة سياسة — لكنه **يُسمّى** فيبلغ من يسوّي الحساب، بدل أن
    يُكتشَف بعد إغلاق الملف أو لا يُكتشَف أصًلا.
    """
    from datetime import timedelta

    from app.clock import today as kuwait_today

    rid = _loan(client, 120.0, 4)
    eid = _emp_id()
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.EosCase).where(
            models.EosCase.employee_id == eid))
        db.commit()
    finally:
        db.close()

    resign = None
    try:
        last_day = (kuwait_today() + timedelta(days=45)).isoformat()
        r = client.post("/api/requests", headers=auth_headers(login(client, *EMP)),
                        json={"request_type_code": "REQRESIGN",
                              "employee_id": eid,
                              "payload_json": {"submitted_at": kuwait_today().isoformat(),
                                               "proposed_last_day": last_day,
                                               "notice_period_days": 30,
                                               "reason": "قياس الدين عند الخروج"}})
        assert r.status_code in (200, 201), r.text[:300]
        resign = r.json()["id"]
        for who in (MGR, ("100000000002", "hr12345")):
            d = client.post(f"/api/requests/{resign}/decide",
                            headers=auth_headers(login(client, *who)),
                            json={"decision": "approved"})
            assert d.status_code == 200, (who[0], d.text[:200])
        hh = auth_headers(login(client, "100000000002", "hr12345"))
        signed = client.post(f"/api/requests/{resign}/documents", headers=hh,
                             data={"kind": "signed_scan"},
                             files={"file": ("s.pdf", b"%PDF-1.4", "application/pdf")})
        assert signed.status_code == 200, signed.text[:200]

        db = SessionLocal()
        try:
            case = db.scalar(select(models.EosCase).where(
                models.EosCase.source_request_id == resign))
            assert case is not None, "لم تُفتح حالة نهاية الخدمة"
            task = db.scalar(select(models.Task).where(
                models.Task.dedup_key == f"exit_loan_due:{case.id}"))
        finally:
            db.close()
        assert task is not None, "انتهت الخدمة ودٌين القرض لم يُسمَّ"
        # والمبلغ يُذكر — ولا يُشترَط رقٌم بعينه: القاعدة مشتركة وقد يسبقه
        # ديٌن من اختباٍر آخر. المقيس أن الدين **يُسمّى** لا أن يساوي رقًما.
        assert "د.ك" in (task.detail or ""), task.detail
        assert task.severity == "critical", task.severity
    finally:
        if resign:
            db = SessionLocal()
            try:
                db.execute(sa_delete(models.EosCase).where(
                    models.EosCase.employee_id == eid))
                db.execute(sa_delete(models.Task).where(
                    models.Task.related_entity_type == "eos_case"))
                db.commit()
            finally:
                db.close()
            _purge(resign)
        _purge(rid)


# ---------------------------------------------------------------------------
# الاتفاقية تُصدَر موقَّعة أو جاهزًة للتوقيع — قرار المالك
# ---------------------------------------------------------------------------

def test_the_loan_issues_its_agreement(client):
    """**والاتفاقية تُصدَر** — ولا تحتاج قالًبا.

    ``OD-022`` بلا قالب في السجلّ، والمستند يُبنى من نوع الطلب ونصّه
    الرسمي لا من ملفّ قالب. وهويّتُه تُحَل من السجلّ: ``WF-009`` يعلن
    ``OD-022`` وحده، فلا يُخمَّن ولا يُشتقّ من قالٍب غائب.
    """
    from app import v15_registry as R

    assert R.canonical_od_for("REQADV", None) == "OD-022"

    rid = _loan(client, 80.0, 2)
    try:
        d = client.get(f"/api/requests/{rid}",
                       headers=auth_headers(login(client, *ACC))).json()
        kinds = [x["kind"] for x in (d.get("documents") or [])]
        assert "generated_pdf" in kinds, kinds
        db = SessionLocal()
        try:
            doc = db.scalar(select(models.RequestDocument).where(
                models.RequestDocument.request_id == rid,
                models.RequestDocument.kind == "generated_pdf"))
            assert doc.od_code == "OD-022", doc.od_code
        finally:
            db.close()
    finally:
        _purge(rid)


def _notice_codes(rid: int, uid: int) -> list[str]:
    db = SessionLocal()
    try:
        return [t.template_code for t in db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid,
            models.Task.assignee_user_id == uid)).all()]
    finally:
        db.close()


@pytest.mark.parametrize("has_signature", [True, False])
def test_one_message_reaches_the_employee_in_both_cases(client, has_signature):
    """**قرار المالك: رسالٌة واحدة تجمع الحالين.**

    الورقة تُطبع موقَّعة من صورة التوقيع المحفوظة، أو بخطٍّ فارغ إن لم
    تكن له صورة. وكنتُ فرّقتُ الرسالة بالحال — «جاهز للاستلام» لمن
    وقّعت صورتُه و«مطلوب حضورك للتوقيع» لغيره — فاختار المالك جملًة
    واحدة.

    وهي أقرب إلى ما يقع: الموظف يذهب إلى الشؤون في الحالين، وهناك يُعرَف
    أيوقّع أم يستلم. ورسالتان تفترضان أن النظام يعرف حال ورقته قبل أن
    يراها، وهو يعرف صورَة التوقيع لا ما تحتاجه الورقة عند التسليم.
    """
    eid = _emp_id()
    db = SessionLocal()
    try:
        user = db.scalar(select(models.User).where(models.User.employee_id == eid))
        uid, was = user.id, user.signature_path
        user.signature_path = was if has_signature else None
        db.commit()
    finally:
        db.close()

    rid = _loan(client, 70.0, 2)
    try:
        codes = _notice_codes(rid, uid)
        assert "NTF-075" in codes, f"لم يصله إشعار الاتفاقية: {codes}"
        assert "NTF-038" not in codes and "NTF-039" not in codes,             f"عادت الرسالتان المفرَّقتان: {codes}"
    finally:
        _purge(rid)
        db = SessionLocal()
        try:
            db.get(models.User, uid).signature_path = was
            db.commit()
        finally:
            db.close()


def test_the_single_notice_is_declared_in_the_catalog(client):
    """والقالب في الكتالوج لا نًصّا مكتوًبا في الشيفرة.

    فالجولة كلّها قامت على أن القوالب تُعلَن في موضع واحد — ونٌصّ يُكتب
    في مكان إرساله يفلت من كل مراجعة تمرّ على الكتالوج.
    """
    from app import notification_templates as NT

    codes = {t["code"] for t in NT.DEFAULT_NOTIFICATION_TEMPLATES}
    assert "NTF-075" in codes, "قالٌب يُرسَل ولا يُعلَن في الكتالوج"
