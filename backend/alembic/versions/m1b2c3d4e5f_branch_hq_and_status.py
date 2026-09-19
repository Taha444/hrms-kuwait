# -*- coding: utf-8 -*-
"""مقرُّ الشركة، وأرشفُة الفرع — طلب المالك (2026-09-19).

- ``is_headquarters``: مقرُّ الشركة الرئيسي — ليس «فرًعا»: يُسمّى «مقر الشركة»،
  ومديُره مديُر الشركة، وعليه الموظفون الإداريون.
- ``status``: ``active`` أو ``archived``. لم يكن للفرع حالٌة قط — فلا طريَق
  لإخراج فرٍع مكرٍَّر أو خارج ملف الشركة إلا حذفه، والحذُف يمحو حضوره وتاريخه.
  فيُؤرشَف: يختفي من القوائم والحضور، ويبقى تاريخه.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "m1b2c3d4e5f"
down_revision = "l0a1b2c3d4e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("branches") as b:
        b.add_column(sa.Column("is_headquarters", sa.Boolean(), nullable=False,
                               server_default=sa.false()))
        b.add_column(sa.Column("status", sa.String(length=20), nullable=False,
                               server_default="active"))


def downgrade() -> None:
    with op.batch_alter_table("branches") as b:
        b.drop_column("status")
        b.drop_column("is_headquarters")
