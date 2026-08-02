# -*- coding: utf-8 -*-
"""R7-G §4 — Salary change approval requests (maker-checker)

Revision ID: d627384950ab
Revises: c516273849fa
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d627384950ab"
down_revision: Union[str, None] = "c516273849fa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "salary_change_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.Integer(),
                  sa.ForeignKey("employees.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("field_name", sa.String(40), nullable=False),
        sa.Column("old_value", sa.String(200), nullable=True),
        sa.Column("new_value", sa.String(200), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("proposed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("proposed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("rejected_reason", sa.Text(), nullable=True),
        sa.Column("applied_change_id", sa.Integer(),
                  sa.ForeignKey("employee_field_changes.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("salary_change_requests")
