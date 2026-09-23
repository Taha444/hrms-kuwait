# -*- coding: utf-8 -*-
"""شركةٌ صريحة تخالف شركة الجلسة تُرفَض في الرواتب ولا تُستبدَل بصمت (SW-009).

قيس على الإنتاج: محاسبٌ عضوٌ في ثلاث شركات طلب معاينة رواتب الرابعة فتلقّى رواتب الأولى
بحالة 200 — الردّ يقول ``company_id: 1`` لكن السكربت لا يقرؤه.
"""
from tests.conftest import login


def _h(client):
    return {"Authorization": f"Bearer {login(client, '100000000001', 'manager123')}"}


def test_an_explicit_other_company_is_refused_not_swapped(client):
    h = _h(client)
    ok = client.get("/api/payroll/preview", params={"period": "2020-01"}, headers=h)
    assert ok.status_code == 200, ok.text
    own = ok.json()["company_id"]
    same = client.get("/api/payroll/preview", params={"period": "2020-01", "company_id": own},
                      headers=h)
    assert same.status_code == 200 and same.json()["company_id"] == own
    other = client.get("/api/payroll/preview", params={"period": "2020-01", "company_id": own + 1},
                       headers=h)
    assert other.status_code == 403 and "بدّل الشركة" in other.text, other.text
    runs = client.get("/api/payroll/runs", params={"company_id": own + 1}, headers=h)
    assert runs.status_code == 403, runs.text


def test_the_top_admin_still_chooses_any_company(client):
    admin = {"Authorization": f"Bearer {login(client, '000000000000', 'admin123')}"}
    r = client.get("/api/payroll/preview", params={"period": "2020-01", "company_id": 2},
                   headers=admin)
    assert r.status_code == 200 and r.json()["company_id"] == 2, r.text
