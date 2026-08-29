# -*- coding: utf-8 -*-
"""TSK-01/TSK-05 — قيد فريد يمنع تكرار المهام المفتوحة + تنظيف القائم

منع التكرار كان في الشيفرة وحدها: ``create_task`` يبحث عن مهمة مفتوحة
بنفس ``dedup_key`` ويتخطّى. وفحص في الشيفرة يُخترق عند التزامن — نسختان
تقرآن «لا يوجد» في اللحظة نفسها فتكتب كلٌّ منهما صفًّا. وهذا بالضبط ما
يحدث مع الفحص اليومي المتكرر وتعدّد النسخ على AWS.

والقيد هنا **جزئي**: على المفتوح وحده. المهام المنتهية تتكرّر بطبيعتها —
معاملة تُجدَّد كل سنة تُنشئ المهمة نفسها كل سنة، ومنع ذلك يمنع العمل لا
التكرار.

والترتيب مقصود: يُنظَّف القائم **قبل** إنشاء الفهرس، وإلا رفضته القاعدة
على بيانات موجودة وسقط النشر.

Revision ID: b6c7d8e9f0a
Revises: a5b6c7d8e9f
"""
from alembic import op
import sqlalchemy as sa

revision = "b6c7d8e9f0a"
down_revision = "a5b6c7d8e9f"
branch_labels = None
depends_on = None

_OPEN = "('open', 'in_progress')"


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # TSK-05 — تنظيف مراجَع، لا مسح
    # ------------------------------------------------------------------
    # (1) المكرّر: يبقى الأقدم — هو الذي رآه المستخدم وربما بدأه.
    #     والباقي يُوسَم dismissed لا يُحذف: صندوق المهام سجلّ أيًضا، ومن
    #     يفتّش لاحًقا يحتاج أن يعرف أن التكرار وقع وكيف عولج.
    conn.execute(sa.text(f"""
        UPDATE tasks SET status = 'dismissed'
        WHERE status IN {_OPEN}
          AND dedup_key IS NOT NULL
          AND id NOT IN (
              SELECT MIN(id) FROM tasks
              WHERE status IN {_OPEN} AND dedup_key IS NOT NULL
              GROUP BY dedup_key
          )
    """))

    # (2) مهام مفتوحة لمعاملات تجديد انتهت أو أُلغيت — عمل مطلوب لشيء
    #     لم يعد قائًما.
    conn.execute(sa.text(f"""
        UPDATE tasks SET status = 'dismissed'
        WHERE status IN {_OPEN}
          AND related_entity_type = 'renewal'
          AND related_entity_id IN (
              SELECT id FROM residency_renewals
              WHERE status IN ('completed', 'rejected')
          )
    """))

    # ------------------------------------------------------------------
    # TSK-01 — القيد نفسه
    # ------------------------------------------------------------------
    op.create_index(
        "uq_tasks_open_dedup", "tasks", ["dedup_key"], unique=True,
        sqlite_where=sa.text(f"status IN {_OPEN} AND dedup_key IS NOT NULL"),
        postgresql_where=sa.text(f"status IN {_OPEN} AND dedup_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_tasks_open_dedup", table_name="tasks")
