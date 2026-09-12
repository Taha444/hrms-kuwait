# -*- coding: utf-8 -*-
"""بحٌث يعمل محلًّيا ويفشل في اإلنتاج — حساسيُة الحالة تختلف بين المحرّكين.

``LIKE`` في SQLite **ال يميّز حالَة الحروف** ألحرف ASCII، وفي PostgreSQL
**يميّزها**. والسويُت تجري على SQLite — **فال اختباَر يمسك هذا أبًدا**.

وهو الصنُف الرابُع من نوعه في هذه الجولة:

1. ترويسٌة ال تُكشَف إال عبر األصول (``expose_headers``) — والاختباُر
   يقرأها ألنه بال أصٍل متقاطع.
2. ساعُة مضيٍف تُقارَن بـ``UTC`` — والاختباُر يجري في بيئٍة واحدة.
3. كتالوٌج نسختُه في القاعدة هي التي تعمل — و``conftest`` يبذر من جديد.
4. **وهذا**: محرُّك الاختبار ال يُفرِّق ما يُفرِّقه محرُّك الإنتاج.

**واألثُر يمسّ ما فيه حروٌف التينية**: رقُم الجواز (``A9988776``) ورقُم
الترخيص ورقُم الملف والسجلُّ التجاري. فمن يكتب ``a9988776`` في البحث العامّ
**ال يجد شيًئا في اإلنتاج ويجده محلًّيا**.

**والدليُل ال يُؤخَذ من القاعدة المحلّية**: قيس أن ``like`` و``ilike``
يُعيدان الصَّف نفسه على SQLite في الحالتين — فالمحرُّك ال يُظهر الفرق.
فيُقاس **ما يُرسَل إلى Postgres**: ``ILIKE`` ال ``LIKE``.

**وما لم يُحوَّل بقصد**: بصماُت المهامّ (``dedup_key``) وبوادُئ األرقام
(``employee_no`` · ``reference_no``) ومفتاُح حسابات القياس — مفاتيُح
داخلية **حسّاسٌة بحّق**، وتخفيُف حساسيّتها يجعل بصمتين مختلفتين واحدة.
"""
from __future__ import annotations

import inspect

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app import models


def _pg(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect())).upper()


def test_postgres_receives_a_case_insensitive_comparison():
    """**جوهر البند**: ما يُرسَل إلى محرّك اإلنتاج ال يميّز الحالة."""
    stmt = select(models.Employee).where(
        models.Employee.passport_number.ilike("%a1%"))
    sql = _pg(stmt)
    assert "ILIKE" in sql, sql[-120:]
    assert " LIKE " not in sql.replace("ILIKE", ""), sql[-120:]


def test_the_local_engine_cannot_prove_this_defect():
    """**وافتراُض القياس يُثبَّت**: SQLite ال يُفرِّق، فال يُؤخَذ منه دليل.

    فلو صار محرُّك الاختبار يميّز الحالة، تغيّر شكُل العطل ووجب إعادُة
    النظر في هذا الملف — ال أن يمضي وهو يقيس ما لم يبقَ.
    """
    from app.database import SessionLocal, _IS_SQLITE

    if not _IS_SQLITE:
        import pytest
        pytest.skip("القاعدُة ليست SQLite — يُقاس األثُر مباشرًة")

    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1))
        if emp is None:
            import pytest
            pytest.skip("ال موظَف في هذه القاعدة")
        was = emp.passport_number
        emp.passport_number = "A9988776"
        db.commit()
        try:
            lower = len(db.scalars(select(models.Employee).where(
                models.Employee.passport_number.like("%a9988776%"))).all())
        finally:
            emp.passport_number = was
            db.commit()
    finally:
        db.close()
    assert lower == 1, (
        "صار محرُّك الاختبار يميّز الحالة — يُعاد النظر في هذا الملف")


def test_user_facing_search_is_case_insensitive():
    """والبحُث الذي يكتبه المستخدم يُقارَن بال حساسيّة — في موضعيه."""
    from app.routers import employees as E, search as S

    for mod in (S, E):
        src = inspect.getsource(mod)
        assert ".like(like)" not in src, f"{mod.__name__}: بحٌث حسّاٌس للحالة"
        assert ".ilike(like)" in src, f"{mod.__name__}: ال بحَث أصًلا"


