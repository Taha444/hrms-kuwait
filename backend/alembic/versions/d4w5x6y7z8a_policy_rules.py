# -*- coding: utf-8 -*-
"""V2.2 §7 (STR-05) — جدول policy_rules + لقطة السياسة على الطلب.

الحدود المالية والمدد كانت مزروعة في الكود أو غير موجودة أصًلا؛ ومرحلة
"اعتماد فوق الحد" (RW-07) لم يكن لها وجود لأن الحد نفسه لم يكن له وجود.

الجدول يبدأ فارًغا عن قصد: policy.DEFAULTS تُبقي السلوك الحالي حرفًيا حتى
تُعتمَد قاعدة، فلا ينكسر شيء بمجرد الترحيل.

Revision ID: d4w5x6y7z8a
Revises: c3v4w5x6y7z
"""
from alembic import op
import sqlalchemy as sa

revision = "d4w5x6y7z8a"
down_revision = "c3v4w5x6y7z"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "policy_rules" not in insp.get_table_names():
        op.create_table(
            "policy_rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), index=True),
            sa.Column("key", sa.String(80), nullable=False, index=True),
            sa.Column("value_json", sa.JSON(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("effective_from", sa.Date()),
            sa.Column("effective_to", sa.Date()),
            sa.Column("note", sa.String(300)),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("created_at", sa.DateTime()),
            sa.UniqueConstraint("company_id", "key", "version", name="uq_policy_rule_version"),
        )
    cols = {c["name"] for c in insp.get_columns("requests")}
    if "policy_snapshot_json" not in cols:
        op.add_column("requests", sa.Column("policy_snapshot_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "policy_snapshot_json" in {c["name"] for c in insp.get_columns("requests")}:
        op.drop_column("requests", "policy_snapshot_json")
    if "policy_rules" in insp.get_table_names():
        op.drop_table("policy_rules")
