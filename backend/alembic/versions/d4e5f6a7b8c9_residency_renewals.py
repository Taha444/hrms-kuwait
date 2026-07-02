"""residency renewals table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-29 02:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'residency_renewals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('permit_id', sa.Integer(), nullable=True),
        sa.Column('renewal_type', sa.String(length=10), nullable=False, server_default='early'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='new'),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('reject_reason', sa.Text(), nullable=True),
        sa.Column('days_left_at_request', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'],
                                name=op.f('fk_residency_renewals_company_id_companies')),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'],
                                name=op.f('fk_residency_renewals_employee_id_employees')),
        sa.ForeignKeyConstraint(['permit_id'], ['permits.id'],
                                name=op.f('fk_residency_renewals_permit_id_permits')),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'],
                                name=op.f('fk_residency_renewals_created_by_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_residency_renewals')),
    )
    op.create_index(op.f('ix_residency_renewals_company_id'), 'residency_renewals',
                    ['company_id'], unique=False)
    op.create_index(op.f('ix_residency_renewals_employee_id'), 'residency_renewals',
                    ['employee_id'], unique=False)
    op.create_index(op.f('ix_residency_renewals_status'), 'residency_renewals',
                    ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_residency_renewals_status'), table_name='residency_renewals')
    op.drop_index(op.f('ix_residency_renewals_employee_id'), table_name='residency_renewals')
    op.drop_index(op.f('ix_residency_renewals_company_id'), table_name='residency_renewals')
    op.drop_table('residency_renewals')
