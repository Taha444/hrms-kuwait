# -*- coding: utf-8 -*-
"""اختبار شامل للـ API باستخدام Flask test client (بدون شبكة)."""
import json

from app import app

app.testing = True


def show(label, resp):
    try:
        data = resp.get_json()
    except Exception:
        data = resp.data.decode()[:200]
    print(f"[{resp.status_code}] {label}")
    return data


def main():
    failures = []

    # 1) محاولة وصول بدون تسجيل دخول
    with app.test_client() as c:
        r = c.get("/api/employees")
        show("employees بدون دخول (متوقع 401)", r)
        assert r.status_code == 401

    # 2) دخول Super Admin
    with app.test_client() as c:
        r = c.post("/api/login", json={"username": "admin", "password": "admin123"})
        data = show("login admin", r)
        assert r.status_code == 200, data
        assert data["role"] == "super_admin"
        assert "manage_companies" in data["permissions"]

        # الشركات
        r = c.get("/api/companies")
        comps = show("companies", r)
        print("   عدد الشركات:", len(comps))
        assert len(comps) == 2

        # كل الموظفين (super admin يرى الجميع)
        r = c.get("/api/employees")
        emps = show("all employees", r)
        print("   إجمالي الموظفين:", len(emps))
        assert len(emps) == 6

        # موظفي شركة 1 فقط
        r = c.get(f"/api/employees?company_id={comps[0]['id']}")
        e1 = show("employees company 1", r)
        print("   موظفو الشركة 1:", len(e1))
        assert len(e1) == 4

        # التراخيص + تجاوز السعة
        r = c.get(f"/api/licenses?company_id={comps[0]['id']}")
        lics = show("licenses company 1", r)
        over = [lic for lic in lics if lic["over_capacity"]]
        print("   تراخيص متجاوزة السعة:", len(over),
              "| فعلي/مسموح:", lics[0]["actual_workers"], "/", lics[0]["allowed_workers"])
        assert lics[0]["actual_workers"] == 4 and lics[0]["allowed_workers"] == 3
        assert len(over) == 1  # 4 موظفين على ترخيص يسمح بـ 3

        # التنبيهات
        r = c.get("/api/alerts")
        al = show("alerts (all)", r)
        print("   عدد التنبيهات:", len(al))
        sev = {}
        for a in al:
            sev[a["severity"]] = sev.get(a["severity"], 0) + 1
        print("   حسب الخطورة:", sev)
        assert any(a["severity"] == "expired" for a in al)   # إقامة منتهية
        assert any(a["type"] == "capacity" for a in al)       # تجاوز سعة

        # حساب نهاية الخدمة لموظف (يستخدم سياسة الشركة)
        khalid = [e for e in e1 if "خالد" in e["name"]][0]
        r = c.post("/api/eos/calculate", json={"employee_id": khalid["id"], "reason": "termination"})
        eos = show("EOS خالد (فصل)", r)
        print("   الخدمة:", eos["service"]["text"], "| المكافأة:", eos["indemnity"], eos["currency"],
              "| اليوم÷", eos["inputs"]["day_divisor"])
        assert eos["indemnity"] > 0

        # استقالة بأقل من 3 سنوات → صفر
        r = c.post("/api/eos/calculate", json={
            "basic_salary": 500, "hire_date": "2024-01-01", "end_date": "2025-06-01",
            "reason": "resignation", "contract_type": "indefinite"})
        eos2 = show("EOS استقالة <3 سنوات (متوقع 0)", r)
        print("   نسبة الاستحقاق:", eos2["entitlement_factor"], "| المكافأة:", eos2["indemnity"])
        assert eos2["indemnity"] == 0.0

        # تقرير ملخص
        r = c.get("/api/reports/summary")
        summ = show("reports summary", r)
        print("   ملخص:", json.dumps(summ, ensure_ascii=False))
        assert summ["total_employees"] == 6

        # تصدير CSV
        r = c.get("/api/reports/export/employees")
        print(f"[{r.status_code}] export employees CSV | حجم:", len(r.data), "بايت")
        assert r.status_code == 200 and b"," in r.data

    # 3) عزل البيانات: مدير الشركة 1 لا يرى موظفي الشركة 2
    with app.test_client() as c:
        r = c.post("/api/login", json={"username": "manager1", "password": "manager123"})
        data = show("login manager1", r)
        assert r.status_code == 200
        company1_id = data["company_id"]

        r = c.get("/api/employees")
        emps = show("manager1 يرى الموظفين", r)
        print("   عدد:", len(emps), "| كلهم بنفس الشركة:",
              all(e["company_id"] == company1_id for e in emps))
        assert len(emps) == 4
        assert all(e["company_id"] == company1_id for e in emps)

        # محاولة إنشاء شركة (ممنوع لغير الإدارة العليا)
        r = c.post("/api/companies", json={"name": "شركة وهمية"})
        show("manager1 ينشئ شركة (متوقع 403)", r)
        assert r.status_code == 403

    # 4) صلاحيات: موظف hr1 ليس لديه calculate_eos
    with app.test_client() as c:
        r = c.post("/api/login", json={"username": "hr1", "password": "hr12345"})
        data = show("login hr1", r)
        assert r.status_code == 200
        print("   صلاحيات hr1:", data["permissions"])

        r = c.get("/api/employees")
        show("hr1 يعرض الموظفين (مسموح)", r)
        assert r.status_code == 200

        r = c.post("/api/eos/calculate", json={"basic_salary": 500, "hire_date": "2020-01-01"})
        d = show("hr1 يحسب نهاية الخدمة (متوقع 403)", r)
        assert r.status_code == 403
        print("   الصلاحية الناقصة:", d.get("missing_permission"))

        r = c.post("/api/companies", json={"name": "x"})
        show("hr1 ينشئ شركة (متوقع 403)", r)
        assert r.status_code == 403

    # 5) قفل الحساب بعد محاولات فاشلة
    with app.test_client() as c:
        for i in range(5):
            c.post("/api/login", json={"username": "manager2", "password": "wrong"})
        r = c.post("/api/login", json={"username": "manager2", "password": "manager123"})
        d = show("manager2 بعد 5 محاولات خاطئة (متوقع حظر)", r)
        print("   الرسالة:", d.get("error"))
        assert r.status_code in (401, 423)

    print("\n" + "=" * 50)
    if failures:
        print("✗ فشلت بعض الاختبارات:", failures)
    else:
        print("✓ جميع اختبارات الـ API نجحت")
    print("=" * 50)


if __name__ == "__main__":
    main()
