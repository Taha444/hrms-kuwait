# -*- coding: utf-8 -*-
"""AWS-02 — جدول جولات المهام المجدولة: القفل والدليل في صفّ واحد.

المجدول يعمل داخل التطبيق، فمع أكثر من instance يعمل على كل واحدة: الفحص
اليومي يُنشئ تنبيهات ومهامّ مكرّرة والإشعارات تصل مرتين. المفتاح الأساسيّ
المركّب هو القفل نفسه — الإدراج عليه ذرّيّ في Postgres وSQLite معًا.

Revision ID: t9l0m1n2o3p
Revises: s8k9l0m1n2o
"""
import sqlalchemy as sa
from alembic import op

revision = "t9l0m1n2o3p"
down_revision = "s8k9l0m1n2o"
branch_labels = None
depends_on = None

TABLE = "job_runs"


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE in sa.inspect(bind).get_table_names():
        return                      # قابل لإعادة التشغيل
    op.create_table(
        TABLE,
        sa.Column("job", sa.String(40), primary_key=True),
        sa.Column("run_key", sa.String(40), primary_key=True),
        sa.Column("status", sa.String(12), nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("holder", sa.String(80), nullable=True),
        sa.Column("recovered", sa.Integer, nullable=True),
    )
    # للتنظيف الدوري وللسؤال «ماذا عمل أمس؟»
    op.create_index("ix_job_runs_started_at", TABLE, ["started_at"])


def downgrade() -> None:
    bind = op.get_bind()
    if TABLE in sa.inspect(bind).get_table_names():
        op.drop_index("ix_job_runs_started_at", table_name=TABLE)
        op.drop_table(TABLE)
