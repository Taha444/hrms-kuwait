# -*- coding: utf-8 -*-
"""تقويمُ العطل الرسمية — قرار المالك (2026-09-17).

جدولٌ جديد؛ لا يمسّ بياناتٍ قائمة. عطلةٌ واحدة لكل شركة في اليوم.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "i7d8e9f0a1b"
down_revision = "h6c7d8e9f0a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "holidays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("company_id", "date", name="uq_holiday_company_date"),
    )
    op.create_index("ix_holidays_company_id", "holidays", ["company_id"])


def downgrade() -> None:
    op.drop_index("ix_holidays_company_id", table_name="holidays")
    op.drop_table("holidays")
