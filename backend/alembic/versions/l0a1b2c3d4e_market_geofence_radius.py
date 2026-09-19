# -*- coding: utf-8 -*-
"""نصُف قطر السياج 200م للأسواق والمجمعات الكبيرة — قرار المالك (2026-09-19).

إحداثيُّ كويت فايندر إحداثيُّ القسيمة، والمحلُّ في سوٍق كبير (الصفاة/المباركية،
أسواق القبلة، مجمع كاظمة، الضجيج) قد يبعد عن مركزها، ونظاُم الموقع داخل
المباني يخطئ بعشرات الأمتار — فيُردّ موظٌف قائٌم في محلّه. والمباني المنفصلة
(الفحيحيل، المرقاب، الري) تبقى 100م.

**لا يمسّ إلا ما بقي على الافتراضي (100م)** — نصُف قطٍر ضُبط باليد يبقى.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "l0a1b2c3d4e"
down_revision = "k9f0a1b2c3d"
branch_labels = None
depends_on = None

MARKET_RADIUS = 200
DEFAULT_RADIUS = 100

#: (رمز الفرع، الرقم الآلي للوحدة) — فروع الأسواق والمجمعات الكبيرة
MARKETS = [
    # مجمع كاظمة التجاري — الجهراء
    ("BN01", "14708253"), ("BN02", "14708237"), ("BN04", "14708229"),
    ("BN06", "14708173"), ("QNK03", "14708413"),
    # أسواق القبلة: الأقمشة والبطانيات، بلوك 2 و4، سوق الصفاة
    ("MAI01", "10225908"), ("MAI02", "10228877"), ("MAI03", "10239779"),
    ("QNK02", "10234409"), ("QNK06", "10231953"), ("QNKZH", "10232091"),
    # الضجيج — مبنى تجاري كبير
    ("QNK01", "14827084"), ("QNK05", "14827105"),
]


def _match(conn, code: str, paci: str):
    row = conn.execute(sa.text("SELECT id FROM branches WHERE address LIKE :pat ORDER BY id"),
                       {"pat": f"%{paci}%"}).first()
    if row:
        return row[0]
    row = conn.execute(sa.text("SELECT id FROM branches WHERE code = :code ORDER BY id"),
                       {"code": code}).first()
    return row[0] if row else None


def _set(src: int, dst: int) -> list[str]:
    conn = op.get_bind()
    changed = []
    for code, paci in MARKETS:
        bid = _match(conn, code, paci)
        if bid is None:
            continue
        res = conn.execute(sa.text(
            "UPDATE branches SET geofence_radius_m = :dst WHERE id = :id AND geofence_radius_m = :src"),
            {"dst": dst, "src": src, "id": bid})
        if res.rowcount:
            changed.append(code)
    return changed


def upgrade() -> None:
    changed = _set(DEFAULT_RADIUS, MARKET_RADIUS)
    print(f"[migration l0a1b2c3d4e] نصف قطر {MARKET_RADIUS}م للأسواق: {len(changed)} {changed}",
          flush=True)


def downgrade() -> None:
    _set(MARKET_RADIUS, DEFAULT_RADIUS)
