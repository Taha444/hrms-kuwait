# -*- coding: utf-8 -*-
"""QA-30 — users.totp_recovery_hashes: رموز استرداد 2FA (مُجزَّأة).

بدونها كان فقدان الهاتف قفًلا تاًما: الدخول يستلزم رمز TOTP، وتعطيل 2FA يستلزم
جلسة تستلزم الدخول — حلقة مغلقة لا مخرج منها إلا تعديل يدوي في القاعدة.

NULL = لا رموز بعد. من فعّل 2FA قبل هذا الترحيل يولّدها من
/2fa/recovery/regenerate بعد تأكيد كلمة مروره.

Revision ID: c3v4w5x6y7z
Revises: b2u3v4w5x6y
"""
from alembic import op
import sqlalchemy as sa

revision = "c3v4w5x6y7z"
down_revision = "b2u3v4w5x6y"
branch_labels = None
depends_on = None


def upgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "totp_recovery_hashes" not in cols:
        op.add_column("users", sa.Column("totp_recovery_hashes", sa.JSON(), nullable=True))


def downgrade() -> None:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}
    if "totp_recovery_hashes" in cols:
        op.drop_column("users", "totp_recovery_hashes")
