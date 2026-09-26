# -*- coding: utf-8 -*-
"""M08 #3 — قاعدةُ الشهر التي يفرضها الخادم (YYYY-MM) تحملها الواجهة كذلك: لا نصٌّ حرٌّ يُرفض بعد الإرسال.

الحارس يشتقّ الحقولَ من الـschema نفسه (لا قائمةٌ يدوية)، ويقيس على الاستجابة التي تبني منها الواجهةُ الفورم.
"""
from pathlib import Path

from app import form_schemas
from tests.conftest import auth_headers, login

SCREEN = Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "SchemaForm.tsx"


def _month_fields():
    return [(code, f["code"]) for code, s in form_schemas.SCHEMAS.items()
            for f in s.get("fields", []) if f.get("format") == "month"]


def test_every_month_field_is_served_with_its_format(client):
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    found = 0
    for code, field in _month_fields():
        for h in (hr, emp):
            r = client.get(f"/api/requests/types/{code}/schema", headers=h)
            if r.status_code != 200:
                continue
            served = {f["code"]: f for f in r.json()["schema"].get("fields", [])}
            if field in served:
                assert served[field].get("format") == "month", (code, field)
                found += 1
                break
    assert found >= 3, "لم تُخدَم حقولُ الشهر للعميل — القياسُ معطوب"


def test_the_form_renders_month_fields_as_month_inputs():
    src = SCREEN.read_text(encoding="utf-8")
    assert '.format === "month"' in src and '"month"' in src and "[0-9]{4}-(0[1-9]|1[0-2])" in src
