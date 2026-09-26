# -*- coding: utf-8 -*-
"""M24 #7 — إعدادات النظام (أعلام الميزات): قيمةٌ غير معروفة وشركةٌ غير موجودة تُرفضان بدل أن تُخزَّنا."""
from tests.conftest import auth_headers, login

KEY = "v15_status_labels"


def _set(client, h, **body):
    return client.post("/api/feature-flags", headers=h, json={"key": KEY, **body})


def test_a_boolean_flag_rejects_unknown_values_and_missing_companies(client):
    h = auth_headers(login(client, "000000000000", "admin123"))
    for bad in ("maybe", "", "2", "tru"):
        r = _set(client, h, value=bad)
        assert r.status_code == 400, (bad, r.status_code, r.text[:100])
    assert _set(client, h, value="on", company_id=999999).status_code == 400
    ok = _set(client, h, value="off")
    assert ok.status_code == 201, ok.text
    assert _set(client, h, value="TRUE").status_code == 201          # المفردات المعروفة تُقبل بأيّ حالة أحرف
    _set(client, h, value="off")                                      # يُعاد للقيمة الافتراضية
