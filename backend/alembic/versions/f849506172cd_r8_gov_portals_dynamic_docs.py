# -*- coding: utf-8 -*-
"""R8 §1+§2 — Government Portals + Dynamic Custom Documents flag

Revision ID: f849506172cd
Revises: e738495061bc
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f849506172cd"
down_revision: Union[str, None] = "e738495061bc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # R8 §1 — Government Portals table
    op.create_table(
        "government_portals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name_ar", sa.String(200), nullable=False),
        sa.Column("name_en", sa.String(200), nullable=True),
        sa.Column("description_ar", sa.Text(), nullable=True),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("category", sa.String(30), nullable=False, server_default="other"),
        sa.Column("icon", sa.String(60), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_gov_portals_category", "government_portals", ["category"])
    op.create_index("ix_gov_portals_is_active", "government_portals", ["is_active"])

    # R8 §2 — Document.notify_on_expiry flag (للـcustom docs)
    op.add_column("documents", sa.Column("notify_on_expiry", sa.Boolean(),
                                        nullable=False, server_default=sa.false()))

    # Seed default government portals (يقدر Admin يعدّل/يمسح بعدين)
    op.execute("""
        INSERT INTO government_portals (name_ar, name_en, description_ar, url, category, sort_order, is_active, created_at, updated_at) VALUES
        ('بوابة مدني (PACI)', 'PACI Portal', 'الهيئة العامة للمعلومات المدنية — طلبات البطاقة المدنية والتحديث', 'https://www.paci.gov.kw/', 'civil_id', 10, true, NOW(), NOW()),
        ('ساحل — الخدمات الحكومية', 'Sahel Portal', 'بوابة ساحل الحكومية الشاملة', 'https://sahel.gov.kw/', 'other', 5, true, NOW(), NOW()),
        ('وزارة التجارة والصناعة', 'MOCI Portal', 'رخص تجارية، سجل تجاري، أذونات تعديل', 'https://www.moci.gov.kw/', 'moci', 20, true, NOW(), NOW()),
        ('هيئة القوى العاملة (PAM)', 'Public Authority of Manpower', 'إذن العمل، ملفات الشركات، تحويل العمالة', 'https://www.pam.gov.kw/', 'work_permits', 30, true, NOW(), NOW()),
        ('الإدارة العامة للإقامة', 'Directorate General of Residency', 'تجديد الإقامات، تأشيرات، استعلام', 'https://moi.gov.kw/', 'residency', 40, true, NOW(), NOW()),
        ('البلدية', 'Kuwait Municipality', 'تراخيص المحلات والفروع', 'https://www.baladia.gov.kw/', 'municipality', 50, true, NOW(), NOW()),
        ('المؤسسة العامة للتأمينات الاجتماعية', 'PIFSS', 'اشتراكات التأمينات والتقاعد', 'https://www.pifss.gov.kw/', 'insurance', 60, true, NOW(), NOW())
    """)


def downgrade() -> None:
    op.drop_column("documents", "notify_on_expiry")
    op.drop_index("ix_gov_portals_is_active", table_name="government_portals")
    op.drop_index("ix_gov_portals_category", table_name="government_portals")
    op.drop_table("government_portals")
