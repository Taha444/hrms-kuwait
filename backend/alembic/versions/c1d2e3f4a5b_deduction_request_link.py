"""خصٌم بلا مصدر رقٌم بلا تفسير — يُربَط بقراره.

Revision ID: c1d2e3f4a5b
Revises: b8c9d0e1f2a

``ADMDED`` صار له أثٌر يكتب صفًّا في ``deductions``. وصفُّ خصٍم بلا إشارة
إلى قراره لا يُفسَّر بعد شهور: من يقرأ كشف الراتب يرى مبلًغا مقتطًعا ولا
يبلغ سبَبه ولا من اعتمده ولا حقَّ الاعتراض عليه.

والرابط هو أيًضا **حارس التكرار**: إعادُة تطبيق الأثر لا تُنشئ خصًما
ثانًيا لقرار واحد — وهي الطريقة نفسها التي حُرست بها حالُة نهاية الخدمة
(``source_request_id``): القياس على وجود الشيء لا على بصمة تدقيق.
"""
from alembic import op
import sqlalchemy as sa

revision = "c1d2e3f4a5b"
down_revision = "b8c9d0e1f2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("deductions") as batch:
        batch.add_column(sa.Column("request_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_deductions_request", "requests", ["request_id"], ["id"])
    op.create_index("ix_deductions_request_id", "deductions", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_deductions_request_id", table_name="deductions")
    with op.batch_alter_table("deductions") as batch:
        batch.drop_constraint("fk_deductions_request", type_="foreignkey")
        batch.drop_column("request_id")
