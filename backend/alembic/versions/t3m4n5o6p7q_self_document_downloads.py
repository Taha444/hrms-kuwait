# -*- coding: utf-8 -*-
"""سجل تنزيل الموظف لمستنداته — تنزيل واحد لكل مستند

قرار العميل: الموظف ينزّل نسخة مستنده من الخدمة الذاتية مرة واحدة فقط.
القيد الفريد (user_id, document_id) هو ما يفرض القاعدة فعليًا؛ الاعتماد على
فحص "هل نزّله قبل كذا؟" وحده يسمح بمرور تنزيلين متزامنين من نافذتين.

Revision ID: t3m4n5o6p7q
Revises: s2l3m4n5o6p
"""
import sqlalchemy as sa
from alembic import op

revision = "t3m4n5o6p7q"
down_revision = "s2l3m4n5o6p"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "self_document_downloads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("document_type_code", sa.String(length=50), nullable=True),
        sa.Column("ip", sa.String(length=50), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"],
                                name=op.f("fk_self_document_downloads_user_id_users"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"],
                                name=op.f("fk_self_document_downloads_document_id_documents"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_self_document_downloads")),
        sa.UniqueConstraint("user_id", "document_id", name="uq_self_document_download"),
    )
    op.create_index(op.f("ix_self_document_downloads_user_id"),
                    "self_document_downloads", ["user_id"], unique=False)
    op.create_index(op.f("ix_self_document_downloads_document_id"),
                    "self_document_downloads", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_self_document_downloads_document_id"),
                  table_name="self_document_downloads")
    op.drop_index(op.f("ix_self_document_downloads_user_id"),
                  table_name="self_document_downloads")
    op.drop_table("self_document_downloads")
