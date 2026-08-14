# -*- coding: utf-8 -*-
"""QA-23 — users.last_activity_at لفرض الخروج التلقائي من الخادم.

كانت المهلة مؤقًتا في المتصفح وحده (auth.tsx)، يتجاوزه إغلاق التبويب أو
استدعاء الـAPI مباشرة، فيظل التوكن صالًحا. الخادم يقيس الخمول الآن بهذا العمود.

NULL = جلسة لم تُسجَّل بعد ⇒ لا يُطبَّق القطع (المستخدمون القائمون لا يُطردون
لحظة النشر؛ أول طلب يضبط الطابع ومنه يبدأ العدّ).

Revision ID: z9s0t1u2v3w
Revises: y8r9s0t1u2v
"""
from alembic import op
import sqlalchemy as sa

revision = "z9s0t1u2v3w"
down_revision = "y8r9s0t1u2v"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "last_activity_at" not in cols:
        op.add_column("users", sa.Column("last_activity_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "last_activity_at" in cols:
        op.drop_column("users", "last_activity_at")
