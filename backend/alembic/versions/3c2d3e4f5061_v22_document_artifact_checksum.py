"""V2.2 §13 — Immutable Document Artifact (checksum + reference_no + signature_version)

Revision ID: 3c2d3e4f5061
Revises: 2b1c2d3e4f50
Create Date: 2026-07-22 01:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3c2d3e4f5061"
down_revision: Union[str, None] = "2b1c2d3e4f50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("request_documents", sa.Column("checksum_sha256", sa.String(length=64), nullable=True))
    op.add_column("request_documents", sa.Column("reference_no", sa.String(length=40), nullable=True))
    op.add_column("request_documents", sa.Column("signature_version", sa.Integer(), nullable=True))
    op.create_index("uq_request_documents_reference_no", "request_documents",
                    ["reference_no"], unique=True,
                    postgresql_where=sa.text("reference_no IS NOT NULL"))


def downgrade() -> None:
    op.drop_index("uq_request_documents_reference_no", "request_documents")
    for col in ("signature_version", "reference_no", "checksum_sha256"):
        op.drop_column("request_documents", col)
