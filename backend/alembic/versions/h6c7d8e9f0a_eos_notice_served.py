# -*- coding: utf-8 -*-
"""هل أُبلغ الإنذار — قرار المالك (2026-09-17) بربط بدل الإنذار بالتسوية.

عمودان يقبلان الفراغ: الحالاتُ القائمة تبقى بلا جواب، ولا تُحسب لها تسويةُ
فصلٍ غير تأديبي قبل أن يُسجَّل.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "h6c7d8e9f0a"
down_revision = "g5b6c7d8e9f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("eos_cases") as b:
        b.add_column(sa.Column("notice_served", sa.Boolean(), nullable=True))
        b.add_column(sa.Column("notice_served_date", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("eos_cases") as b:
        b.drop_column("notice_served_date")
        b.drop_column("notice_served")
