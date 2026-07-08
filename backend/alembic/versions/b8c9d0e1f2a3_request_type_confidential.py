"""request type is_confidential flag (FIX-014)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-08 00:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('request_types', sa.Column('is_confidential', sa.Boolean(), nullable=False,
                                             server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('request_types', 'is_confidential')
