# -*- coding: utf-8 -*-
"""Seed notification template DOC-CUSTOM-EXPIRING for custom-doc expiry alerts.

Revision ID: i2b3c4d5e6f
Revises: h1a2b3c4d5e
Create Date: 2026-08-09

R9 §10 — يبذر قالب إشعار خاص بانتهاء المستندات المخصّصة، بحيث الـscanner
يقدر يستخدم notify_from_template بدل create_task المباشر — فيستفيد من:
  - SLA hours (24 ساعة) → المهمة تُصعَّد للـHR/manager لو ما اتنفذت في الوقت
  - channel_default (in_app) → قابل للتحويل لواتساب/SMS من إعدادات المستخدم
  - category (documents) → المستخدم يقدر يفصل قناة تسليم فئة المستندات بالكامل

Downgrade يشيل القالب فقط.
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = "i2b3c4d5e6f"
down_revision: Union[str, None] = "h1a2b3c4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TEMPLATE_CODE = "DOC-CUSTOM-EXPIRING"
_TEMPLATE_NAME = "مستند مخصّص قارب على الانتهاء"
_TEMPLATE_BODY = (
    "المستند «{{title}}» الخاص بـ{{entity_kind}} {{entity_name}} "
    "ينتهي خلال {{days_left}} يومًا (بتاريخ {{expiry_date}}). "
    "الرجاء المتابعة."
)


def upgrade() -> None:
    conn = op.get_bind()
    exists = conn.execute(
        text("SELECT id FROM notification_templates WHERE code = :c LIMIT 1"),
        {"c": _TEMPLATE_CODE},
    ).first()
    if exists:
        return
    conn.execute(text("""
        INSERT INTO notification_templates
            (code, name, category, event_type, channel_default, sla_hours,
             body_text, is_active, created_at)
        VALUES
            (:code, :name, 'documents', 'doc_expiring', 'in_app', 24,
             :body, TRUE, NOW())
    """), {"code": _TEMPLATE_CODE, "name": _TEMPLATE_NAME, "body": _TEMPLATE_BODY})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DELETE FROM notification_templates WHERE code = :c"),
                 {"c": _TEMPLATE_CODE})
