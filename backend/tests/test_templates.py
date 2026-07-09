# -*- coding: utf-8 -*-
"""اختبار وحدة الصيغ والنماذج: التعبئة التلقائية ببيانات الموظف + العزل."""
from tests.conftest import auth_headers, login


def _emp_id(client, hr_token):
    emps = client.get("/api/employees", headers=auth_headers(hr_token)).json()
    return emps[0]["id"], emps[0]["name"]


def test_list_and_render_autofills_employee(client):
    hr = login(client, "100000000002", "hr12345")
    tpls = client.get("/api/templates", headers=auth_headers(hr)).json()
    assert len(tpls) >= 42  # قوالب HRMS-PR-001..042 ثنائية اللغة المزروعة
    salary = next(t for t in tpls if "راتب" in t["name"])
    assert salary["name_en"]  # عنوان إنجليزي مرافق (تصميم ثنائي اللغة الجديد)
    emp_id, emp_name = _emp_id(client, hr)

    r = client.post(f"/api/templates/{salary['id']}/render", headers=auth_headers(hr),
                    json={"employee_id": emp_id, "extra": {}, "save": True})
    assert r.status_code == 200, r.text
    html = r.json()["html"]
    assert emp_name in html               # الاسم عُبّئ تلقائيًا في شبكة بيانات الموظف
    assert salary["name_en"] in html       # العنوان الإنجليزي ظاهر في الترويسة
    assert "{{" not in html               # لا متغيّرات غير معبّأة
    assert r.json()["document_id"]        # حُفظ في ملف الموظف


def test_render_fills_custom_extra_field(client):
    """آلية extra العامة لا تزال تعمل لأي صيغة تحتوي متغيّرًا مخصًصا (وليست خاصة بالقوالب المزروعة)."""
    admin = login(client, "000000000000", "admin123")
    r = client.post("/api/templates", headers=auth_headers(admin),
                    json={"name": "صيغة تجريبية", "category": "عام",
                          "body_html": "<p>موجّه إلى: {{addressed_to}}</p>"})
    assert r.status_code == 201, r.text
    tpl_id = r.json()["id"]

    hr = login(client, "100000000002", "hr12345")
    emp_id, _ = _emp_id(client, hr)
    r = client.post(f"/api/templates/{tpl_id}/render", headers=auth_headers(hr),
                    json={"employee_id": emp_id, "extra": {"addressed_to": "بنك الخليج"}, "save": False})
    assert r.status_code == 200, r.text
    assert "بنك الخليج" in r.json()["html"]


def test_employee_cannot_manage_templates(client):
    emp = login(client, "100000000101", "emp12345")
    r = client.get("/api/templates", headers=auth_headers(emp))
    assert r.status_code == 403  # الموظف لا يملك manage_templates


def test_template_render_respects_isolation(client):
    # HR الشركة 1 (يملك تعبئة/طباعة القوالب) لا يصل لموظف الشركة 2
    hr1 = login(client, "100000000002", "hr12345")
    tpls = client.get("/api/templates", headers=auth_headers(hr1)).json()
    tpl = tpls[0]
    # احصل على موظف من الشركة 2 عبر الإدارة العليا
    admin = login(client, "000000000000", "admin123")
    emp2 = client.get("/api/employees", headers=auth_headers(admin), params={"company_id": 2}).json()[0]
    r = client.post(f"/api/templates/{tpl['id']}/render", headers=auth_headers(hr1),
                    json={"employee_id": emp2["id"], "extra": {}, "save": False})
    assert r.status_code == 404  # العزل يمنع الوصول
