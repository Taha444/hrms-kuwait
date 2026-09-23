# -*- coding: utf-8 -*-
"""صاحب الشركة (company_owner) ليس موظًفا: لا سجل employees له، وعضويته في
الشركات تمثيلية لا وظيفية (CROSS_COMPANY_ROLES). لمستنداته الشخصية (مدنية/
جواز) وهويته الأساسية مكاٌن — سجل حسابه (users) نفسه، لا سجل موظف مصطنع.

- documents.company_id يصير اختيارًيا: مستند صاحب الشركة ليس ملًكا لشركة
  واحدة بعينها.
- أعمدة هوية أساسية تُضاف على users (اختيارية، تخص المالك فقط عملًيا):
  date_of_birth, nationality, passport_number, passport_expiry.

Revision ID: o5d6e7f8g9b
Revises: n2c3d4e5f6a
Create Date: 2026-09-23
"""
from alembic import op
import sqlalchemy as sa

revision = "o5d6e7f8g9b"
down_revision = "n2c3d4e5f6a"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "sqlite":
        with op.batch_alter_table("documents") as batch:
            batch.alter_column("company_id", existing_type=sa.Integer(), nullable=True)
    else:
        op.alter_column("documents", "company_id", existing_type=sa.Integer(), nullable=True)

    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("nationality", sa.String(length=80), nullable=True))
    op.add_column("users", sa.Column("passport_number", sa.String(length=40), nullable=True))
    op.add_column("users", sa.Column("passport_expiry", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("users", "passport_expiry")
    op.drop_column("users", "passport_number")
    op.drop_column("users", "nationality")
    op.drop_column("users", "date_of_birth")

    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table("documents") as batch:
            batch.alter_column("company_id", existing_type=sa.Integer(), nullable=False)
    else:
        op.alter_column("documents", "company_id", existing_type=sa.Integer(), nullable=False)
