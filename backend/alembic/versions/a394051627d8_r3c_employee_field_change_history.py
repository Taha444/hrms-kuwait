# -*- coding: utf-8 -*-
"""R3-C §4 — Employee field change history

Revision ID: a394051627d8
Revises: 9283940516c7
Create Date: 2026-08-02

جدول EmployeeFieldChange لتتبّع التغييرات الحرجة (راتب/تاريخ تعيين/عقد/مسمى)
مع effective_date منفصل عن changed_at — بحيث يمكن تسجيل تغيير مستقبلي.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a394051627d8"
down_revision: Union[str, None] = "9283940516c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employee_field_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, index=True),
        sa.Column("employee_id", sa.Integer(),
                  sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("field_name", sa.String(40), nullable=False),
        sa.Column("old_value", sa.String(200), nullable=True),
        sa.Column("new_value", sa.String(200), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
    )
    op.create_index("ix_efc_employee_effective", "employee_field_changes",
                   ["employee_id", "effective_date"])


def downgrade() -> None:
    op.drop_index("ix_efc_employee_effective", table_name="employee_field_changes")
    op.drop_table("employee_field_changes")
