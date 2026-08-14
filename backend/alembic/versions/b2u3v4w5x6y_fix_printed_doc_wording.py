# -*- coding: utf-8 -*-
"""QA-13 — تصحيح صياغة المستندات المطبوعة في القوالب القائمة.

ثلاثة عيوب تظهر في ورق رسمي يوقّعه الموظف ويقدّمه لجهة خارجية:

1) "د.ك د.ك" — قيمة الراتب كانت تحمل الوحدة، والقالب يكتبها بعدها. صارت
   القيمة رقًما مجرًدا (``templates.py``)، فمن كان يعتمد على الوحدة المضمَّنة
   ينتقل إلى ``{{basic_salary_kwd}}``. القاعدة ميكانيكية: إن جاورت الرمزَ
   كلمةُ وحدة — قبله أو بعده — فالجملة تكتب الوحدة بنفسها.

2) "شركة شركة الخليج" — القالب يكتب "شركة" ثم اسم الشركة الذي يبدأ بها.

3) النسخة الإنجليزية تطبع "KWD 1234.000 د.ك" — يعالجها (1) نفسه، فالوحدة
   هناك تسبق الرمز لا تتبعه.

الترحيل لازم لأن ``catalog_seed`` يُدرج ولا يُحدِّث: تصحيح النص في seed.py
لا يبلغ أي قاعدة قائمة. ولا تُلمس القوالب المخصّصة لشركة (company_id غير
فارغ) — نصّها قرار مالكها.

Revision ID: b2u3v4w5x6y
Revises: a1t2u3v4w5x
"""
import re

from alembic import op
import sqlalchemy as sa

revision = "b2u3v4w5x6y"
down_revision = "a1t2u3v4w5x"
branch_labels = None
depends_on = None

_UNIT = r"د\.ك|دينار|KD|KWD"
_SALARY = r"\{\{\s*basic_salary\s*\}\}"
# الوحدة تتبع الرمز (عربي: "1234 د.ك") أو تسبقه (إنجليزي: "KWD 1234")
_UNIT_AFTER = re.compile(_SALARY + r"(\s*(?:</strong>)?\s*)(" + _UNIT + r")")
_UNIT_BEFORE = re.compile(r"(" + _UNIT + r")(\s*(?:<strong>)?\s*)" + _SALARY)
_ANY_SALARY = re.compile(_SALARY)
# "شركة" زائدة قبل اسم الشركة (الاسم نفسه يبدأ بها)
_COMPANY_DUP = re.compile(r"شركة\s+(\{\{\s*company_name(?:_en)?\s*\}\})")

_KEEP = "@@KEEP_SALARY@@"

# خلايا النماذج المطبوعة تحمل الوحدة داخلها ("[____] /KWD") ثم تكرّرها في
# آخر الخلية ("... د.ك د.ك"). ونصّ إنجليزي انقلب حرفًيا: "/syaD" = "Days/".
# كلاهما أثر توليد أخطأ في اتجاه النص، ويظهر في 20 صًفا عبر عدة نماذج.
_CELL = re.compile(r"(<td[^>]*dir='rtl'[^>]*>)(.*?)(</td>)", re.S)
_TRAILING_UNIT = re.compile(r"(?:\s*(?:د\.ك|دينار|يوم|days?))+\s*$", re.I)
# وحدتان متلاصقتان في آخر الخلية = وحدتا حقلين مضغوطين في صف واحد
_TRAILING_REPEAT = re.compile(r"\s*(د\.ك|دينار|يوم|days?)(?:\s+\1)+\s*$", re.I)
_REVERSED_DAYS = re.compile(r"/syaD")


def _fix_cell(m: "re.Match[str]") -> str:
    open_tag, inner, close_tag = m.group(1), m.group(2), m.group(3)
    inner = _REVERSED_DAYS.sub("/Days", inner)
    # تكرار صريح للوحدة ⇒ يُحذف كله؛ ووحدة واحدة تُحذف فقط إن كانت مكتوبة
    # داخل الخلية أصلًا ("/KWD")، وإلا فقد تكون هي الوحدة الوحيدة الصحيحة.
    if _TRAILING_REPEAT.search(inner):
        inner = _TRAILING_REPEAT.sub("", inner)
    elif "/KWD" in inner or "/Days" in inner:
        inner = _TRAILING_UNIT.sub("", inner)
    return open_tag + inner + close_tag


def _fix(body: str) -> str:
    """يعيد النص بعد تصحيح الوحدة المكرَّرة واسم الشركة المكرَّر."""
    # نحمي المواضع التي تجاورها وحدة، ثم نحوّل ما بقي إلى المفتاح ذي الوحدة
    guarded = _UNIT_AFTER.sub(_KEEP + r"\1\2", body)
    guarded = _UNIT_BEFORE.sub(r"\1\2" + _KEEP, guarded)
    guarded = _ANY_SALARY.sub("{{basic_salary_kwd}}", guarded)
    out = guarded.replace(_KEEP, "{{basic_salary}}")
    out = _COMPANY_DUP.sub(r"\1", out)
    return _CELL.sub(_fix_cell, out)


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, body_html FROM document_templates WHERE company_id IS NULL"
    )).fetchall()
    for rid, body in rows:
        if not body:
            continue
        fixed = _fix(body)
        if fixed != body:
            bind.execute(sa.text("UPDATE document_templates SET body_html = :b WHERE id = :i"),
                         {"b": fixed, "i": rid})


def downgrade() -> None:
    """لا رجوع: الرجوع يعيد "د.ك د.ك" و"شركة شركة" إلى ورق رسمي."""
