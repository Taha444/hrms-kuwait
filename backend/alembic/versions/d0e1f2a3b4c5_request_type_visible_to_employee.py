"""request type visible_to_employee + default_template_code (P0-02/P0-06)

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('request_types', sa.Column('visible_to_employee', sa.Boolean(), nullable=False,
                                             server_default=sa.false()))
    op.add_column('request_types', sa.Column('default_template_code', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('request_types', 'default_template_code')
    op.drop_column('request_types', 'visible_to_employee')
