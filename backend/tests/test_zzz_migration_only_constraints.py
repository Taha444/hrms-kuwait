# -*- coding: utf-8 -*-
"""قيٌد في الترحيل وحده — يمرُّ أخضَر في الاختبار ويسقط في الإنتاج.

**الدرُس مكتوٌب في ``models.py``** عند ``uq_tasks_open_dedup``: ``conftest``
يبني قاعدَة الاختبار بـ``Base.metadata.create_all`` من **المخطَّط**، لا
بـ``alembic``. فقيٌد يُنشئه ترحيٌل ولا يُعلنه نموٌذج **غيُر موجوٍد في
الاختبارات أصًلا** — وكلُّ سباٍق يعتمد عليه يمرُّ أخضَر ثم ينهار على قاعدة
العميل.

**والقياُس ذهب في الاتجاهين:**

- أربعَة عشر قيًدا مسمًّى في النماذج: **كلُّها مُرحَّلة** (صفُر غياب).
- وستُة قيود تفرٍُّد تُنشَأ في الترحيلات: أربعٌة **يراها المخطَّط فعًلا**
  لأن ``unique=True`` على العمود يُنشئ قيًدا (بلا اسم) — فالاسُم وحده كان
  في الترحيل، ومنها ``request_documents.reference_no`` الذي أسقط حارًسا
  فعًلا في السويت. **واثنان لا يراهما المخطَّط:**

  * ``feature_flags(key, company_id)`` — تفرٌُّد **مركَّب**، ولا يُعبِّر
    عنه علُم عمود. و``set_flag`` قراءٌة ثم كتابة.
  * ``companies.commercial_reg`` — وله فحٌص تطبيقيٌّ قبل الكتابة
    (``_check_commercial_reg_unique``)، **والفحُص لا يرى الطلَب الموازي**:
    شركتان بسجٍّل تجاريٍّ واحد تُقيَّد عمالُة إحداهما على الأخرى عند الجهات.

**والحسُم يختلف بحسب معنى الفعل**: إنشاُء شركٍة **يُردّ** (409 بالرسالة
التي يقولها الفحُص نفسه — فقيٌد يردُّ خمسمئة يُبادل تسابًقا بانهيار)؛
وضبُط علٍَم **يُعاد قراءتُه** ويستقرُّ على قيمة — فالمقصوُد أن يُضبَط، لا
أن يفشل أحُد النداءين.
"""
from __future__ import annotations

import pathlib
import re

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import models
from app.database import SessionLocal

MIG = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions"


# ---------------------------------------------------------------------------
# القياُس البنيوي — في الاتجاهين
# ---------------------------------------------------------------------------

def _migration_blob() -> str:
    return "".join(p.read_text(encoding="utf-8", errors="ignore")
                   for p in MIG.glob("*.py"))


def test_every_named_constraint_in_the_models_is_migrated():
    """نموٌذج يُعلن قيًدا وترحيٌل ال يُنشئه = قاعدُة عميٍل بال قيد."""
    src = (pathlib.Path(__file__).resolve().parents[1] / "app" / "models.py"
           ).read_text(encoding="utf-8")
    declared = set(re.findall(
        r'UniqueConstraint\([^)]*name\s*=\s*["\']([\w]+)["\']', src))
    declared |= set(re.findall(r'Index\(\s*["\']([\w]+)["\']', src))
    blob = _migration_blob()
    missing = sorted(n for n in declared if n not in blob)
    assert not missing, f"قيوٌد معلَنٌة وال ترحيَل لها: {missing}"


