# -*- coding: utf-8 -*-
"""RNW-12 — مصدر القيم المعتمَدة في معاملة التجديد.

القيمة وحدها لا تكفي. حين يُسأل بعد سنة عن تاريخ انتهاء إقامة في ملف موظف،
الفرق بين جواب مكتوب وتخمين هو أن يكون محفوًظا: هل قرأه النظام أم أدخله
إنسان، وبأي ثقة، ومن أي مستند، ومن أكّده ومتى.

Revision ID: q6i7j8k9l0m
Revises: p5h6i7j8k9l
"""
import sqlalchemy as sa
from alembic import op

from app.migration_ops import add_column  # يعمل على SQLite وPostgreSQL

revision = "q6i7j8k9l0m"
down_revision = "p5h6i7j8k9l"
branch_labels = None
depends_on = None


def upgrade() -> None:
    add_column("residency_renewals", sa.Column("confirmed_data_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    # لا نُسقط العمود: إسقاطه يفقد سجلّ مصدر القيم، وهو لا يُعاد بناؤه.
    pass
