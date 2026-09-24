# -*- coding: utf-8 -*-
"""البحث بالرقم الوظيفي — في قائمة الموظفين وفي البحث الشامل (M05، 2026-09-24).

قيس على الإنتاج: البحث بالاسم «رامين» رجّع 3 نتائج، والبحث برقمه الوظيفي
(GUF-HQ-00001) — المطبوع على كل مستند رسمي — رجّع صفرًا في الاثنين.
"""
from tests.conftest import login


def _h(client):
    return {"Authorization": f"Bearer {login(client, '000000000000', 'admin123')}"}


def test_employee_list_search_matches_employee_no(client):
    h = _h(client)
    emps = client.get("/api/employees", params={"company_id": 1}, headers=h).json()
    target = next(e for e in emps if e.get("employee_no"))
    r = client.get("/api/employees", params={"company_id": 1, "q": target["employee_no"]}, headers=h)
    assert r.status_code == 200
    assert any(e["id"] == target["id"] for e in r.json()), (target["employee_no"], r.json())


def test_global_search_matches_employee_no(client):
    h = _h(client)
    emps = client.get("/api/employees", params={"company_id": 1}, headers=h).json()
    target = next(e for e in emps if e.get("employee_no"))
    r = client.get("/api/search", params={"q": target["employee_no"]}, headers=h)
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()["results"].get("employees", [])]
    assert target["id"] in ids, (target["employee_no"], r.json())
