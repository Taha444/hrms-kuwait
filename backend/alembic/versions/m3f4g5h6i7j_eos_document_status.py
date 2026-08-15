# -*- coding: utf-8 -*-
"""V2.2 §3.3/§15 (AP-04) — فصل دورة مستند نهاية الخدمة عن حالة الحالة.

كانت الحالة تمتدّ: settled → ready_to_print → printed → filed. فحالة تشغيلية
(هل طُبعت الورقة؟) تختلط بحالة قانونية (هل صُرفت المستحقات؟) — فتبدو تسوية
مصروفة "غير مكتملة" لأن أحًدا لم يطبعها، وتعدّ تقاريرُ الإنهاء الطباعةَ إنجاًزا.

الحالة تنتهي عند settled، والطباعة/الأرشفة في document_status.

Revision ID: m3f4g5h6i7j
Revises: l2e3f4g5h6i
"""
from alembic import op
import sqlalchemy as sa

revision = "m3f4g5h6i7j"
down_revision = "l2e3f4g5h6i"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("eos_cases")}
    if "document_status" not in cols:
        op.add_column("eos_cases", sa.Column("document_status", sa.String(20),
                                             nullable=False, server_default="PENDING"))
    # الحالات القائمة: تُنقل حالتها الورقية إلى عمودها وتعود الحالة إلى settled
    bind.execute(sa.text(
        "UPDATE eos_cases SET document_status = CASE status "
        "WHEN 'ready_to_print' THEN 'READY' WHEN 'printed' THEN 'PRINTED' "
        "WHEN 'filed' THEN 'FILED' ELSE document_status END, "
        "status = CASE WHEN status IN ('ready_to_print','printed','filed') "
        "THEN 'settled' ELSE status END"))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE eos_cases SET status = CASE document_status "
        "WHEN 'READY' THEN 'ready_to_print' WHEN 'PRINTED' THEN 'printed' "
        "WHEN 'FILED' THEN 'filed' ELSE status END "
        "WHERE status = 'settled'"))
    cols = {c["name"] for c in sa.inspect(bind).get_columns("eos_cases")}
    if "document_status" in cols:
        op.drop_column("eos_cases", "document_status")
