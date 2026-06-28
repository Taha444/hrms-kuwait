# -*- coding: utf-8 -*-
"""اختبارات نظام الأذونات الدقيق (مصفوفة صفحة×فعل) — مع التوافق الخلفي."""
from tests.conftest import auth_headers, login


def _hr_id(client, admin):
    users = client.get("/api/users", headers=auth_headers(admin), params={"company_id": 1}).json()
    return next(u["id"] for u in users if u["civil_id"] == "100000000002")


def test_matrix_catalog(client):
    admin = login(client, "000000000000", "admin123")
    r = client.get("/api/users/permission-matrix", headers=auth_headers(admin))
    assert r.status_code == 200
    codes = [p["code"] for p in r.json()["pages"]]
    assert "employees" in codes and "approve" in r.json()["actions_ar"]


def test_granular_override_restricts_then_resets(client):
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    hr_id = _hr_id(client, admin)

    # افتراضيًا HR يضيف موظفًا (من صلاحيات دوره)
    hr = login(client, "100000000002", "hr12345")
    assert client.get("/api/employees", headers=auth_headers(hr)).status_code == 200

    # قيّد HR على صفحة الموظفين: قراءة فقط
    r = client.post(f"/api/users/{hr_id}/matrix", headers=ah,
                    json={"grants": {"employees": ["read"]}})
    assert r.status_code == 200, r.text

    hr = login(client, "100000000002", "hr12345")
    h = auth_headers(hr)
    assert client.get("/api/employees", headers=h).status_code == 200       # قراءة مسموحة
    add = client.post("/api/employees", headers=h, json={"name": "س", "basic_salary": 100})
    assert add.status_code == 403                                            # الإضافة ممنوعة الآن

    # المصفوفة تعكس التقييد
    m = client.get(f"/api/users/{hr_id}/matrix", headers=ah).json()
    assert m["matrix"]["employees"]["read"] is True
    assert m["matrix"]["employees"]["add"] is False
    assert "employees" in m["custom_pages"]

    # إعادة التعيين → يعود لصلاحيات الدور
    assert client.post(f"/api/users/{hr_id}/matrix/reset", headers=ah).status_code == 200
    m2 = client.get(f"/api/users/{hr_id}/matrix", headers=ah).json()
    assert m2["matrix"]["employees"]["add"] is True
    assert "employees" not in m2["custom_pages"]


def test_other_pages_unaffected_by_role_default(client):
    # مستخدم بلا أي مصفوفة دقيقة يبقى على صلاحيات دوره (توافق خلفي)
    mgr = login(client, "100000000001", "manager123")
    assert client.get("/api/employees", headers=auth_headers(mgr)).status_code == 200


def test_seven_actions_exposed_and_derived(client):
    admin = login(client, "000000000000", "admin123")
    ah = auth_headers(admin)
    # الكتالوج يعرض الأفعال الجديدة (طباعة/تصدير) على صفحة الموظفين
    cat = client.get("/api/users/permission-matrix", headers=ah).json()["pages"]
    emp = next(p for p in cat if p["code"] == "employees")
    assert {"print", "export"} <= set(emp["actions"])

    hr_id = _hr_id(client, admin)
    # HR بلا تخصيص يرث الطباعة من القراءة (read ⇒ print)
    m = client.get(f"/api/users/{hr_id}/matrix", headers=ah).json()["matrix"]
    assert m["employees"]["read"] is True and m["employees"]["print"] is True

    # تقييد الصفحة على القراءة فقط ⇒ تُمنع الطباعة (لا يتسرّب الافتراضي المشتقّ)
    client.post(f"/api/users/{hr_id}/matrix", headers=ah, json={"grants": {"employees": ["read"]}})
    m2 = client.get(f"/api/users/{hr_id}/matrix", headers=ah).json()["matrix"]
    assert m2["employees"]["read"] is True and m2["employees"]["print"] is False
    client.post(f"/api/users/{hr_id}/matrix/reset", headers=ah)
