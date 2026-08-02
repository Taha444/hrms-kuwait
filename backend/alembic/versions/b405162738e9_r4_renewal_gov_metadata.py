# -*- coding: utf-8 -*-
"""R4 §7 — Residency Renewal government transaction metadata

Revision ID: b405162738e9
Revises: a394051627d8
Create Date: 2026-08-02

يضيف حقول إتمام المعاملة الحكومية (gov ref، رسوم، رقم/تاريخ جديد)
+ حقول تحقق HR للإغلاق النهائي.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b405162738e9"
down_revision: Union[str, None] = "a394051627d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("residency_renewals", sa.Column("gov_reference_no", sa.String(60), nullable=True))
    op.add_column("residency_renewals", sa.Column("fees_amount", sa.Float(), nullable=True))
    op.add_column("residency_renewals", sa.Column("fees_receipt_no", sa.String(60), nullable=True))
    op.add_column("residency_renewals", sa.Column("new_permit_number", sa.String(60), nullable=True))
    op.add_column("residency_renewals", sa.Column("new_expiry_date", sa.Date(), nullable=True))
    op.add_column("residency_renewals", sa.Column("finalized_at", sa.DateTime(), nullable=True))
    op.add_column("residency_renewals",
                  sa.Column("finalized_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("residency_renewals", sa.Column("hr_verified_at", sa.DateTime(), nullable=True))
    op.add_column("residency_renewals",
                  sa.Column("hr_verified_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True))
    op.add_column("residency_renewals", sa.Column("hr_verification_note", sa.Text(), nullable=True))
    op.create_index("ix_rn_gov_reference_no", "residency_renewals", ["gov_reference_no"])


def downgrade() -> None:
    op.drop_index("ix_rn_gov_reference_no", table_name="residency_renewals")
    for col in ("hr_verification_note", "hr_verified_by", "hr_verified_at",
                "finalized_by", "finalized_at",
                "new_expiry_date", "new_permit_number",
                "fees_receipt_no", "fees_amount", "gov_reference_no"):
        op.drop_column("residency_renewals", col)
