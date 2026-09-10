# -*- coding: utf-8 -*-
"""البند 3 — الاستقالة تبلغ نهايتها **من الشاشة** لا من الواجهة البرمجية.

**العطل المقيس**: مسار الاستقالة يعمل على الخادم — يسوقه
``test_zzz_exit_master_case`` كامًلا ويخضرّ: اعتماد المدير، فاعتماد
شؤون الموظفين، فـ``awaiting_signature``، فرفع النسخة الموقّعة،
فـ``completed`` وفتح مرجع نهاية الخدمة.

**لكنه يسوقه بنداء المسار لا بضغط زرّ.** وكتلة التوقيع في الشاشة —
الموعد ورفع النسخة الموقّعة — كانت محروسة بالصلاحية العامة
``approve_request``. وقياس الصلاحية:

- ``approve_request in _ALL`` → ``True``
- الأدوار التي تحملها → ``['super_admin']``

فالشرط **كاذٌب لكل دور إلا المدير العام التقني**: لا شؤون الموظفين، ولا
مدير الشركة، ولا المالك (``company_owner`` لا يحمل ولا واحدة من صلاحيات
الاعتماد أصًلا). فتصل الاستقالة مرحلة التوقيع ولا يملك **أحٌد في الشركة**
زًرا يتمّها. وزرّ «تسجيل الاستلام» كان بالشرط نفسه.

وهذا يلتقي بقاعدة المالك «لا تمنح أي مستخدم Super Admin»: المخرج الوحيد
كان محجوًزا للدور الذي مُنع منحه.

**والاختبار الذي يمرّ من الخادم ولا يمرّ من الشاشة صادَق على طريق لا
يستطيع أحٌد أن يسلكه.** فهذه الحرّاس تقيس ما تعرضه الشاشة عند كل مرحلة،
لا ما يقبله المسار وحده.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from app.task_kinds import is_notification
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")
MGR = ("100000000001", "manager123")
SUP = ("100000000005", "sup12345")

RESIGN = {"submitted_at": "2027-08-01", "proposed_last_day": "2027-09-01",
          "notice_period_days": 30, "reason": "قياس مسار الاستقالة"}


def _offered(client, rid: int, creds) -> list[str]:
    """ما تعرضه الشاشة لهذا المستخدم على هذا الطلب الآن."""
    d = client.get(f"/api/requests/{rid}",
                   headers=auth_headers(login(client, *creds))).json()
    return [a["action"] for a in (d.get("allowed_actions") or [])]


@pytest.fixture
def resignation(client):
    """استقاٌلة مقدَّمة — ويُنظَّف أثرها كلّه بعد القياس."""
    db = SessionLocal()
    try:
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
        # «لا خروج آخر مفتوح» شرٌط مسبق يُثبَّت لا يُفترَض: موظف البذرة
        # تتشاركه اختبارات أخرى، وبعضها يفتح مرجًعا ويتركه.
        db.execute(sa_delete(models.EosCase).where(
            models.EosCase.employee_id == eid))
        db.commit()
    finally:
        db.close()

    r = client.post("/api/requests", headers=auth_headers(login(client, *EMP)),
                    json={"employee_id": eid, "request_type_code": "REQRESIGN",
                          "payload_json": RESIGN})
    assert r.status_code in (200, 201), r.text[:300]
    rid = r.json()["id"]

    yield rid

    db = SessionLocal()
    try:
        db.execute(sa_delete(models.EosCase).where(
            models.EosCase.source_request_id == rid))
        db.execute(sa_delete(models.EosCase).where(
            models.EosCase.employee_id == eid))
        for tbl in (models.RequestDocument, models.RequestApproval,
                    models.Appointment):
            db.execute(sa_delete(tbl).where(tbl.request_id == rid))
        db.execute(sa_delete(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == rid))
        db.execute(sa_delete(models.Request).where(models.Request.id == rid))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def at_signature(client, resignation):
    """استقاٌلة معتمَدة حتى مرحلة التوقيع — بالاعتمادين لا بحيلة."""
    for who in (MGR, HR):
        d = client.post(f"/api/requests/{resignation}/decide",
                        headers=auth_headers(login(client, *who)),
                        json={"decision": "approved", "note": "تمّ"})
        assert d.status_code == 200, (who[0], d.text[:200])
    body = client.get(f"/api/requests/{resignation}",
                      headers=auth_headers(login(client, *HR))).json()
    assert body["status"] == "awaiting_signature", body["status"]
    return resignation


# ---------------------------------------------------------------------------
# كل مرحلة تعرض فعلها لمن يملكه
# ---------------------------------------------------------------------------

def test_each_approval_stage_offers_its_action(client, resignation):
    """خطّ الأساس: مرحلتا القرار تعرضان أفعالهما لمعتمِديهما."""
    assert "approve" in _offered(client, resignation, MGR)
    # ولا يعتمد من ليس معتمِد المرحلة الأولى.
    assert _offered(client, resignation, SUP) == []

    client.post(f"/api/requests/{resignation}/decide",
                headers=auth_headers(login(client, *MGR)),
                json={"decision": "approved"})
    assert "approve" in _offered(client, resignation, HR)


def test_the_signature_stage_is_walkable_by_a_real_role(client, at_signature):
    """**جوهر البند**: مرحلة التوقيع لها مخرٌج يراه دوٌر حقيقي.

    كان الشرط على الصلاحية العامة ``approve_request`` — ولا يحملها إلا
    ``super_admin`` — فتصل الاستقالة هنا ويقف الجميع. والمخرج الآن
    معروٌض لشؤون الموظفين.
    """
    acts = _offered(client, at_signature, HR)
    assert acts == ["upload_signed_scan"], acts


def test_the_employee_cannot_sign_his_own_resignation_through(client, at_signature):
    """ولا يتمّ صاحب الاستقالة توقيعها بنفسه — عرًضا ولا نداًء."""
    assert _offered(client, at_signature, EMP) == []
    r = client.post(f"/api/requests/{at_signature}/documents",
                    headers=auth_headers(login(client, *EMP)),
                    data={"kind": "signed_scan"},
                    files={"file": ("s.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 403, r.text[:200]


def test_a_stalled_signature_stage_says_what_it_needs(client, at_signature):
    """ومن ليس صاحبها ولا يملكها يُقرأ له السبب لا الفراغ."""
    d = client.get(f"/api/requests/{at_signature}",
                   headers=auth_headers(login(client, *SUP))).json()
    assert d["allowed_actions"] == []
    assert "النسخة الموقّعة" in (d.get("no_actions_reason") or ""), \
        d.get("no_actions_reason")


# ---------------------------------------------------------------------------
# وتبلغ نهايتها، ويقع أثرها، وتُقفَل مهامّها
# ---------------------------------------------------------------------------

def _sign(client, rid: int):
    return client.post(f"/api/requests/{rid}/documents",
                       headers=auth_headers(login(client, *HR)),
                       data={"kind": "signed_scan"},
                       files={"file": ("s.pdf", b"%PDF-1.4", "application/pdf")})


def test_the_resignation_reaches_a_terminal_state(client, at_signature):
    """**والرحلة تُقطَع إلى آخرها** بالفعل المعروض نفسه."""
    assert _sign(client, at_signature).status_code == 200

    db = SessionLocal()
    try:
        req = db.get(models.Request, at_signature)
        status, closed = req.status, req.closed_at
    finally:
        db.close()
    assert status == "completed", status
    assert closed is not None, "بلغ نهايته ولم يُغلَق"


def test_completion_opens_the_exit_case_linked_to_it(client, at_signature):
    """وأثرها يقع: مرجع نهاية الخدمة يُفتح ويُربط بالطلب.

    وهذا مقيٌس في ``test_zzz_exit_master_case`` عبر المسار — ويُعاد هنا
    بالفعل **المعروض** كي لا يُصلَح العرض ويُكسَر الأثر بلا أن يُلحَظ.
    """
    _sign(client, at_signature)
    db = SessionLocal()
    try:
        case = db.scalar(select(models.EosCase).where(
            models.EosCase.source_request_id == at_signature))
        ref = getattr(case, "reference_no", None)
        day = str(getattr(case, "termination_date", ""))
    finally:
        db.close()
    assert case is not None, "اكتملت الاستقالة ولم يُفتح مرجعها"
    assert ref, "مرجٌع بلا رقم"
    assert day == RESIGN["proposed_last_day"], day


def test_no_work_task_survives_the_resignation(client, at_signature):
    """ومهامّ عملها تُقفَل، وإخطاراتها تبقى تُقرأ."""
    _sign(client, at_signature)
    db = SessionLocal()
    try:
        rows = db.scalars(select(models.Task).where(
            models.Task.related_entity_type == "request",
            models.Task.related_entity_id == at_signature,
            models.Task.status.in_(("open", "in_progress")),
        )).all()
        work = [f"{t.type}:{t.title}" for t in rows if not is_notification(t.type)]
        notes = [t.type for t in rows if is_notification(t.type)]
    finally:
        db.close()
    assert not work, f"مهام مفتوحة بعد الاكتمال: {work}"
    assert notes, "أُغلقت الإخطارات مع المهام — فلا يعرف الموظف ماذا جرى"


def test_the_official_document_is_issued(client, at_signature):
    """والورقة تُصدَر: استقاٌلة مكتملة بلا مستند إجراٌء بلا أثر ورقي."""
    _sign(client, at_signature)
    d = client.get(f"/api/requests/{at_signature}",
                   headers=auth_headers(login(client, *HR))).json()
    kinds = [x["kind"] for x in (d.get("documents") or [])]
    assert "generated_pdf" in kinds, kinds
    assert "signed_scan" in kinds, kinds