def test_internal_keys_stay_case_sensitive():
    """**ومفتاٌح داخلٌي تُخفَّف حساسيّتُه تصير بصمتان واحدة.**

    ``dedup_key`` يمنع تكراَر مهمٍة، و``employee_no`` يُولَّد ببادئة
    التينية. فمقارنٌة بال حساسيّة تجمع ما فرَّقه النظاُم قصًدا.
    """
    import pathlib

    app = pathlib.Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for p in app.rglob("*.py"):
        body = p.read_text(encoding="utf-8")
        for key in ("dedup_key.ilike", "employee_no.ilike",
                    "reference_no.ilike", "civil_id.ilike("):
            if key in body:
                offenders.append(f"{p.name}:{key}")
    # ``civil_id`` أرقاٌم فال حالَة له — يُستثنى إن ظهر في البحث العامّ.
    offenders = [o for o in offenders if "civil_id" not in o]
    assert not offenders, offenders


# ---------------------------------------------------------------------------
# وطوُل العمود: SQLite يتجاهله وPostgreSQL يفرضه
# ---------------------------------------------------------------------------

def test_a_too_long_value_is_a_clear_400_not_a_confusing_404():
    """**و``DataError`` يجمع عطلين مختلفين — فال يُردّان بجواٍب واحد.**

    على PostgreSQL يرفعه ``NumericValueOutOfRange`` (معرٌِّف خارج مدى
    العمود) **و**``StringDataRightTruncation`` (قيمٌة أطوُل من حقلها).
    واألوُل «سجٌّل غير موجود» بحّق؛ والثاني ليس كذلك: من كتب رمَز فرٍع
    بسبعة أحرف يُقال له «السجلّ غير موجود» **فال يفهم ما فعل** ويُعيد
    المحاولة بالقيمة نفسها.

    وال يُقاس هذا على القاعدة المحلّية: **SQLite يتجاهل طوَل العمود** فال
    يرفع شيًئا. فيُقاس املعالُج نفسه بخطٍأ مُركَّب.
    """
    import app.main as M

    class _Orig(Exception):
        pass

    _Orig.__name__ = "StringDataRightTruncation"

    class _Err(Exception):
        def __init__(self):
            self.orig = _Orig()

    r = M._out_of_range_response(None, _Err())
    assert r.status_code == 400, r.status_code
    body = r.body.decode("utf-8")
    assert "أطوُل" in body or "أطول" in body, body

    # واملدى العددي يبقى 404 — فال يُبدَّل عطٌل بعطل.
    assert M._out_of_range_response(None, OverflowError("x")).status_code == 404


def test_the_narrowest_free_text_input_is_capped_at_its_column():
    """**وحٌدّ عند املدخل يسمّي الحقَل، واملركزُّي يُنجي من الخمسمئة.**

    ``Branch.code`` عمودُه ستُة أحرف وهو **أضيُق مدخٍل حٍّر في النظام**،
    ويدخل **الرقَم الوظيفي** لكل موظٍف في الفرع. فسبعُة أحرٍف كانت تُحفَظ
    محلًّيا وتُسقِط الطلَب في اإلنتاج.
    """
    import pydantic

    from app import schemas

    for cls in (schemas.BranchIn, schemas.BranchUpdate):
        f = cls.model_fields["code"]
        limits = [getattr(md, "max_length", None) for md in (f.metadata or [])]
        assert 6 in [x for x in limits if x], (cls.__name__, limits)

    try:
        schemas.BranchIn(name="فرع", code="ABCDEFG")
    except pydantic.ValidationError as exc:
        assert "code" in str(exc)
    else:
        raise AssertionError("قُبِلت سبعُة أحرف — الحدُّ ال يعمل")


def test_the_column_limit_is_read_not_assumed():
    """**والحدُّ من العمود ال من الذاكرة** — فلو وُسِّع العمود سقط الحارس.

    فحٌدّ مكتوٌب بالي;د يصير أضيَق من عموده بعد ترحيٍل، فيرفض ما تقبله
    القاعدة.
    """
    from app import models, schemas

    col = models.Branch.__table__.c.code
    declared = int(str(col.type)[8:-1])
    f = schemas.BranchIn.model_fields["code"]
    limits = [x for x in (getattr(md, "max_length", None)
                          for md in (f.metadata or [])) if x]
    assert limits and limits[0] == declared, (limits, declared)
