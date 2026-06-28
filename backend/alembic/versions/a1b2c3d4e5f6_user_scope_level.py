"""user scope_level (company/branch/multi/self)

Revision ID: a1b2c3d4e5f6
Revises: 57b1c9e2001e
Create Date: 2026-06-28 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '57b1c9e2001e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('scope_level', sa.String(length=10), nullable=False,
                      server_default='company'))

    # تعبئة خلفية: اشتقاق المستوى من البيانات القائمة قبل وجود العمود
    users = sa.table(
        'users',
        sa.column('id', sa.Integer),
        sa.column('role', sa.String),
        sa.column('scope_level', sa.String),
        sa.column('scope_branch_id', sa.Integer),
    )
    # خدمة ذاتية للموظف
    op.execute(users.update().where(users.c.role == 'employee')
               .values(scope_level='self'))
    # مسؤول الفرع → عدة فروع (عبر جدول branch_supervisors)
    op.execute(users.update().where(users.c.role == 'branch_supervisor')
               .values(scope_level='multi'))
    # أي مستخدم مقيّد بفرع واحد صراحةً
    op.execute(users.update()
               .where(users.c.scope_branch_id.isnot(None))
               .where(users.c.role.notin_(('employee', 'branch_supervisor')))
               .values(scope_level='branch'))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('scope_level')
