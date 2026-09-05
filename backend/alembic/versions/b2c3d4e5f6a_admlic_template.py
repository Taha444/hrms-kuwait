# -*- coding: utf-8 -*-
"""ADMLIC — قالب تجديد ترخيص الشركة يبلغ القواعد القائمة.

كان ``default_template_code = "HRMS-PR-022"`` وهو **«إنذار موظف»**،
فئته «الإجراءات التأديبية». والقالب لا يُرسَم منه جسم المستند، لكنه
يُشتقّ منه ``od_code`` ويُختَم ``template_code`` على الأثر — فأثرُ
تجديد ترخيص شركة كان يُحفَظ ويُصنَّف تحت فئة تأديبية.

**وقرار المالك**: قالب تجديد الترخيص. ولم يكن موجوًدا — الاثنان
والأربعون قالًبا كلّها موجَّهة للموظف. فبُني ``HRMS-PR-043``، ومعه
مسار عرض يقبل كيان شركة وغلاف يعرض بيانات المنشأة بدل شبكة الموظف.

**والبذر يُدرج ولا يُحدِّث** (درس QA-07): فبلا هذا الترحيل لا يصل
القالب الجديد إلى قاعدة قائمة، ويبقى ``ADMLIC`` على تصنيفه التأديبي.

Revision ID: b2c3d4e5f6a
Revises: a1b2c3d4e5f
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a"
down_revision = "a1b2c3d4e5f"
branch_labels = None
depends_on = None

NEW_CODE = "HRMS-PR-043"
OLD_CODE = "HRMS-PR-022"


def _templates():
    return sa.table("document_templates",
                    sa.column("id", sa.Integer),
                    sa.column("code", sa.String),
                    sa.column("company_id", sa.Integer))


def _types():
    return sa.table("request_types",
                    sa.column("code", sa.String),
                    sa.column("default_template_code", sa.String))


def upgrade():
    bind = op.get_bind()

    # القالب نفسه يُبذَر من ``seed.py`` عند أول تشغيل على قاعدة جديدة.
    # وعلى قاعدة قائمة قد لا يوجد — فيُنشأ هنا من نفس المصدر، فلا نسخة
    # ثانية من نصّه تنحرف عن الأولى.
    exists = bind.execute(sa.text(
        "SELECT 1 FROM document_templates WHERE code = :c LIMIT 1"
    ), {"c": NEW_CODE}).first()
    if not exists:
        try:
            from app.seed import DEFAULT_TEMPLATES  # noqa: PLC0415
            row = next((r for r in DEFAULT_TEMPLATES if r[0] == NEW_CODE), None)
        except Exception:                       # noqa: BLE001
            row = None
        if row:
            code, name_ar, name_en, category, body = row
            cols = {c["name"] for c in sa.inspect(bind).get_columns(
                "document_templates")}
            values = {"code": code, "name": name_ar, "body_html": body}
            from datetime import datetime as _dt

            for k, v in (("name_en", name_en), ("category", category),
                         ("version", 1), ("is_active", True),
                         ("company_id", None),
                         # عمود غير قابل للفراغ — يُملأ صراحًة لأن
                         # الافتراض في النموذج لا يسري على INSERT خام.
                         ("created_at", _dt.utcnow())):
                if k in cols:
                    values[k] = v
            op.execute(sa.text(
                "INSERT INTO document_templates ({}) VALUES ({})".format(
                    ", ".join(values), ", ".join(f":{k}" for k in values))
            ).bindparams(**values))

    # ولا يُربَط النوع بقالب غير موجود: ربط بلا قالب يترك الأثر بلا صنف.
    linked = bind.execute(sa.text(
        "SELECT 1 FROM document_templates WHERE code = :c LIMIT 1"
    ), {"c": NEW_CODE}).first()
    if linked:
        t = _types()
        # مشروط بالقيمة الخاطئة: لو صُحّح يدًوا فلا يُمسّ.
        op.execute(t.update()
                   .where(t.c.code == "ADMLIC")
                   .where(sa.or_(t.c.default_template_code == OLD_CODE,
                                 t.c.default_template_code.is_(None)))
                   .values(default_template_code=NEW_CODE))


def downgrade():
    t = _types()
    op.execute(t.update()
               .where(t.c.code == "ADMLIC")
               .where(t.c.default_template_code == NEW_CODE)
               .values(default_template_code=OLD_CODE))
