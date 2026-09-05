# -*- coding: utf-8 -*-
"""مرحلة استلام لطلب الإجازة.

بعد إلغاء انتظار التوقيع (``e5f6a7b8c9d``) صارت الإجازة تُغلَق عند شؤون
الموظفين: يصدر المستند وتقول الشاشة «مكتمل» ولا يُقال لأحد أين يأخذه.

**والبذر يُدرج ولا يُحدِّث** (درس QA-07): بلا هذا الترحيل تبقى سلاسل
الشركات القائمة بلا مرحلة استلام.

**ولا يُكتَب فوق تخصيص**: السلسلة صفٌّ لكل شركة، وقد تكون شركة عدّلتها.
فالترحيل يقرأ كل صفّ ويُلحق المرحلة **إن لم تكن فيه** — وترتيبها بعد آخر
مرحلة قائمة، لا رقًما مفترًضا. وهو بذلك قابل لإعادة التشغيل.

Revision ID: f6a7b8c9d0e
Revises: e5f6a7b8c9d
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e"
down_revision = "e5f6a7b8c9d"
branch_labels = None
depends_on = None

LEAVE_CODES = ("leave", "REQLV", "annual_leave", "sick_leave")

STAGE = {"label": "جاهزة للاستلام من شؤون الموظفين", "role": "hr",
         "kind": "pickup"}


def _rows(conn):
    marks = ", ".join(f":c{i}" for i in range(len(LEAVE_CODES)))
    params = {f"c{i}": c for i, c in enumerate(LEAVE_CODES)}
    return conn.execute(
        sa.text(f"SELECT id, approval_chain_json FROM request_types "
                f"WHERE code IN ({marks})"), params).fetchall()


def _chain(raw):
    """السلسلة قد تصل نًصا أو مفكوكًة بحسب المحرّك — والقراءة تحتمل الاثنين."""
    if isinstance(raw, str):
        raw = json.loads(raw or "[]")
    return list(raw or [])


def _save(conn, row_id, chain):
    conn.execute(
        sa.text("UPDATE request_types SET approval_chain_json = :c "
                "WHERE id = :i"),
        {"c": json.dumps(chain, ensure_ascii=False), "i": row_id})


def upgrade():
    conn = op.get_bind()
    for row_id, raw in _rows(conn):
        chain = _chain(raw)
        if any(s.get("kind") == "pickup" for s in chain):
            continue
        order = max((s.get("order", 0) for s in chain), default=-1) + 1
        _save(conn, row_id, chain + [{"order": order, **STAGE}])


def downgrade():
    conn = op.get_bind()
    for row_id, raw in _rows(conn):
        chain = _chain(raw)
        kept = [s for s in chain if s.get("kind") != "pickup"]
        if len(kept) != len(chain):
            _save(conn, row_id, kept)
