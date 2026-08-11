# -*- coding: utf-8 -*-
"""EOS case lifecycle table (9 stages with separation of duties).

Revision ID: r1k2l3m4n5o
Revises: q0j1k2l3m4n
Create Date: 2026-08-10

QA §6 — initiated → calculated → approved → clearance → acknowledged
        → settled → ready_to_print → printed → filed
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "r1k2l3m4n5o"
down_revision: Union[str, None] = "q0j1k2l3m4n"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "eos_cases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"),
                  nullable=False, index=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"),
                  nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False,
                  server_default="initiated", index=True),
        sa.Column("reference_no", sa.String(60), nullable=True, unique=True, index=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("termination_reason", sa.String(40), nullable=True),
        sa.Column("used_leave_days", sa.Float(), nullable=False, server_default="0"),
        sa.Column("settlement_json", sa.JSON(), nullable=True),
        sa.Column("initiated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("initiated_at", sa.DateTime(), nullable=True),
        sa.Column("calculated_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("calculated_at", sa.DateTime(), nullable=True),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("clearance_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("clearance_at", sa.DateTime(), nullable=True),
        sa.Column("clearance_notes", sa.Text(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("acknowledgment_note", sa.Text(), nullable=True),
        sa.Column("settled_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("payment_reference", sa.String(80), nullable=True),
        sa.Column("printed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("printed_at", sa.DateTime(), nullable=True),
        sa.Column("filed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("filed_at", sa.DateTime(), nullable=True),
        sa.Column("filing_location", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("eos_cases")
