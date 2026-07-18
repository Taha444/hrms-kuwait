"""V1.5 Phase 4 — RequestDocument.od_code + lifecycle_status

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("request_documents", sa.Column("od_code", sa.String(length=10), nullable=True))
    op.add_column("request_documents", sa.Column(
        "lifecycle_status", sa.String(length=20), nullable=False, server_default="GENERATED"))
    op.create_index("ix_request_documents_od_code", "request_documents", ["od_code"])


def downgrade() -> None:
    op.drop_index("ix_request_documents_od_code", "request_documents")
    op.drop_column("request_documents", "lifecycle_status")
    op.drop_column("request_documents", "od_code")
