"""notification templates + preferences + task delivery log (FIX-004)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-08 00:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notification_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=60), nullable=False),
        sa.Column('event_type', sa.String(length=40), nullable=False),
        sa.Column('channel_default', sa.String(length=20), nullable=False, server_default='in_app'),
        sa.Column('sla_hours', sa.Integer(), nullable=True),
        sa.Column('body_text', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notification_templates')),
        sa.UniqueConstraint('code', name=op.f('uq_notification_templates_code')),
    )
    op.create_table(
        'notification_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=60), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notification_preferences_user_id_users'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notification_preferences')),
        sa.UniqueConstraint('user_id', 'category', 'channel', name='uq_notif_pref'),
    )
    op.create_index(op.f('ix_notification_preferences_user_id'), 'notification_preferences',
                    ['user_id'], unique=False)
    op.add_column('tasks', sa.Column('template_code', sa.String(length=50), nullable=True))
    op.add_column('tasks', sa.Column('channel', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('tasks', 'channel')
    op.drop_column('tasks', 'template_code')
    op.drop_index(op.f('ix_notification_preferences_user_id'), table_name='notification_preferences')
    op.drop_table('notification_preferences')
    op.drop_table('notification_templates')
