# -*- coding: utf-8 -*-
"""M22 / SW-018 — شاشة سجلّ التدقيق تعرض كلَّ ما يرجعه ``GET /audit``.

القاعدة تحفظ ستة عشر حقلًا لكل فعل، والـAPI أُكمل ليرجعها كلَّها، لكن **الشاشة** بقيت تعرض
أحدَ عشر: لا نتيجةَ ولا صفةَ ولا سببَ ولا قبل/بعد ولا الفاعلَ الحقيقيّ تحت الانتحال — فلا
يُرى أنجح الفعلُ أم فشل، ولا بأيّ صفةٍ وقع. وأصلُ العطل «موضعان يصفان قاعدةً واحدة»؛ فالحارس
يشتقّ مفاتيحَ الاستجابة من الاستجابة نفسها لا من قائمةٍ يدوية، فحقلٌ يُضاف غدًا يفرض نفسَه.
"""
from __future__ import annotations

from pathlib import Path

from tests.conftest import auth_headers, login

SCREEN = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "Audit.tsx"

#: مفاتيحٌ لا تُعرض بحقلٍ مستقلّ عمدًا: معرّفاتٌ داخلية لا يقرؤها إنسان.
INTERNAL = {"id", "company_id", "branch_id"}


def test_the_screen_renders_every_field_the_endpoint_returns(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    rows = client.get("/api/audit", headers=admin, params={"limit": 5}).json()
    assert rows, "لا صفّ تدقيق لقياس شكل الاستجابة"
    src = SCREEN.read_text(encoding="utf-8")
    missing = sorted(k for k in rows[0] if k not in INTERNAL and f"r.{k}" not in src)
    assert not missing, f"حقولٌ يخزّنها التدقيق ويرجعها الـAPI ولا تعرضها الشاشة: {missing}"
