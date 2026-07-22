"""PILOT-P0-6 + P0-11 — employee_no (unique) + backfill + commercial_reg unique index

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-07-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5d6e7f8a9b0"
down_revision: Union[str, None] = "b4c5d6e7f8a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PILOT-P0-6 — رقم وظيفي مرئي، فريد على مستوى النظام
    op.add_column("employees", sa.Column("employee_no", sa.String(length=30), nullable=True))
    op.create_index("ix_employees_employee_no", "employees", ["employee_no"])
    op.create_unique_constraint("uq_employees_employee_no", "employees", ["employee_no"])

    # PILOT-P0-11 — منع تكرار السجل التجاري بين شركتين (كان قابل للتكرار قبل الفحص)
    # ملاحظة: NULL لا يعتبر متعارضًا في المؤشرات الفريدة، لذا الشركات بلا سجل تجاري
    # لا تصطدم مع بعضها.
    op.create_index("uq_companies_commercial_reg", "companies", ["commercial_reg"],
                    unique=True, postgresql_where=sa.text("commercial_reg IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("uq_companies_commercial_reg", "companies")
    op.drop_constraint("uq_employees_employee_no", "employees", type_="unique")
    op.drop_index("ix_employees_employee_no", "employees")
    op.drop_column("employees", "employee_no")
