# -*- coding: utf-8 -*-
"""البندان 6 و7 — خريطة الإجازة إلى المستند، ومسار السفر.

**6 — أُغلق قبل هذه الجولة، ويُثبَّت هنا لا يُعاد إصلاحه.** التقرير يقول
إن الإجازة تولّد ``OD-005`` (قرار تغيير وظيفي) بينما السجل يقول
``OD-011``. والقياس على البناء الحالي: ``leave → HRMS-PR-027 → OD-011``
— مطابق للسجل. فالبند يسبق إصلاح الخريطة، والحارس هنا يمنع عودته.

**7 — المسار القانوني كان يُحَل من الكود وحده.** كنية ``leave`` في
السجل تقول حرفًيا «قد يتحول إلى WF-002 لو travel_required=true»،
و``resolve_request`` لا ترى الحمولة أصًلا. فإجازة السفر تُقرأ «إجازة
عادية» في كل ما يعرض المسار — **بينما مسارها الفعلي يمرّ بالمندوب**.

**وحدود ما نُفِّذ مذكورة**: ``OD-012`` (إفادة مالية للسفر) و``OD-013``
(غلاف متابعة حكومية) لا قالب لهما في السجل. فتوليدهما ليس إصلاح كود بل
مستندان يلزم اعتمادهما. وادّعاء إنتاجهما أسوأ من غيابهما.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models, v15_registry as R, workflow
from app.database import SessionLocal
from tests.conftest import auth_headers, login

EMP = ("100000000101", "emp12345")
HR = ("100000000002", "hr12345")


def _emp_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee.id).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()


def _leave(client, travel: bool, day: str) -> int:
    hdr = auth_headers(login(client, *EMP))
    body = {"employee_id": _emp_id(), "request_type_code": "REQLV",
            "payload_json": {"start_date": f"2031-{day}-01",
                             "end_date": f"2031-{day}-04", "days": 4,
                             "leave_type": "unpaid", "reason": "قياس المسار",
                             "travel_required": travel}}
    if travel:
        body["payload_json"]["destination"] = "القاهرة"
    r = client.post("/api/requests", headers=hdr, json=body)
    assert r.status_code == 201, r.text[:250]
    return r.json()["id"]


def test_the_leave_template_matches_the_registry():
    """**البند 6**: الخريطة مطابقة للسجل — ويُثبَّت لا يُعاد إصلاحه."""
    leave = next(rt for rt in workflow.DEFAULT_REQUEST_TYPES
                 if rt["code"] == "leave")
    od = R.resolve_template(leave["default_template_code"])
    assert od == "OD-011", f"{leave['default_template_code']} → {od}"
    assert R.CANONICAL_WORKFLOWS["WF-001"]["od"] == ["OD-011"]


def test_a_travelling_leave_is_read_as_travel(client):
    """**جوهر البند 7**: السفر يُقرأ سفًرا لا إجازة عادية."""
    rid = _leave(client, travel=True, day="03")
    body = client.get(f"/api/requests/{rid}",
                      headers=auth_headers(login(client, *HR))).json()
    assert body["canonical_workflow"] == "WF-002", body["canonical_workflow"]


def test_a_normal_leave_stays_normal(client):
    """ولا يُرقَّى ما لا يستحق: بلا سفر يبقى WF-001."""
    rid = _leave(client, travel=False, day="04")
    body = client.get(f"/api/requests/{rid}",
                      headers=auth_headers(login(client, *HR))).json()
    assert body["canonical_workflow"] == "WF-001", body["canonical_workflow"]


def test_the_promotion_rule_is_the_one_the_registry_documents():
    """والقاعدة من السجل لا من ظنّ: كنية ``leave`` تنصّ عليها."""
    note = R.LEGACY_REQUEST_ALIASES["leave"].get("note", "")
    assert "WF-002" in note and "travel_required" in note, note
    promoted = R.resolve_request_for("leave", {"travel_required": True})
    assert promoted["canonical"] == "WF-002"
    assert promoted["promoted_from"] == "WF-001"
    assert R.resolve_request_for("leave", {})["canonical"] == "WF-001"


def test_the_bare_code_resolver_is_untouched():
    """و``resolve_request`` تبقى للكود المجرَّد: الكتالوج والاستبدال.

    سؤال «ما مسار هذا النوع؟» غير سؤال «ما مسار هذا الطلب؟» — ودمجهما
    في دالة واحدة يجعل الكتالوج يعرض السفر لكل من يطلب إجازة.
    """
    assert R.resolve_request("leave")["canonical"] == "WF-001"


def test_the_routing_already_treats_travel_as_travel(client):
    """**والاسم ليس المهمّ وحده**: المسار الفعلي يمرّ بالمندوب.

    وهذا كان صحيًحا قبل البند (QA-10) — يُقاس هنا لأن الاسم بلا مسار
    مطابق تسميٌة لا إصلاح.
    """
    rid = _leave(client, travel=True, day="05")
    hdr = auth_headers(login(client, *HR))
    for who in (("100000000005", "sup12345"), HR):
        client.post(f"/api/requests/{rid}/decide",
                    headers=auth_headers(login(client, *who)),
                    json={"decision": "approved"})
    body = client.get(f"/api/requests/{rid}", headers=hdr).json()
    assert body["status"] == "awaiting_delegate", body["status"]
    assert "delegate" in [s.get("role") for s in body.get("stages", [])]


def test_the_travel_documents_have_no_template_yet():
    """**وحدّ ما نُفِّذ مقيس لا مُدَّعى**.

    ``OD-012`` و``OD-013`` معرَّفان في كتالوج المستندات ولا قالب لهما.
    فإنتاجهما ليس إصلاح كود بل مستندان يلزم اعتمادهما — وادّعاء إنتاجهما
    أسوأ من غيابهما. ويسقط هذا الحارس متى أُضيف القالب، فيُذكِّر بإكمال
    الشقّ الثاني.
    """
    docs = getattr(R, "CANONICAL_DOCUMENTS", {})
    assert {"OD-012", "OD-013"} <= set(docs), "خرجا من كتالوج المستندات"
    for od in ("OD-012", "OD-013"):
        tpl = [k for k, v in R.LEGACY_PRN_ALIASES.items()
               if isinstance(v, dict) and v.get("canonical") == od]
        assert not tpl, (
            f"صار لـ{od} قالب ({tpl}) — أكمل توليده في مسار السفر"
        )
