"""بدٌل يُعتمد ولا يُصرَف — جدوٌل للأثر الموجب.

Revision ID: d2e3f4a5b6c
Revises: c1d2e3f4a5b

``REQALLOW`` يجمع النوع والمبلغ وتاريخ النفاذ والتكرار، ولا يقرؤها أحد.
والرواتب لا تعرف البدلات أصًلا: ``gross = earned_basic + overtime_pay``.
فلا موضع يهبط فيه البدل.

وجدوٌل مستقل لا خصٌم بإشارة سالبة: الأثر الموجب والسالب معنيان مختلفان،
وخلطهما يُفسِد كل تقرير خصومات بعده.
"""
from alembic import op
import sqlalchemy as sa

revision = "d2e3f4a5b6c"
down_revision = "c1d2e3f4a5b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "allowances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("requests.id"), nullable=True),
        sa.Column("allowance_type", sa.String(40), nullable=False, server_default="other"),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.String(250), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_allowances_company_id", "allowances", ["company_id"])
    op.create_index("ix_allowances_employee_id", "allowances", ["employee_id"])
    op.create_index("ix_allowances_request_id", "allowances", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_allowances_request_id", table_name="allowances")
    op.drop_index("ix_allowances_employee_id", table_name="allowances")
    op.drop_index("ix_allowances_company_id", table_name="allowances")
    op.drop_table("allowances")
