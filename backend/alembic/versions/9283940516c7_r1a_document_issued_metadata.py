# -*- coding: utf-8 -*-
"""R1-A §8 — Document immutable artifact metadata

Revision ID: 9283940516c7
Revises: 8172839405b6
Create Date: 2026-08-02

يضيف حقول التوثيق الرسمي على جدول documents:
- is_issued: عَلَم فصل مستندات التوليد الحقيقي عن المعاينة (Preview)
- reference_no: رقم مرجعي فريد ومقروء
- template_version, checksum_sha256, generated_at/by, signature_version

كذلك يمسح مستندات "form_*" القديمة اللي كانت تُنشأ عن طريق Preview بالخطأ
(كانت تكتب على القرص وتنشئ صف Document بلا metadata فعلي).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9283940516c7"
down_revision: Union[str, None] = "8172839405b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # الأعمدة الجديدة
    op.add_column("documents", sa.Column("is_issued", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("documents", sa.Column("reference_no", sa.String(60), nullable=True))
    op.add_column("documents", sa.Column("template_version", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("checksum_sha256", sa.String(64), nullable=True))
    op.add_column("documents", sa.Column("generated_at", sa.DateTime(), nullable=True))
    op.add_column("documents", sa.Column("generated_by", sa.Integer(),
                                         sa.ForeignKey("users.id"), nullable=True))
    op.add_column("documents", sa.Column("signature_version", sa.Integer(), nullable=True))
    op.create_index("ix_documents_is_issued", "documents", ["is_issued"])
    op.create_index("ux_documents_reference_no", "documents", ["reference_no"], unique=True)

    # عداد نسخة القالب — يُختم على المستند المُولّد
    op.add_column("document_templates",
                  sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    # تنظيف مستندات المعاينة القديمة (اللي كانت تتخزّن بالغلط من Preview)
    # نمسح كل document_type_code يبدأ بـform_HRMS-PR أو form_ متبوعًا برقم القالب
    conn = op.get_bind()
    conn.execute(sa.text(
        "DELETE FROM documents WHERE document_type_code LIKE 'form\\_%' ESCAPE '\\' "
        "AND (is_issued = 0 OR is_issued IS NULL)"
    ))


def downgrade() -> None:
    op.drop_column("document_templates", "version")
    op.drop_index("ux_documents_reference_no", table_name="documents")
    op.drop_index("ix_documents_is_issued", table_name="documents")
    op.drop_column("documents", "signature_version")
    op.drop_column("documents", "generated_by")
    op.drop_column("documents", "generated_at")
    op.drop_column("documents", "checksum_sha256")
    op.drop_column("documents", "template_version")
    op.drop_column("documents", "reference_no")
    op.drop_column("documents", "is_issued")
