# -*- coding: utf-8 -*-
"""بذر كتالوج قوالب الإشعارات الـ74 في قاعدة الإنتاج

سبب الترحيل: الجدول كان يُنشأ فارغًا. الترحيل a7b8c9d0e1f2 أنشأ
notification_templates بلا صفوف، والصفوف كانت تُدرَج فقط في seed.py التجريبي —
وهو يمسح كل الجداول ومحظور في الإنتاج (ALLOW_DEMO_SEED). فبقي الجدول في الإنتاج
شبه فارغ (صف DOC-CUSTOM-EXPIRING وحده من الترحيل i2b3c4d5e6f).

وnotify_from_template يرجع None بصمت حين لا يجد القالب:

    tpl = db.scalar(select(NotificationTemplate).where(code == code, is_active))
    if not tpl:
        return None

فكانت **كل** الإشعارات المبنية على قوالب لا تصل أحدًا في الإنتاج — لا إشعار
اكتمال الطلب (NTF-037) وحده. لم يظهر ذلك في الاختبارات لأن conftest يبذر القاعدة
بـseed.py الكامل، فالقوالب موجودة هناك دائمًا.

idempotent: يُدرج الغائب فقط ويُحدّث نصوص الموجود، فلا يكرر ولا يمسح تخصيصًا
أُدخل على is_active من الواجهة.

Revision ID: s2l3m4n5o6p
Revises: r1k2l3m4n5o
"""
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "s2l3m4n5o6p"
down_revision = "r1k2l3m4n5o"
branch_labels = None
depends_on = None


def _catalog():
    """يُقرأ من نفس المصدر الذي يستعمله التطبيق حتى لا تنشأ قائمتان متوازيتان."""
    from app.notification_templates import DEFAULT_NOTIFICATION_TEMPLATES
    return DEFAULT_NOTIFICATION_TEMPLATES


def upgrade() -> None:
    conn = op.get_bind()
    existing = {r[0] for r in conn.execute(sa.text(
        "SELECT code FROM notification_templates"))}

    now = datetime.now(timezone.utc)
    inserted = updated = 0
    for tpl in _catalog():
        if tpl["code"] in existing:
            # نحدّث المحتوى فقط — is_active يبقى كما ضبطته الإدارة
            conn.execute(sa.text("""
                UPDATE notification_templates
                   SET name = :name, category = :category, event_type = :event_type,
                       channel_default = :channel_default, sla_hours = :sla_hours,
                       body_text = :body_text
                 WHERE code = :code
            """), tpl)
            updated += 1
        else:
            conn.execute(sa.text("""
                INSERT INTO notification_templates
                       (code, name, category, event_type, channel_default,
                        sla_hours, body_text, is_active, created_at)
                VALUES (:code, :name, :category, :event_type, :channel_default,
                        :sla_hours, :body_text, TRUE, :created_at)
            """), {**tpl, "created_at": now})
            inserted += 1

    print(f"notification templates: {inserted} inserted, {updated} updated")


def downgrade() -> None:
    # لا نحذف: القوالب مرجع تشغيلي، وحذفها يُسكت الإشعارات مرة أخرى.
    pass