def test_every_uniqueness_a_migration_creates_is_visible_to_the_schema():
    """**الاتجاُه الآخر، وهو األخطر**: ما ال يراه المخطَُّط ال تراه الاختبارات.

    ويُقاس على **المخطَّط نفسه** ال على نصّ النماذج: قيُد عموٍد بال اسم
    يفرض التفرَُّد وإن لم يُسمَّ — فالمقيُس هو الفرُض، ال التسمية.
    """
    blob = _migration_blob()
    names: list[tuple[str, list[str]]] = []
    for m in re.finditer(r'create_unique_constraint\(\s*["\'][\w]+["\']\s*,\s*'
                         r'["\'](\w+)["\']\s*,\s*\[([^\]]*)\]', blob):
        names.append((m.group(1), re.findall(r'["\'](\w+)["\']', m.group(2))))
    for m in re.finditer(r'create_index\(\s*["\'][\w]+["\']\s*,\s*["\'](\w+)["\']\s*,\s*'
                         r'\[([^\]]*)\][^)]*unique\s*=\s*True', blob, re.S):
        names.append((m.group(1), re.findall(r'["\'](\w+)["\']', m.group(2))))

    assert names, "القياُس ال يرى قيَد تفرٍُّد واحًدا في الترحيالت — صار أعمى"

    unseen = []
    for table, cols in names:
        t = models.Base.metadata.tables.get(table)
        if t is None or not cols:
            continue
        enforced = any(c.unique for c in (t.c.get(x) for x in cols) if c is not None)
        for uc in t.constraints:
            if uc.__class__.__name__ == "UniqueConstraint" and \
                    sorted(x.name for x in uc.columns) == sorted(cols):
                enforced = True
        for ix in t.indexes:
            if ix.unique and sorted(x.name for x in ix.columns) == sorted(cols):
                enforced = True
        if not enforced:
            unseen.append(f"{table}{tuple(cols)}")
    assert not unseen, ("تفرٌُّد يفرضه ترحيٌل وال يراه المخطَّط — فالاختباراُت "
                        f"ال تراه:\n  " + "\n  ".join(unseen))


# ---------------------------------------------------------------------------
# والأثُر يُقاس في القاعدة
# ---------------------------------------------------------------------------

def test_two_companies_cannot_share_one_commercial_register():
    """**والقفُل في القاعدة ال في الفحص** — فالفحُص ال يرى الموازي."""
    db = SessionLocal()
    made = []
    try:
        cr = "ZZZ-CR-قياس-1"
        a = models.Company(name="شركُة قياٍس أولى", commercial_reg=cr)
        db.add(a)
        db.commit()
        made.append(a.id)
        b = models.Company(name="شركُة قياٍس ثانية", commercial_reg=cr)
        db.add(b)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.rollback()
        for cid in made:
            db.execute(models.Company.__table__.delete().where(
                models.Company.id == cid))
        db.commit()
        db.close()


def test_the_api_answers_a_duplicate_register_with_a_readable_conflict(client):
    """**وقيٌد يردُّ خمسمئة يُبادل تسابًقا بانهيار** — فيُترجَم إلى ٤٠٩.

    والرسالُة هي التي يقولها الفحُص التطبيقي نفسه، فال نصّان لقاعدٍة واحدة.
    """
    from tests.conftest import auth_headers, login

    h = auth_headers(login(client, "000000000000", "admin123"))
    cr = "ZZZ-CR-قياس-2"
    made = []
    try:
        first = client.post("/api/companies", json={"name": "قياٌس أول",
                                                    "commercial_reg": cr}, headers=h)
        assert first.status_code in (200, 201), first.text[:250]
        made.append(first.json().get("id"))
        second = client.post("/api/companies", json={"name": "قياٌس ثان",
                                                     "commercial_reg": cr}, headers=h)
        assert second.status_code == 409, (second.status_code, second.text[:250])
        assert "السجل التجاري" in second.text
    finally:
        db = SessionLocal()
        try:
            for cid in [x for x in made if x]:
                db.execute(models.Company.__table__.delete().where(
                    models.Company.id == cid))
            db.commit()
        finally:
            db.close()


def test_setting_the_same_flag_twice_settles_on_a_value():
    """**وضبُط علٍَم مرّتين يستقرُّ ال ينهار** — فالمقصوُد أن يُضبَط.

    والصفُّ الثاني ال يُنشأ: ``uq_feature_flags_key_company`` يمنعه،
    و``set_flag`` يُعيد القراءَة فيُحدِّث.
    """
    from app import feature_flags as F

    key = next(iter(F.REGISTRY))
    db = SessionLocal()
    try:
        F.set_flag(db, key, "on", company_id=1)
        F.set_flag(db, key, "off", company_id=1)
        rows = db.scalars(select(models.FeatureFlag).where(
            models.FeatureFlag.key == key,
            models.FeatureFlag.company_id == 1)).all()
        assert len(rows) == 1, [(r.id, r.value) for r in rows]
        assert rows[0].value == "off", rows[0].value
    finally:
        db.execute(models.FeatureFlag.__table__.delete().where(
            models.FeatureFlag.key == key,
            models.FeatureFlag.company_id == 1))
        db.commit()
        db.close()
