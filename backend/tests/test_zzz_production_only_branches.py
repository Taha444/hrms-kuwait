# -*- coding: utf-8 -*-
"""فرٌع ال يعمل إال في اإلنتاج — ال يُجرَّب إال يوَم الحاجة.

الصنُف السادُس من «يعمل محلًّيا ويفشل في اإلنتاج». وهو أخبثُها: **حاٌرس
مكتوٌب لحالٍة ال تقع في االختبار أبًدا**، فإن كان معطوًبا لم يُعلَم إال
حين يُعتمَد عليه.

**وقيس: خمسَة عشر فرًعا إنتاجًيا في التطبيق**، وأخطرُها
``POST /admin/reset-demo-data`` — **يمسح قاعدَة العميل كلَّها**. وكان
حارسُه الوحيد::

    assert "ERASE-ALL-DATA" in src, "المسح في الإنتاج بال تأكيد صريح"

**أي أنه يقرأ الشيفرَة وال يُجرِّب الفرع.** فيمرّ أخضَر لو:

- عُكست املقارنة (``==`` مكان ``!=``)،
- أو لم يُقرأ ``confirm`` من الطلب أصًلا،
- أو تقدَّمت البوّابُة الثانية فأذنت قبل التأكيد،
- أو انكسرت مقارنُة الحالة (``upper()``).

فيُجرَّب الفرُع هنا **بحاالت الرفض وحدها**: ال يُمرَّر تأكيٌد صحيح مع
إذٍن مفتوح في اختبار — فذلك يمسح قاعدَة السويت، **واختباٌر يُفسِد بيئته
أسوأ من العطل الذي يبحث عنه**.
"""
from __future__ import annotations

import os

from sqlalchemy import func, select

from app import models
from app.config import settings
from app.database import SessionLocal
from tests.conftest import auth_headers, login

ADMIN = ("000000000000", "admin123")


def _rows() -> int:
    db = SessionLocal()
    try:
        return db.scalar(select(func.count()).select_from(models.Employee)) or 0
    finally:
        db.close()


def _force_production(monkeypatch) -> None:
    """اإلنتاُج مشتٌقّ من رابط القاعدة — فيُجبَر بالخاصيّة ال بالرابط."""
    monkeypatch.setattr(type(settings), "is_production",
                        property(lambda self: True))


def test_the_erase_refuses_in_production_without_confirmation(client, monkeypatch):
    """**جوهر البند**: الفرُع اإلنتاجي يُجرَّب ال يُقرأ.

    وال يُمسّ صٌّف واحد — يُقاس العدُد قبل وبعد.
    """
    before = _rows()
    _force_production(monkeypatch)
    hdr = auth_headers(login(client, *ADMIN))

    r = client.post("/api/admin/reset-demo-data", headers=hdr)
    assert r.status_code == 400, (r.status_code, r.text[:200])
    assert "ERASE-ALL-DATA" in r.text, r.text[:200]
    assert _rows() == before, "مُسِحت صفوٌف رغم الرفض"


def test_a_wrong_confirmation_is_not_enough(client, monkeypatch):
    """**وتأكيٌد قريٌب ليس تأكيًدا** — فالمقارنُة حرفيٌة ال تقريبية."""
    before = _rows()
    _force_production(monkeypatch)
    hdr = auth_headers(login(client, *ADMIN))

    for bad in ("erase", "ERASE", "ERASE-ALL", "ERASE_ALL_DATA", "نعم"):
        r = client.post(f"/api/admin/reset-demo-data?confirm={bad}", headers=hdr)
        assert r.status_code == 400, (bad, r.status_code, r.text[:150])
        assert _rows() == before, f"مُسِحت صفوٌف بتأكيٍد خاطئ: {bad}"


def test_the_second_gate_still_blocks_even_with_the_right_word(client, monkeypatch):
    """**وبوّابتان ال واحدة**: التأكيُد الصحيح ال يكفي بال إذٍن صريح.

    ``ALLOW_DEMO_RESET`` هو الباُب الثاني. ولو سقط أحدهما بقي اآلخر —
    وهو ما يُقاس هنا: تأكيٌد صحيح **وال إذن** ⇒ 403، وال صَّف يُمَسّ.
    """
    before = _rows()
    _force_production(monkeypatch)
    monkeypatch.delenv("ALLOW_DEMO_RESET", raising=False)
    hdr = auth_headers(login(client, *ADMIN))

    r = client.post("/api/admin/reset-demo-data?confirm=ERASE-ALL-DATA",
                    headers=hdr)
    assert r.status_code == 403, (r.status_code, r.text[:200])
    assert _rows() == before, "مُسِحت صفوٌف بال إذٍن صريح"


def test_development_needs_no_written_confirmation():
    """**وال يُشدَّد على التطوير بما يُشدَّد به على اإلنتاج.**

    فالتأكيُد المكتوب لحماية قاعدة عميل، و``_reset_allowed`` تسمح
    تلقائًيا في التطوير. ويُقاس بقراءة الشرط ال بتشغيل المسح — **فاختباٌر
    يمسح بيئَته يُفسِد ما بعده**.
    """
    import inspect

    from app.routers import admin as A

    src = inspect.getsource(A._reset_allowed)
    assert "if not settings.is_production" in src, src
    assert "ALLOW_DEMO_RESET" in src, src


def test_the_production_only_branches_are_counted_not_forgotten():
    """**وخمسَة عشر فرًعا إنتاجًيا تُعَدّ فال يُنسى واحد.**

    فهذا الملُّف يُجرِّب أخطرَها؛ وعدُدها يُقاس ليُرى إن نبت فرٌع جديد ال
    يُجرَّبه شيء.
    """
    import pathlib

    app = pathlib.Path(__file__).resolve().parents[1] / "app"
    hits = []
    for p in app.rglob("*.py"):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "is_production" in line and not line.strip().startswith("#"):
                hits.append(f"{p.name}:{i}")
    assert 10 <= len(hits) <= 25, (
        f"تغيّر عدُد الفروع الإنتاجية ({len(hits)}) — يُراجَع ما يُجرَّب منها:\n"
        + "\n".join(hits))
