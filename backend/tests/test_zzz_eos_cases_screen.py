# -*- coding: utf-8 -*-
"""P6-27 — شاشة معاملات نهاية الخدمة: ما تعرضه هو ما يقبله الخادم.

**قرار المالك**: حالة نهاية الخدمة هي المرجع. وكان المرجع **بلا شاشة
إطلاًقا**: ثمانية نقاط نهاية تسوق المعاملة من الفتح إلى الحفظ، ولا
واجهة تصل إليها. والمعروض الوحيد صفحة ``/eos`` — وهي **حاسبة تقديرية**
تستدعي ``/eos/for-employee`` ولا تلمس المعاملة.

فمن أراد إنهاء خدمة لم يجد إلا المسودة على ملف الموظف، وهي المسار الذي
قرّر المالك ألّا يكون المرجع.

**والصلاحيات تُقرأ من الخادم لا تُحسب في الواجهة** (درس APP-01): منطق
صلاحيات مكرَّر في مكانين ينحرف أحدهما، فيظهر زرّ يرفضه الخادم أو يُخفى
إجراء يملكه صاحبه. فالشاشة تقرأ ``/eos/cases/stage-roles``.

وهذه الاختبارات تقيس **العقد** الذي تعتمد عليه الشاشة: أن ما تقرؤه
موجود، وأن ما تعرضه من صلاحيات هو ما يفرضه الخادم بالضبط.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from app.routers import eos as eos_router
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
ACC = ("100000000007", "account123")
EMP = ("100000000101", "emp12345")

SCREEN = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
          / "EosCases.tsx")


@pytest.fixture
def a_case(client):
    """معاملة مفتوحة يُقاس عليها، ثم تُنظَّف."""
    db = SessionLocal()
    eid = None
    try:
        hr = db.scalar(select(models.User).where(models.User.civil_id == HR[0]))
        eid = db.scalar(select(models.Employee.id).where(
            models.Employee.company_id == hr.company_id,
            models.Employee.status == "active",
            models.Employee.non_payroll.is_(False)).order_by(
                models.Employee.id.desc()))
        db.execute(sa_delete(models.EosCase).where(
            models.EosCase.employee_id == eid))
        db.commit()
        r = client.post("/api/eos/cases", headers=auth_headers(login(client, *HR)),
                        params={"employee_id": eid, "termination_date": "2027-06-01",
                                "reason": "resignation"})
        assert r.status_code == 201, r.text[:200]
        yield r.json()
    finally:
        db.execute(sa_delete(models.EosCase).where(
            models.EosCase.employee_id == eid))
        db.commit()
        db.close()


def test_the_screen_exists_and_reads_the_case_endpoints():
    """خطّ الأساس: الشاشة موجودة وتخاطب المعاملة لا الحاسبة."""
    assert SCREEN.exists(), "لا شاشة لمعاملات نهاية الخدمة"
    text = SCREEN.read_text(encoding="utf-8")
    assert "/eos/cases" in text, "الشاشة لا تقرأ المعاملات"
    assert "/eos/for-employee" not in text, (
        "الشاشة تستدعي الحاسبة التقديرية — وهي ليست المرجع"
    )


def test_the_screen_does_not_compute_permissions_itself():
    """**درس APP-01**: قائمة أدوار مكتوبة في الواجهة تنحرف عن الخادم."""
    text = SCREEN.read_text(encoding="utf-8")
    assert "/eos/cases/stage-roles" in text, (
        "الشاشة لا تقرأ سياسة الأدوار من الخادم"
    )
    for role in ('"accountant"', '"company_manager"', '"hr"'):
        assert role not in text, (
            f"الشاشة تحمل قائمة أدوار خاصة بها ({role}) — نسخة ثانية تنحرف"
        )


def test_the_policy_endpoint_matches_what_the_server_enforces(client):
    """وما تعلنه السياسة هو ما يفرضه ``_require_role`` بالضبط."""
    hdr = auth_headers(login(client, *HR))
    r = client.get("/api/eos/cases/stage-roles", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["flow"] == eos_router.EOS_FLOW, body["flow"]
    declared = {k: set(v) for k, v in body["roles"].items()}
    actual = {k: set(v) for k, v in eos_router._STAGE_ROLES.items()}
    assert declared == actual, f"معلَن: {declared} · مفروض: {actual}"
    assert body["you"] == "hr", body["you"]


def test_a_case_carries_its_origin_to_the_screen(client, a_case):
    """**الرابط يصل إلى الشاشة**: عمود بلا قارئ يعيد العطل الذي أُصلح."""
    assert "source_request_id" in a_case, sorted(a_case)
    assert a_case["source_request_id"] is None, (
        "فُتحت مباشرة فلا مصدر — والقيمة تقول ذلك صراحًة"
    )
    text = SCREEN.read_text(encoding="utf-8")
    assert "source_request_id" in text, "الشاشة لا تعرض أصل المعاملة"


def test_the_list_shows_what_the_screen_needs(client, a_case):
    """وما تعرضه الشاشة موجود في الردّ — لا حقل تخترعه."""
    hdr = auth_headers(login(client, *HR))
    rows = client.get("/api/eos/cases", headers=hdr).json()
    assert rows, "القائمة فارغة رغم وجود معاملة"
    row = next(c for c in rows if c["id"] == a_case["id"])
    for key in ("reference_no", "employee_name", "termination_date", "status",
                "stage_index", "total_stages", "source_request_id"):
        assert key in row, f"«{key}» غائب عن ردّ القائمة"


def test_the_status_filter_the_screen_sends_works(client, a_case):
    """والتصفية التي ترسلها الشاشة مقبولة على الخادم."""
    hdr = auth_headers(login(client, *HR))
    hit = client.get("/api/eos/cases", headers=hdr,
                     params={"status": "initiated"}).json()
    assert any(c["id"] == a_case["id"] for c in hit), "التصفية لا تُرجع المعاملة"
    miss = client.get("/api/eos/cases", headers=hdr,
                      params={"status": "settled"}).json()
    assert not any(c["id"] == a_case["id"] for c in miss), (
        "التصفية تُرجع معاملة بحالة أخرى"
    )


def test_the_next_step_the_screen_offers_is_the_one_the_server_accepts(client, a_case):
    """**جوهر APP-01**: ما تعرضه الشاشة هو ما يقبله الخادم.

    الخطوة التالية بعد ``initiated`` هي ``calculated``، والسياسة تقول
    إنها للمحاسب. فتُقبَل منه وتُرفَض من غيره — والشاشة تعرضها له وحده.
    """
    policy = client.get("/api/eos/cases/stage-roles",
                        headers=auth_headers(login(client, *HR))).json()
    flow = policy["flow"]
    nxt = flow[flow.index("initiated") + 1]
    assert nxt == "calculated", nxt
    assert "accountant" in policy["roles"][nxt], policy["roles"][nxt]

    # من ليس في القائمة يُرفض — فإخفاء الزرّ عنه يطابق الخادم.
    denied = client.post(f"/api/eos/cases/{a_case['id']}/calculate",
                         headers=auth_headers(login(client, *HR)),
                         params={"used_leave_days": 0})
    assert denied.status_code in (403, 409), denied.status_code

    allowed = client.post(f"/api/eos/cases/{a_case['id']}/calculate",
                          headers=auth_headers(login(client, *ACC)),
                          params={"used_leave_days": 0})
    assert allowed.status_code == 200, allowed.text[:200]
    assert allowed.json()["status"] == "calculated"


def test_the_screen_is_reachable_only_where_the_server_allows(client):
    """والحارس في التوجيه هو صلاحية القائمة نفسها، لا أشدّ ولا أرخى."""
    app_tsx = (Path(__file__).resolve().parents[2] / "frontend" / "src"
               / "App.tsx").read_text(encoding="utf-8")
    # سطر **التوجيه** لا سطر التنقّل: أول كتابة قسمت على "/eos/cases"
    # فأمسكت رابط القائمة الجانبية، وحارسه مكتوب بصيغة أخرى.
    route = 'path="/eos/cases"'
    assert route in app_tsx, "الشاشة بلا مسار"
    after = app_tsx.split(route, 1)[1][:220]
    assert 'a.can("view_employee")' in after, (
        f"حارس المسار لا يطابق صلاحية القائمة على الخادم: {after[:120]}"
    )

    # ومن لا يملكها يُرفض على الخادم أيًضا — فالإخفاء ليس الحماية الوحيدة.
    r = client.get("/api/eos/cases", headers=auth_headers(login(client, *EMP)))
    assert r.status_code == 403, r.status_code
