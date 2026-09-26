# -*- coding: utf-8 -*-
"""M08 #2 — حقلٌ شرطيٌّ يصير مخفيًّا تُمسح قيمتُه في الواجهة، فلا يُرسَل ما يرفضه الخادم.

الخادم يرفض حقلًا مخفيًّا يحمل قيمة (P9-32). كانت الواجهة تُخفيه وتُبقي قيمته في الحمولة: من أشّر السفر وكتب
الوجهة ثم ألغى التأشير رُفض طلبُه بأمرٍ بمسح حقلٍ لا يراه. الجزءان: الخادم يرفض (يُقاس هنا)، والواجهة تمسح (حارسُ مصدر).
"""
from pathlib import Path

from tests.conftest import auth_headers, login

SCREEN = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "SchemaForm.tsx"


def test_the_server_refuses_a_filled_hidden_field(client):
    from app import form_schemas
    schema = next(s for s in form_schemas.SCHEMAS.values()
                  if any("show" in c for c in (s.get("conditional") or [])))
    cond = next(c for c in schema["conditional"] if c.get("show"))
    gated = cond["show"][0]
    code = next(c for c, s in form_schemas.SCHEMAS.items() if s is schema)
    errors = form_schemas.validate_payload(code, {gated: "x"}, strict=False)
    assert any(gated in e and "الشرط" in e for e in errors), errors


def test_the_form_clears_fields_that_become_hidden():
    src = SCREEN.read_text(encoding="utf-8")
    assert "evalConditionals(schema, next).hidden.forEach" in src and "delete next[h]" in src
