# -*- coding: utf-8 -*-
"""M08 #6 — تفاصيل الطلب: المفاتيح الداخلية (_*) لا تُعرض، وما ليس من الـschema يُميَّز حقلًا إضافيًا.

الخادم يقبل مفاتيح خارج الـschema عمدًا (قِيس أن مسارات مشروعة ترسلها: ``_attachments``، ``addressed_to``…)،
فالحمايةُ في العرض: لا يُقرأ مفتاحٌ أدخله المُرسِل صفًّا من نموذج النوع.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend" / "src"


def test_the_payload_view_hides_internal_keys_and_marks_extras():
    src = (ROOT / "components" / "PayloadView.tsx").read_text(encoding="utf-8")
    assert '!k.startsWith("_")' in src
    assert "pv_extra_field" in src
    i18n = (ROOT / "i18n.tsx").read_text(encoding="utf-8")
    line = next(l for l in i18n.splitlines() if l.strip().startswith("pv_extra_field:"))
    assert "ar:" in line and "en:" in line
