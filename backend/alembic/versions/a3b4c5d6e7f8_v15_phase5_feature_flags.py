"""V1.5 Phase 5 — feature_flags table

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-07-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("value", sa.String(length=500), nullable=False),
        sa.Column("note", sa.String(length=250), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_feature_flags_key", "feature_flags", ["key"])
    op.create_index("ix_feature_flags_company_id", "feature_flags", ["company_id"])
    # فريد: (key, company_id) — كل شركة قيمة واحدة لكل flag
    op.create_index("uq_feature_flags_key_company", "feature_flags",
                    ["key", "company_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_feature_flags_key_company", "feature_flags")
    op.drop_index("ix_feature_flags_company_id", "feature_flags")
    op.drop_index("ix_feature_flags_key", "feature_flags")
    op.drop_table("feature_flags")
