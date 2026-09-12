# -*- coding: utf-8 -*-
"""رقُم نسخٍة واحٌد لكل قالب — سجٌّل «immutable» ال يحمل رقمين متساويين.

**العطل**: ``update_template`` يقرأ آخَر نسخٍة ثم يُدخِل ``last + 1``. وبين
القراءة والكتابة نافذة: تحريران في اللحظة نفسها يكتبان **الرقَم نفسه**،
فيصير للقالب نسختان بالرقم ذاته. والمستنداُت المُصدَرة تشير إلى رقم النسخة
— فال يُعرَف أيَّهما أُصدرت به، وهو نقُض الغرض المكتوب في شرح الصفّ:
«immutable audit trail».

**والسابقُة قائمة**: ``user_signature_versions`` لها قيٌد على
``(user_id, version)`` لنفس العلّة. فهذا شقيقُها.

**ويُقاس قبل أن يُفرَض**: قاعدٌة فيها رقمان متساويان يسقط عليها القيد فتفشل
النشرُة كلُّها. فإن وُجد تكراٌر **تُرقَّم النسُخ من جديد بترتيب تحريرها** —
ولا تُحذَف نسخة: هي نصُّ قالٍب أُصدِر به مستندٌ يوًما.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g5b6c7d8e9f"
down_revision = "f4a5b6c7d8e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    dupes = bind.execute(sa.text("""
        SELECT template_id FROM document_template_versions
        GROUP BY template_id, version HAVING COUNT(*) > 1
    """)).fetchall()

    for (template_id,) in {(r[0],) for r in dupes}:
        rows = bind.execute(sa.text("""
            SELECT id FROM document_template_versions
             WHERE template_id = :t ORDER BY edited_at, id
        """), {"t": template_id}).fetchall()
        for n, (row_id,) in enumerate(rows, start=1):
            bind.execute(sa.text(
                "UPDATE document_template_versions SET version = :v WHERE id = :i"),
                {"v": n, "i": row_id})

    with op.batch_alter_table("document_template_versions") as batch:
        batch.create_unique_constraint("uq_template_version",
                                       ["template_id", "version"])


def downgrade() -> None:
    with op.batch_alter_table("document_template_versions") as batch:
        batch.drop_constraint("uq_template_version", type_="unique")
