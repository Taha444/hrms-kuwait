"""save EOS settlement in employee file

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-29 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('termination_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('termination_reason', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('eos_settlement_json', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.drop_column('eos_settlement_json')
        batch_op.drop_column('termination_reason')
        batch_op.drop_column('termination_date')
