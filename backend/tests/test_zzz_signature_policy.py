# -*- coding: utf-8 -*-
"""P5-23 — سياسة التوقيع تُقرأ من إعلانها، والانحراف صار مستحيًلا بنيوًيا.

**ما كان بالقياس:**

``requires_physical_signature`` راية على 54 نوًعا ولها عمود في القاعدة —
و**لا موضع واحد يقرؤها**. والسلوك يأتي من بنية السلسلة:
``stage.kind == "hr_review"`` هو ما يوقف الطلب للتوقيع.

فانحرف الاثنان: **14 نوًعا** تُعلن «توقيع مادّي مطلوب» ولا تطلبه أبًدا —
ومنها الاستقالة وتسوية نهاية الخدمة وإخلاء الطرف، تُصدَر ويُغلق طلبها
«مكتمل» بلا أن يوقّع الموظف شيًئا.

**وقرار المالك**: الاستقالة والتسوية وإخلاء الطرف **تُوقَّع**، وتُرفَع
الراية عن الباقي.

**ولم تُضَف مراحل للثلاثة.** لو أُصلحت ثلاث حالات لعاد الانحراف مع
رابعة تُضاف غًدا. فصارت **الراية هي المشغّل**: الطلب يقف للتوقيع حين
يُعلن نوعه ذلك عند المرحلة المُصدِرة للمستند — فالمعلَن هو الواقع، ولا
يبقى موضعان ينحرفان.

**والبذر يُدرج ولا يُحدِّث** (درس QA-07 مع ``REQSIG``): فالترحيل
``f0a1b2c3d4e`` يبلّغ القرار إلى القواعد القائمة. وإهماله هنا لا يترك
عيًبا صامًتا بل **يُعطّل** الأنواع الأحد عشر على الإنتاج — تقف طلباتها
عند ``awaiting_signature`` انتظاًرا لتوقيع لم يقرّره أحد.
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from sqlalchemy import delete as sa_delete, select

from app import exit_guard, models, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

#: قرار المالك: هذه تُوقَّع. و``leave`` كانت تعمل أصًلا.
SIGNED = {"leave", "REQRESIGN", "REQEOS", "REQCLR"}

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")
MGR = ("100000000001", "manager123")

RESIGN = {"submitted_at": "2027-01-05", "proposed_last_day": "2027-02-05",
          "notice_period_days": 30, "reason": "ظروف شخصية"}


@pytest.fixture
def resigning_employee():
    """موظف تُفتح له استقالة ثم تُغلق.

    حارس «خروج واحد» (P6-27) يمنع فتح استقالة ثانية للموظف نفسه —
    فاختباران يفتحانها بلا تنظيف يسقط ثانيهما بسبب ليس ما يقيسه.
    """
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
        yield eid
    finally:
        rows = [r for (r,) in db.execute(select(models.Request.id).where(
            models.Request.employee_id == eid,
            models.Request.request_type_code.in_(
                exit_guard.EXIT_REQUEST_TYPES))).all()]
        if rows:
            db.execute(sa_delete(models.Task).where(
                models.Task.related_entity_type == "request",
                models.Task.related_entity_id.in_(rows)))
            db.execute(sa_delete(models.RequestApproval).where(
                models.RequestApproval.request_id.in_(rows)))
            db.execute(sa_delete(models.RequestDocument).where(
                models.RequestDocument.request_id.in_(rows)))
            db.execute(sa_delete(models.Request).where(
                models.Request.id.in_(rows)))
            db.commit()
        db.close()


def _declares(rt: dict) -> bool:
    return bool(rt.get("requires_physical_signature"))


def _issuing(rt: dict) -> bool:
    return any(s.get("produces_document") or s.get("kind") == "hr_review"
               for s in (rt.get("approval_chain_json") or []))


def test_the_engine_reads_the_declaration_not_the_chain_shape():
    """**جوهر الإصلاح**: المشغّل صار الإعلان لا بنية السلسلة."""
    src = inspect.getsource(workflow.decide)
    assert "requires_physical_signature" in src, (
        "المحرّك ما زال لا يقرأ السياسة المعلَنة"
    )
    assert 'if kind == "hr_review":' not in src, (
        "بقي مشغّل ثانٍ من بنية السلسلة — وموضعان ينحرفان"
    )


def test_exactly_the_owners_three_still_require_a_signature():
    """قرار المالك مثبَّت بالأسماء: الاستقالة والتسوية وإخلاء الطرف."""
    declared = {rt["code"] for rt in workflow.DEFAULT_REQUEST_TYPES
                if _declares(rt)}
    assert declared == SIGNED, (
        f"زائد: {sorted(declared - SIGNED)} · ناقص: {sorted(SIGNED - declared)}"
    )


def test_the_divergence_is_gone_not_merely_smaller():
    """**والانحراف صفر**: كل نوع يُعلن توقيًعا له مرحلة تُصدر مستنًدا.

    ونوع يُعلن توقيًعا بلا مستند يُصدره يقف للأبد على توقيع ورقة لا
    وجود لها — وهو ما كان ``REQWP`` يفعله لو قُرئت رايته.
    """
    orphans = [rt["code"] for rt in workflow.DEFAULT_REQUEST_TYPES
               if _declares(rt) and not _issuing(rt)]
    assert not orphans, f"تُعلن توقيًعا بلا مستند يُصدَر: {orphans}"


def test_a_signed_type_stops_and_waits(client, resigning_employee):
    """الاستقالة تقف عند التوقيع ولا تُغلق «مكتملة» بلا توقيع."""
    eid = resigning_employee
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQRESIGN",
        "payload_json": RESIGN})
    assert r.status_code == 201, r.text[:250]
    rid = r.json()["id"]

    for who in (MGR, HR):
        h = auth_headers(login(client, *who))
        d = client.post(f"/api/requests/{rid}/decide", headers=h,
                        json={"decision": "approved"})
        assert d.status_code == 200, d.text[:200]

    body = client.get(f"/api/requests/{rid}", headers=hdr).json()
    assert body["status"] == "awaiting_signature", (
        f"أُغلقت الاستقالة بلا توقيع: {body['status']}"
    )


def test_the_document_is_generated_before_the_wait(client, resigning_employee):
    """ولا يُنتظَر توقيع ورقة لم تُولَّد بعد."""
    eid = resigning_employee
    hdr = auth_headers(login(client, *EMP))
    rid = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQRESIGN",
        "payload_json": RESIGN}).json()["id"]
    for who in (MGR, HR):
        client.post(f"/api/requests/{rid}/decide",
                    headers=auth_headers(login(client, *who)),
                    json={"decision": "approved"})

    db = SessionLocal()
    try:
        docs = db.scalars(select(models.RequestDocument).where(
            models.RequestDocument.request_id == rid)).all()
    finally:
        db.close()
    assert any(d.lifecycle_status == "GENERATED" and d.file_path for d in docs), (
        f"وقف للتوقيع بلا مستند: {[(d.kind, d.lifecycle_status) for d in docs]}"
    )


def test_a_lifted_type_no_longer_waits(client):
    """وما رُفعت رايته لا يقف: خطوة يدوية بلا سبب هي ما يعالجه البند.

    ولولا رفع الراية لتوقّفت الأنواع الأحد عشر كلها بعد أن صار المحرّك
    يقرأ الإعلان — أي أن القراءة بلا القرار كانت ستُعطّلها.
    """
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()
    hdr = auth_headers(login(client, *EMP))
    r = client.post("/api/requests", headers=hdr, json={
        "employee_id": eid, "request_type_code": "REQTRF",
        "payload_json": {"current_branch": "الفرع الأول",
                         "target_branch": "الفرع الثاني",
                         "effective_date": "2027-03-01",
                         "reason": "إعادة توزيع"}})
    assert r.status_code == 201, r.text[:250]
    rid = r.json()["id"]
    for who in (MGR, HR):
        h = auth_headers(login(client, *who))
        d = client.post(f"/api/requests/{rid}/decide", headers=h,
                        json={"decision": "approved"})
        if d.status_code != 200:
            break
    body = client.get(f"/api/requests/{rid}", headers=hdr).json()
    assert body["status"] != "awaiting_signature", (
        "نوع رُفعت رايته ما زال يقف للتوقيع"
    )


def test_the_decision_reaches_existing_databases():
    """**والبذر يُدرج ولا يُحدِّث**: بلا ترحيل يبقى الإنتاج على قيمته.

    وهنا لا يترك الإهمالُ عيًبا صامًتا بل يُعطّل: بعد أن صار المحرّك
    يقرأ الراية، تقف الأنواع الأحد عشر عند ``awaiting_signature``
    انتظاًرا لتوقيع لم يقرّره أحد.
    """
    versions = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    # الترحيل الذي **يضبط القيم** لا الذي يذكر العمود: أول كتابة أمسكت
    # ترحيل المخطّط الابتدائي لأن CREATE TABLE فيه يذكر العمود.
    setters = [p for p in versions.glob("*.py")
               if "requires_physical_signature" in (
                   text := p.read_text(encoding="utf-8"))
               and "REQRESIGN" in text]
    assert setters, "لا ترحيل يوصّل قرار التوقيع إلى القواعد القائمة"

    text = setters[0].read_text(encoding="utf-8")
    for code in ("REQEOS", "REQCLR"):
        assert code in text, f"{code} غائب عن الترحيل"
    for code in ("REQTRF", "ADMWARN", "REQPROMO"):
        assert code in text, f"{code} غائب عن الترحيل — تبقى رايته مرفوعة"


def test_certificates_were_never_in_the_gap():
    """والشهادات لم تكن جزًءا من الانحراف — تُصدرها الشركة وتوقّعها هي."""
    certs = {"salary_certificate", "REQCERTSAL", "REQCERTEMP", "REQCERTEXP"}
    declared = {rt["code"] for rt in workflow.DEFAULT_REQUEST_TYPES
                if _declares(rt)}
    assert not (certs & declared), sorted(certs & declared)
