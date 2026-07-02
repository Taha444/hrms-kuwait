"""employee actual salary/branch/license + created_by

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-29 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.add_column(sa.Column('actual_salary', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('actual_license_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('actual_branch_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('created_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_employees_actual_license_id_licenses'),
                                    'licenses', ['actual_license_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('fk_employees_actual_branch_id_branches'),
                                    'branches', ['actual_branch_id'], ['id'])
        batch_op.create_foreign_key(batch_op.f('fk_employees_created_by_users'),
                                    'users', ['created_by'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_employees_created_by_users'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_employees_actual_branch_id_branches'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_employees_actual_license_id_licenses'), type_='foreignkey')
        batch_op.drop_column('created_by')
        batch_op.drop_column('actual_branch_id')
        batch_op.drop_column('actual_license_id')
        batch_op.drop_column('actual_salary')
