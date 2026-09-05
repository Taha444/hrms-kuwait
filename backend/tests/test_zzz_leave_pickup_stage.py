# -*- coding: utf-8 -*-
"""مرحلة استلام لطلب الإجازة — قرار المالك.

بعد إلغاء انتظار التوقيع صارت الإجازة تُغلَق عند شؤون الموظفين: يصدر
المستند وتقول الشاشة «مكتمل» ولا يُقال لأحد أين يأخذه. وهو أثر جانبي
قِسته وأبلغتُه، فقرّر المالك إضافة المرحلة.

**وموضعها بعد المندوب لا قبله**: ليأخذ الموظف نموذج الإجازة وإذن
المغادرة مًعا، لا على دفعتين.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
SUP = ("100000000005", "sup12345")
HR = ("100000000002", "hr12345")
DELEGATE = ("100000000004", "deleg123")

#: اختبارات **المسار** تستعمل نوًعا لا يخصم الرصيد: الرصيد مشترك بين
#: وحدات الاختبار، فوحدة تستهلكه تُسقط غيرها بسبب لا علاقة له بها.
#: والخصم نفسه يقيسه ``test_the_balance_is_deducted_before_the_handover``
#: بيومين من ``annual``.
LEAVE = {"start_date": "2028-04-02", "end_date": "2028-04-06", "days": 5,
         "leave_type": "unpaid", "reason": "راحة", "travel_required": False}


def _emp_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()


def _leave(client, hdr, **over) -> int:
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": _emp_id(), "request_type_code": "REQLV",
        "payload_json": {**LEAVE, **over}})
    assert r.status_code == 201, r.text[:250]
    return r.json()["id"]


def test_a_leave_ends_ready_for_pickup_not_silently_complete(client):
    """**جوهر القرار**: الورقة تصدر ويُقال أين تُستلَم."""
    hdr = auth_headers(login(client, *EMP))
    rid = _leave(client, hdr)
    for who in (SUP, HR):
        d = client.post(f"/api/requests/{rid}/decide",
                        headers=auth_headers(login(client, *who)),
                        json={"decision": "approved"})
        assert d.status_code == 200, d.text[:200]

    assert client.get(f"/api/requests/{rid}", headers=hdr).json()["status"] \
        == "ready_for_pickup"


def test_the_pickup_closes_the_request(client):
    """ومرحلة لا تُغلَق تصير طابوًرا لا ينتهي — فالاستلام يُنهي الطلب."""
    hdr = auth_headers(login(client, *EMP))
    rid = _leave(client, hdr, start_date="2028-05-02", end_date="2028-05-04",
                 days=3)
    for who in (SUP, HR):
        client.post(f"/api/requests/{rid}/decide",
                    headers=auth_headers(login(client, *who)),
                    json={"decision": "approved"})

    hr_hdr = auth_headers(login(client, *HR))
    r = client.post(f"/api/requests/{rid}/received", headers=hr_hdr)
    assert r.status_code == 200, r.text[:200]
    assert client.get(f"/api/requests/{rid}", headers=hdr).json()["status"] \
        == "completed"


def test_the_document_is_already_issued_when_pickup_opens(client):
    """والاستلام لا يُفتَح على لا شيء: المستند صادر قبله.

    فلو صارت المرحلة قبل التوليد لدُعي الموظف ليأخذ ورقًة لم تُطبَع.
    """
    hdr = auth_headers(login(client, *EMP))
    rid = _leave(client, hdr, start_date="2028-06-04", end_date="2028-06-06",
                 days=3)
    for who in (SUP, HR):
        client.post(f"/api/requests/{rid}/decide",
                    headers=auth_headers(login(client, *who)),
                    json={"decision": "approved"})

    db = SessionLocal()
    try:
        docs = db.scalars(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid)).all()
    finally:
        db.close()
    assert any(d.lifecycle_status == "GENERATED" and d.file_path
               for d in docs), (
        f"فُتح الاستلام بلا مستند: {[(d.kind, d.lifecycle_status) for d in docs]}"
    )


def test_a_travelling_leave_picks_up_after_the_delegate(client):
    """**والموضع مقصود**: الاستلام بعد إذن المغادرة لا قبله.

    فلو سبقه لاستُدعي الموظف مرّتين — مرّة للإجازة ومرّة للإذن.
    """
    import io as _io

    hdr = auth_headers(login(client, *EMP))
    rid = _leave(client, hdr, start_date="2028-07-02", end_date="2028-07-06",
                 travel_required=True, destination="القاهرة")
    for who in (SUP, HR):
        client.post(f"/api/requests/{rid}/decide",
                    headers=auth_headers(login(client, *who)),
                    json={"decision": "approved"})
    assert client.get(f"/api/requests/{rid}", headers=hdr).json()["status"] \
        == "awaiting_delegate", "الاستلام سبق المندوب"

    dl = auth_headers(login(client, *DELEGATE))
    r = client.post(f"/api/requests/{rid}/documents", headers=dl,
                    data={"kind": "exit_permit"},
                    files={"file": ("exit.pdf", _io.BytesIO(b"exit-permit"),
                                    "application/pdf")})
    assert r.status_code == 200, r.text[:200]
    assert r.json()["status"] == "ready_for_pickup", r.json()["status"]


def test_the_decision_reaches_existing_databases():
    """**والبذر يُدرج ولا يُحدِّث**: بلا ترحيل تبقى سلاسل الشركات بلا استلام.

    ولا يُكتَب فوق تخصيص: السلسلة صفٌّ لكل شركة، فالترحيل يُلحق المرحلة
    إن لم تكن فيه ويترك ما عداه.
    """
    from pathlib import Path

    versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    hits = [p for p in versions.glob("*.py")
            if "approval_chain_json" in (t := p.read_text(encoding="utf-8"))
            and '"pickup"' in t]
    assert hits, "مرحلة الاستلام لا تصل إلى القواعد القائمة"
    text = "\n".join(p.read_text(encoding="utf-8") for p in hits)
    assert "REQLV" in text and '"leave"' in text, (
        "الترحيل لا يغطّي كودَي الإجازة — أحدهما يبقى بلا استلام"
    )


def test_the_seed_and_the_migration_describe_the_same_stage():
    """وقاعدة مكتوبة في مكانين تنحرف — فيُقاس تطابقهما لا يُفترَض."""
    from pathlib import Path

    leave = next(rt for rt in workflow.DEFAULT_REQUEST_TYPES
                 if rt["code"] == "leave")
    stage = next(s for s in leave["approval_chain_json"]
                 if s.get("kind") == "pickup")

    mig = (Path(__file__).resolve().parents[1] / "alembic" / "versions"
           / "f6a7b8c9d0e_leave_pickup_stage.py").read_text(encoding="utf-8")
    assert stage["label"] in mig, "وصف المرحلة اختلف بين البذر والترحيل"
    assert f'"role": "{stage["role"]}"' in mig, "دور المرحلة اختلف بينهما"


def test_an_execution_stage_is_never_skipped_for_a_repeated_actor():
    """**العيب الكامن**: قاعدة «لا يراجع أحد قراره» كانت تبتلع التنفيذ.

    تخطّي مرحلة استلام لأن منفّذها هو نفسه من اعتمد قبلها يُلغي **عمًلا
    واقًعا** لا قراًرا مكرًرا: يُغلَق الطلب وقد صدر المستند ولم يستلمه
    أحد. وكان كامًنا لأن مراحل التنفيذ القائمة يخالف دورها ما قبلها
    دائًما (المحاسب بعد المدير) — وأول استلام بدور ``hr`` بعد مراجعة
    ``hr`` كشفه.

    والحارس على القاعدة نفسها لا على عرَضها في الإجازة.
    """
    assert workflow.ACTION_STAGE_KINDS >= {"pickup", "delegate_exit"}, (
        workflow.ACTION_STAGE_KINDS
    )
    import inspect

    src = inspect.getsource(workflow._skip_duplicate_approver)
    assert "ACTION_STAGE_KINDS" in src, (
        "عادت قاعدة التخطّي تبتلع مراحل التنفيذ"
    )


def test_the_balance_is_deducted_before_the_handover_not_after(client):
    """**الخطر الحقيقي في إضافة المرحلة**: أن يتأخّر الأثر إلى تسليم الورقة.

    الأثر كان مربوًطا بالإغلاق. وإضافة مرحلة بعده تنقل خصم الرصيد
    وتسجيل الإجازة إلى أن يسجّل أحدهم الاستلام — فيسافر الموظف ولا صفّ
    إجازة له ولا رصيد نقص. وأسوأ منه أن نقص الرصيد كان سيظهر بعد أن
    قيل له «جاهز للاستلام».

    فُصل التطبيق عن الإغلاق: يقع عند انتهاء العمل، ويُغلق الطلب عند
    التسليم. وهذا الحارس يقيس **التوقيت** لا وقوع الأثر وحده.
    """
    hdr = auth_headers(login(client, *EMP))
    rid = _leave(client, hdr, start_date="2028-08-01", end_date="2028-08-02",
                 days=2, leave_type="annual")
    for who in (SUP, HR):
        client.post(f"/api/requests/{rid}/decide",
                    headers=auth_headers(login(client, *who)),
                    json={"decision": "approved"})

    db = SessionLocal()
    try:
        req = db.get(models.Request, rid)
        assert req.status == "ready_for_pickup", req.status
        applied = db.scalars(select(models.RequestApproval).where(
            models.RequestApproval.request_id == rid,
            models.RequestApproval.approver_role == "system")).all()
        leaves = db.scalars(select(models.Leave).where(
            models.Leave.employee_id == req.employee_id)).all()
    finally:
        db.close()

    assert [a.decision for a in applied] == ["approved"], (
        f"الأثر لم يقع قبل التسليم: {[(a.decision, a.note) for a in applied]}"
    )
    assert any(str(l.start_date).startswith("2028-08-01") for l in leaves), (
        "لا صفّ إجازة قبل التسليم — الموظف يسافر بلا سجل"
    )


def test_a_failed_effect_does_not_open_a_handover(client):
    """ولا يُدعى أحد ليستلم ورقًة أثرُها لم يقع.

    فالفشل يوقف الطلب عند ``apply_failed``، ولا يمرّ إلى «جاهز للاستلام».
    """
    hdr = auth_headers(login(client, *EMP))
    # أيام تفوق الرصيد السنوي (30) وتبقى داخل حدّ النموذج (90).
    rid = _leave(client, hdr, start_date="2029-01-01", end_date="2029-03-31",
                 days=90, leave_type="annual")
    for who in (SUP, HR):
        client.post(f"/api/requests/{rid}/decide",
                    headers=auth_headers(login(client, *who)),
                    json={"decision": "approved"})

    db = SessionLocal()
    try:
        req = db.get(models.Request, rid)
        status, stage = req.status, req.current_stage
    finally:
        db.close()
    assert status == "apply_failed", status
    # ولا يقفز إلى الأمام: الفشل يُرجعه إلى آخر مرحلة اعتُمدت فعًلا.
    assert stage == 1, f"الفشل نقل الطلب إلى مرحلة لم يبلغها: {stage}"
