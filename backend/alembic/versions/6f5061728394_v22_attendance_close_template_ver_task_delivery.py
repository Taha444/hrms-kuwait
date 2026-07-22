"""V2.2 §17 + §14 + §20 — attendance close + template versions + task delivery retry

Revision ID: 6f5061728394
Revises: 5e4f50617283
Create Date: 2026-07-22 02:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6f5061728394"
down_revision: Union[str, None] = "5e4f50617283"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # §17 attendance month close
    op.create_table(
        "attendance_month_closes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("period", sa.String(length=7), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="closed"),
        sa.Column("closed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column("reopened_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reopened_at", sa.DateTime(), nullable=True),
        sa.Column("reopen_reason", sa.String(length=300), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("company_id", "period", name="uq_att_close_company_period"),
    )

    # §14 template versioning
    op.create_table(
        "document_template_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("document_templates.id"),
                  nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("body_html", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=60), nullable=False, server_default="عام"),
        sa.Column("edited_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("edited_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column("change_note", sa.String(length=300), nullable=True),
    )

    # §20 task delivery retry
    op.add_column("tasks", sa.Column("delivery_attempts", sa.Integer(), nullable=False,
                                     server_default="0"))
    op.add_column("tasks", sa.Column("last_delivery_error", sa.String(length=400), nullable=True))
    op.add_column("tasks", sa.Column("last_delivery_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for col in ("last_delivery_at", "last_delivery_error", "delivery_attempts"):
        op.drop_column("tasks", col)
    op.drop_table("document_template_versions")
    op.drop_table("attendance_month_closes")
