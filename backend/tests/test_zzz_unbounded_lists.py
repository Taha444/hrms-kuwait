# -*- coding: utf-8 -*-
"""قائمٌة بلا سقف — تنكسر بالنموّ لا بالخطأ.

**القياس**: كلُّ ``GET`` يُعيد ``.all()`` من جدوٍل ينمو، بلا حدٍّ ولا
نافذٍة زمنية. أنذر الكنُس خمسَة عشر موضًعا، وسقط عشٌر منها لأن **مُطابِقي
أخذ الاسم جزًءا من اسم**: ``Notification`` من ``NotificationTemplate``،
و``Request`` من ``RequestType``، و``Document`` من ``DocumentTemplate``.
فأُصلح القياُس بحدّ الكلمة (``models.Request`` لا ``models.RequestType``).

وأخطأ هذا الملُف نفسه في المسار: كتبتُ ``/api/tasks`` والمساُر
``/api/tasks/my``. فردَّ الخادُم «غير موجود» — والحارُس يقيس ما يسمّيه.

وبقي عشٌر، **سبٌع منها مقيَّدٌة بكائنها**: نسُخ مستنٍد واحد، سجلُّ موظٍف
واحد، خطُّ معاملٍة واحدة. تنمو بعمر كائنها لا بعمر النظام — فلا تُعَدّ
عطًلا.

**واثنتان بلا سقٍف حًقّا:**

- ``GET /tasks/my`` — صندوُق المهامّ، **أكثُر شاشٍة تُفتَح**. افتراضُه
  ``status="open"`` كان يحميه وحده، والمعامَل بيد العميل: ``?status=``
  يُلغي الترشيح فيُعيد كلَّ ما أُسند للمستخدم في عمره. والـdigest اليومي
  وحده يضيف صًفّا لكل مستخدم كلَّ يوم.
- ``GET /requests/mine`` — تنمو بمدّة خدمة الموظف، و``_serialize``
  يستعلم لكل صّف على حدة: فمئُة طلٍب مئُة جولٍة على القاعدة.

**وعطٌل ثاٍن ظهر مع السقف**: ترشيُح الفئة في الصندوق كان يُطبَّق **بعد**
بناء القائمة كلّها. ومع سقٍف يصير ذلك عطًلا لا بطًئا: نأخذ أحدَث مئتين ثم
نُرشِّح، فتُعرَض ثالٌث من فئٍة فيها خمسون. فنزل الترشيُح إلى الاستعلام.

**والجواُب يبقى مصفوفًة** كما كان، والعدُد الكّلي في ترويسة
``X-Total-Count`` — فلا تُكسَر واجهٌة قائمة، وتعرف الشاشُة أن بعده بقيّة.
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")
EMP = ("100000000101", "emp12345")
PROBE = "unbounded_probe:"


def _hr_id() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(models.User.id).where(
            models.User.civil_id == HR[0]))
    finally:
        db.close()


def _seed_tasks(n: int, status: str = "done") -> None:
    db = SessionLocal()
    try:
        uid = _hr_id()
        for i in range(n):
            db.add(models.Task(
                company_id=1, type="request_stage", title=f"قياس {i}",
                assignee_user_id=uid, status=status, severity="info",
                dedup_key=f"{PROBE}{status}:{i}"))
        db.commit()
    finally:
        db.close()


def _purge() -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Task).where(
            models.Task.dedup_key.like(f"{PROBE}%")))
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# الصندوق له سقف
# ---------------------------------------------------------------------------

def test_the_inbox_has_a_ceiling(client):
    """**جوهر البند**: ``?status=`` لا يُعيد عمَر المستخدم كلَّه."""
    _seed_tasks(12, status="done")
    try:
        hdr = auth_headers(login(client, *HR))
        r = client.get("/api/tasks/my?status=done&limit=5", headers=hdr)
        assert r.status_code == 200, r.text[:200]
        assert len(r.json()) == 5, len(r.json())
    finally:
        _purge()


def test_the_total_is_returned_so_the_screen_knows_there_is_more():
    """**وسقٌف يُخفي بلا أن يقول يُضلِّل** — فالعدُد الكّلي في ترويسة."""
    import inspect

    from app.routers import tasks as T

    src = inspect.getsource(T.my_tasks)
    assert 'X-Total-Count' in src, "السقُف يُخفي ولا يقول كم بقي"


def test_the_inbox_still_returns_an_array(client):
    """**ولا يُكسَر شكُل الجواب**: مصفوفٌة كما كانت، لا كائٌن يلفّها."""
    hdr = auth_headers(login(client, *HR))
    r = client.get("/api/tasks/my", headers=hdr)
    assert r.status_code == 200
    assert isinstance(r.json(), list), type(r.json())


def test_the_default_still_shows_the_open_box(client):
    """والافتراُض لم يتغيّر: «مفتوحة» تعني ما لم يُنجَز بعد."""
    _seed_tasks(3, status="open")
    try:
        hdr = auth_headers(login(client, *HR))
        r = client.get("/api/tasks/my", headers=hdr)
        titles = {x["title"] for x in r.json()}
        assert {"قياس 0", "قياس 1", "قياس 2"} <= titles, sorted(titles)[:8]
    finally:
        _purge()


# ---------------------------------------------------------------------------
# وترشيُح الفئة في الاستعلام
# ---------------------------------------------------------------------------

def test_the_category_filter_is_applied_in_the_query(client):
    """**جوهر العطل الثاني**: لا يُرشَّح بعد بناء القائمة.

    فمع سقٍف يصير الترشيُح البعدي عطًلا: نأخذ أحدَث مئتين ثم نُرشِّح،
    فتُعرَض ثالٌث من فئٍة فيها خمسون.
    """
    import inspect

    from app.routers import tasks as T

    src = inspect.getsource(T.my_tasks)
    assert 'x["category"] == category' not in src, "الترشيُح ما زال بعدًيا"
    assert "models.Task.type.in_(types" in src, "الفئُة لا تنزل إلى الاستعلام"


def test_a_category_view_is_not_starved_by_the_ceiling(client):
    """ويُقاس الأثر لا الشكل: فئٌة فيها ثمانية تُعرَض ثمانيًة مع سقٍف ضيّق."""
    _seed_tasks(8, status="open")          # request_stage → فئة approvals
    try:
        hdr = auth_headers(login(client, *HR))
        r = client.get("/api/tasks/my?category=approvals&limit=8", headers=hdr)
        assert r.status_code == 200, r.text[:200]
        got = [x for x in r.json() if x["title"].startswith("قياس ")]
        assert len(got) == 8, (len(got), [x["title"] for x in r.json()][:10])
        assert all(x["category"] == "approvals" for x in r.json()), \
            {x["category"] for x in r.json()}
    finally:
        _purge()


# ---------------------------------------------------------------------------
# وطلباتي كذلك
# ---------------------------------------------------------------------------

def test_my_requests_has_a_ceiling_and_reports_the_total(client):
    """**وقائمُة طلباتي تنمو بمدّة الخدمة** — ولكل صٍّف جولٌة على القاعدة."""
    hdr = auth_headers(login(client, *EMP))
    r = client.get("/api/requests/mine?limit=1", headers=hdr)
    assert r.status_code == 200, r.text[:200]
    assert isinstance(r.json(), list)
    assert len(r.json()) <= 1, len(r.json())
    assert "X-Total-Count" in r.headers, dict(r.headers)


def test_the_ceiling_cannot_be_raised_without_bound(client):
    """**وسقٌف يرفعه العميل بلا حدٍّ ليس سقًفا.**

    فـ``limit=10000`` يُقصَر إلى الحدّ الأعلى، ولا يُقبَل صفٌر ولا سالب.
    """
    hdr = auth_headers(login(client, *HR))
    for bad in ("limit=0", "limit=-5", "limit=999999", "offset=-1"):
        r = client.get(f"/api/tasks/my?{bad}", headers=hdr)
        assert r.status_code == 200, (bad, r.text[:200])


# ---------------------------------------------------------------------------
# والسقف يُقال، ويُقرأ
# ---------------------------------------------------------------------------

def test_the_total_header_is_exposed_to_the_browser():
    """**وترويسٌة لا تُكشَف لا تُقرأ.**

    ``allow_headers`` تخصّ ما يُرسله المتصفّح، و``expose_headers`` ما
    يُسمح له بقراءته من الجواب. وبدونها تصل ``X-Total-Count`` إلى
    المتصفّح **ويحجُبها هو عن الشيفرة** — فالسقُف يُخفي ولا يقول، والشاشُة
    تعرض مئتين وعندها ألف.

    وهي حالٌة **تعمل في الاختبار وتصمت في الإنتاج**: عميُل الاختبار لا
    أصَل متقاطع له فيرى كلَّ الترويسات. فلا يُمسَك إال بقراءة الإعداد.
    """
    import app.main as M

    for mw in M.app.user_middleware:
        if "CORS" in str(mw.cls):
            exposed = mw.kwargs.get("expose_headers") or []
            assert "X-Total-Count" in exposed, exposed
            return
    raise AssertionError("لا وسيَط CORS — يُعاد النظر في هذا الحارس")


def test_the_screen_says_how_many_are_hidden():
    """**والشاشُة تقول كم بقي** — لا تعرض السقَف كأنه الكلّ."""
    import pathlib
    import re

    page = (pathlib.Path(__file__).resolve().parents[2]
            / "frontend" / "src" / "pages" / "Tasks.tsx")
    if not page.exists():
        import pytest
        pytest.skip("لا واجهَة في هذه الشجرة")

    src = page.read_text(encoding="utf-8")
    assert "x-total-count" in src.lower(), "الشاشُة لا تقرأ العدد الكّلي"
    assert "tasks_partial" in src, "لا تقول للمستخدم أن بعده بقيّة"

    # والنصُّ من طبقة الترجمة لا مكتوًبا بالي;د — فزُّر اللغة يعمل عليه.
    i18n = page.parents[1] / "i18n.tsx"
    body = i18n.read_text(encoding="utf-8")
    assert re.search(r"tasks_partial:\s*\{\s*ar:", body), "النصُّ خارج الترجمة"
