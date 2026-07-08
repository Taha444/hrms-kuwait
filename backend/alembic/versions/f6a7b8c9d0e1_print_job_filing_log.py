"""print job / filing log columns on request_documents (FIX-008)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-08 00:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('request_documents',
                  sa.Column('print_status', sa.String(length=20), nullable=False,
                            server_default='ready_to_print'))
    op.add_column('request_documents', sa.Column('printed_at', sa.DateTime(), nullable=True))
    op.add_column('request_documents', sa.Column('printed_by', sa.Integer(), nullable=True))
    op.add_column('request_documents', sa.Column('filed_at', sa.DateTime(), nullable=True))
    op.add_column('request_documents', sa.Column('filed_by', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('request_documents', 'filed_by')
    op.drop_column('request_documents', 'filed_at')
    op.drop_column('request_documents', 'printed_by')
    op.drop_column('request_documents', 'printed_at')
    op.drop_column('request_documents', 'print_status')
