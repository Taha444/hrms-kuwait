# -*- coding: utf-8 -*-
"""سجل حركات رصيد الإجازة السنوية

مراجعة العميل (الصفحة ٣): عرض الرصيد المتاح، وخصمه تلقائيًا بعد كل استهلاك،
وعرض السجل في جدول.

الرصيد كان عمودًا (annual_leave_balance) لا يُخصم منه شيء: طلب الإجازة يكتمل
بلا أثر — لا سجل Leave يُنشأ ولا رصيد ينقص. ولو خُصم من العمود وحده لما أمكن
تفسير الرقم لاحًقا. هذا الجدول يحفظ كل حركة بالرصيد قبلها وبعدها ومرجعها،
فالرقم قابل لإعادة البناء والاعتراض عليه يُحسم بمستند.

Revision ID: x7q8r9s0t1u
Revises: w6p7q8r9s0t
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "x7q8r9s0t1u"
down_revision: Union[str, None] = "w6p7q8r9s0t"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "leave_ledger" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "leave_ledger",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("days", sa.Float(), nullable=False),
        sa.Column("balance_before", sa.Float(), nullable=False),
        sa.Column("balance_after", sa.Float(), nullable=False),
        sa.Column("leave_type", sa.String(length=30), nullable=True),
        sa.Column("request_id", sa.Integer(), nullable=True),
        sa.Column("leave_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"],
                                name=op.f("fk_leave_ledger_employee_id_employees"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leave_ledger")),
    )
    op.create_index(op.f("ix_leave_ledger_employee_id"), "leave_ledger",
                    ["employee_id"], unique=False)
    op.create_index(op.f("ix_leave_ledger_company_id"), "leave_ledger",
                    ["company_id"], unique=False)
    op.create_index(op.f("ix_leave_ledger_request_id"), "leave_ledger",
                    ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_table("leave_ledger")
