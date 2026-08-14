# -*- coding: utf-8 -*-
"""QA-18 — employees.non_payroll: سجل وصول/صلاحية لا وظيفة على الكشف.

المندوب الذي يخدم شركتين يحتاج سجل موظف في كل منهما ليعمل فيهما، لكن راتبه في
واحدة. بلا هذا التمييز يدخل كشف الشركة الثانية براتب صفر، ويُحتسب له مستحق
نهاية خدمة لا وجود له.

التعبئة الرجعية مشتقّة لا مخمَّنة: تُعلَّم سجلات الموظفين المرتبطة بعضوية
شركة (user_company_links) لمستخدم له وظيفة أصلية (users.employee_id) —
أي الإسنادات الثانوية وحدها. ولا تُلمَس الوظيفة الأصلية أًبدا.

Revision ID: a1t2u3v4w5x
Revises: z9s0t1u2v3w
"""
from alembic import op
import sqlalchemy as sa

revision = "a1t2u3v4w5x"
down_revision = "z9s0t1u2v3w"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("employees")}
    if "non_payroll" not in cols:
        op.add_column("employees", sa.Column("non_payroll", sa.Boolean(),
                                             nullable=False, server_default=sa.false()))
    if "non_payroll_reason" not in cols:
        op.add_column("employees", sa.Column("non_payroll_reason", sa.String(200), nullable=True))

    tables = set(sa.inspect(bind).get_table_names())
    if "user_company_links" in tables:
        op.execute(sa.text("""
            UPDATE employees SET non_payroll = true,
                   non_payroll_reason = 'إسناد ثانوي — وصول/صلاحية فقط (تعبئة رجعية)'
            WHERE id IN (
                SELECT l.employee_id FROM user_company_links l
                JOIN users u ON u.id = l.user_id
                WHERE u.employee_id IS NOT NULL AND u.employee_id <> l.employee_id
            )
        """))


def downgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("employees")}
    if "non_payroll_reason" in cols:
        op.drop_column("employees", "non_payroll_reason")
    if "non_payroll" in cols:
        op.drop_column("employees", "non_payroll")
