"""PILOT-P0-7 + P0-8 — Payroll staged workflow + Termination staged workflow

Revision ID: e7f8a9b0c1d2
Revises: c5d6e7f8a9b0
Create Date: 2026-07-22 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "c5d6e7f8a9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PILOT-P0-7 — تتبع كل خطوة في دورة الرواتب (فصل السلطات)
    op.add_column("payroll_runs", sa.Column("prepared_by_user_id", sa.Integer(),
                                            sa.ForeignKey("users.id"), nullable=True))
    op.add_column("payroll_runs", sa.Column("prepared_at", sa.DateTime(), nullable=True))
    op.add_column("payroll_runs", sa.Column("approved_by_user_id", sa.Integer(),
                                            sa.ForeignKey("users.id"), nullable=True))
    op.add_column("payroll_runs", sa.Column("approved_at", sa.DateTime(), nullable=True))
    op.add_column("payroll_runs", sa.Column("finalized_by_user_id", sa.Integer(),
                                            sa.ForeignKey("users.id"), nullable=True))
    op.add_column("payroll_runs", sa.Column("finalized_at", sa.DateTime(), nullable=True))
    op.add_column("payroll_runs", sa.Column("locked_by_user_id", sa.Integer(),
                                            sa.ForeignKey("users.id"), nullable=True))
    op.add_column("payroll_runs", sa.Column("locked_at", sa.DateTime(), nullable=True))
    # التسويات بعد الـlock ترتبط بالمسيّر الأصلي
    op.add_column("payroll_runs", sa.Column("adjustment_of_run_id", sa.Integer(),
                                            sa.ForeignKey("payroll_runs.id"), nullable=True))
    op.add_column("payroll_runs", sa.Column("adjustment_reason", sa.Text(), nullable=True))
    # توسعة الـperiod لدعم لاحقة "-ADJ-<id>"
    with op.batch_alter_table("payroll_runs") as b:
        b.alter_column("period", type_=sa.String(length=30), existing_type=sa.String(length=7))

    # PILOT-P0-8 — دورة إنهاء الخدمة (لا فصل فوري):
    #   HR يحضّر → المحاسب يعتمد → HR ينفّذ
    op.add_column("employees", sa.Column("pending_termination_json", sa.Text(), nullable=True))
    op.add_column("employees", sa.Column("pending_termination_prepared_by", sa.Integer(),
                                         sa.ForeignKey("users.id"), nullable=True))
    op.add_column("employees", sa.Column("pending_termination_prepared_at", sa.DateTime(), nullable=True))
    op.add_column("employees", sa.Column("pending_termination_approved_by", sa.Integer(),
                                         sa.ForeignKey("users.id"), nullable=True))
    op.add_column("employees", sa.Column("pending_termination_approved_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    for col in ("pending_termination_approved_at", "pending_termination_approved_by",
                "pending_termination_prepared_at", "pending_termination_prepared_by",
                "pending_termination_json"):
        op.drop_column("employees", col)
    with op.batch_alter_table("payroll_runs") as b:
        b.alter_column("period", type_=sa.String(length=7), existing_type=sa.String(length=30))
    for col in ("adjustment_reason", "adjustment_of_run_id",
                "locked_at", "locked_by_user_id",
                "finalized_at", "finalized_by_user_id",
                "approved_at", "approved_by_user_id",
                "prepared_at", "prepared_by_user_id"):
        op.drop_column("payroll_runs", col)
