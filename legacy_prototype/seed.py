# -*- coding: utf-8 -*-
"""
سكربت تعبئة بيانات تجريبية. يُنشئ:
- مستخدم إدارة عليا (Super Admin)
- شركتين بسياسات نهاية خدمة مختلفة
- مدير لكل شركة + موظف بصلاحيات محددة
- تراخيص وموظفين وإقامات (بعضها قرب الانتهاء لتجربة التنبيهات)
"""
import sqlite3
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

import db as dbmod

DB_PATH = dbmod.DB_PATH


def d(days):
    return (date.today() + timedelta(days=days)).isoformat()


def run():
    # تهيئة قاعدة البيانات
    dbmod.init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # تنظيف الجداول (إعادة تعبئة نظيفة)
    for t in ["user_permissions", "permits", "deductions", "allowances", "leaves",
              "attendance", "disciplinary_actions", "assets", "performance_reviews",
              "employment_history", "eos_settlements", "payslips", "payroll_runs",
              "notifications", "departments", "documents",
              "transfers", "audit_log", "employees", "licenses", "business_files",
              "users", "companies"]:
        cur.execute(f"DELETE FROM {t}")
    conn.commit()

    # ---- الإدارة العليا ----
    cur.execute(
        "INSERT INTO users (company_id, username, password_hash, full_name, role) VALUES (?,?,?,?,?)",
        (None, "admin", generate_password_hash("admin123"), "مدير النظام العام", "super_admin"),
    )

    # ---- الشركة الأولى: مقاولات (مقسوم 26) ----
    cur.execute(
        """INSERT INTO companies (name, name_en, commercial_reg, entity_type, status,
                                  eos_day_divisor, eos_max_months, alert_lead_days)
           VALUES (?,?,?,?,?,?,?,?)""",
        ("شركة الخليج للمقاولات", "Gulf Contracting Co.", "123456", "ذات مسؤولية محدودة",
         "active", 26, 18, 30),
    )
    c1 = cur.lastrowid

    # ---- الشركة الثانية: تجارة (مقسوم 30) ----
    cur.execute(
        """INSERT INTO companies (name, name_en, commercial_reg, entity_type, status,
                                  eos_day_divisor, eos_max_months, alert_lead_days)
           VALUES (?,?,?,?,?,?,?,?)""",
        ("شركة الوطنية للتجارة", "National Trading Co.", "654321", "شركة شخص واحد",
         "active", 30, 18, 45),
    )
    c2 = cur.lastrowid

    # ---- مديرو الشركات ----
    cur.execute(
        "INSERT INTO users (company_id, username, password_hash, full_name, role) VALUES (?,?,?,?,?)",
        (c1, "manager1", generate_password_hash("manager123"), "مدير شركة المقاولات", "company_manager"),
    )
    cur.execute(
        "INSERT INTO users (company_id, username, password_hash, full_name, role) VALUES (?,?,?,?,?)",
        (c2, "manager2", generate_password_hash("manager123"), "مدير الشركة الوطنية", "company_manager"),
    )

    # ---- موظف بصلاحيات محددة (الشركة 1) ----
    cur.execute(
        "INSERT INTO users (company_id, username, password_hash, full_name, role) VALUES (?,?,?,?,?)",
        (c1, "hr1", generate_password_hash("hr12345"), "موظف موارد بشرية", "employee"),
    )
    hr_uid = cur.lastrowid
    for p in ["view_employee", "create_employee", "edit_employee", "manage_permits",
              "view_alerts", "view_reports"]:
        cur.execute("INSERT INTO user_permissions (user_id, perm_code) VALUES (?,?)", (hr_uid, p))

    # ---- التراخيص ----
    cur.execute(
        """INSERT INTO licenses (company_id, name, license_no, issuing_authority, license_type,
                                 status, issue_date, expiry_date, allowed_workers, address)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (c1, "ترخيص مقاولات إنشائية", "LIC-001", "بلدية الكويت", "main", "active",
         d(-700), d(20), 3, "حولي - الكويت"),  # ينتهي خلال 20 يوم → تنبيه
    )
    lic1 = cur.lastrowid
    cur.execute(
        """INSERT INTO licenses (company_id, name, license_no, issuing_authority, license_type,
                                 status, issue_date, expiry_date, allowed_workers, address)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (c2, "ترخيص تجاري عام", "LIC-100", "وزارة التجارة والصناعة", "main", "active",
         d(-400), d(200), 10, "العاصمة - الكويت"),
    )
    lic2 = cur.lastrowid

    # ---- موظفو الشركة 1 ----
    employees_c1 = [
        ("289010112345", "أحمد محمود علي", "مصري", "عامل", "مهندس موقع", 850, d(-1500), lic1),
        ("288050298765", "راجيش كومار", "هندي", "عامل", "فني كهرباء", 450, d(-900), lic1),
        ("290111054321", "محمد حسن", "سوري", "عامل", "نجار", 400, d(-300), lic1),
        ("287070167890", "خالد العتيبي", "كويتي", "موظف", "مدير مشاريع", 1500, d(-2600), lic1),
    ]
    emp_ids_c1 = []
    for civ, name, nat, wt, job, sal, hire, lic in employees_c1:
        cur.execute(
            """INSERT INTO employees (company_id, civil_id, name, nationality, worker_type,
                                      job_title, basic_salary, hire_date, status, license_id, contract_type)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (c1, civ, name, nat, wt, job, sal, hire, "active", lic, "indefinite"),
        )
        emp_ids_c1.append(cur.lastrowid)

    # ---- موظفو الشركة 2 ----
    for civ, name, nat, wt, job, sal, hire in [
        ("291020156789", "سارة الأحمد", "كويتية", "موظف", "محاسبة", 700, d(-600)),
        ("286090145678", "جون سميث", "بريطاني", "موظف", "مستشار", 1200, d(-1100)),
    ]:
        cur.execute(
            """INSERT INTO employees (company_id, civil_id, name, nationality, worker_type,
                                      job_title, basic_salary, hire_date, status, license_id, contract_type)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (c2, civ, name, nat, wt, job, sal, hire, "active", lic2, "indefinite"),
        )

    # ---- إقامات وأذونات عمل (بعضها قرب الانتهاء) ----
    permit_rows = [
        (emp_ids_c1[0], "residency", "RES-1001", d(-360), d(5)),    # حرج: 5 أيام
        (emp_ids_c1[0], "work_permit", "WP-1001", d(-360), d(35)),
        (emp_ids_c1[1], "residency", "RES-1002", d(-300), d(-3)),   # منتهي
        (emp_ids_c1[2], "residency", "RES-1003", d(-200), d(60)),
        (emp_ids_c1[3], "residency", "RES-1004", d(-700), d(120)),
    ]
    for eid, kind, num, sd, ed in permit_rows:
        cur.execute(
            "INSERT INTO permits (company_id, employee_id, kind, number, start_date, expiry_date, status) VALUES (?,?,?,?,?,?,?)",
            (c1, eid, kind, num, sd, ed, "active"),
        )

    # ---- مستند قرب الانتهاء ----
    cur.execute(
        "INSERT INTO documents (company_id, entity_type, entity_id, title, file_path, expiry_date) VALUES (?,?,?,?,?,?)",
        (c1, "company", c1, "شهادة التأمينات الاجتماعية", None, d(15)),
    )

    # ---- خصم تجريبي ----
    cur.execute(
        "INSERT INTO deductions (company_id, employee_id, amount, reason, ded_type, date) VALUES (?,?,?,?,?,?)",
        (c1, emp_ids_c1[1], 25, "تأخير متكرر", "violation", d(-10)),
    )

    # ---- ملف تجاري للشركة 1 ----
    cur.execute(
        """INSERT INTO business_files (company_id, file_no, file_name, status, issue_date,
                                       commercial_reg, classification, authority, legal_entity_type,
                                       ownership_category, workers_count, licenses_count)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (c1, "BF-001", "الملف الرئيسي", "نشط", d(-1500), "123456", "مقاولات",
         "الهيئة العامة للقوى العاملة", "ذات مسؤولية محدودة", "خاص", 4, 1),
    )

    conn.commit()
    conn.close()

    print("=" * 55)
    print(" تمت تعبئة البيانات التجريبية بنجاح")
    print("=" * 55)
    print(" حسابات الدخول:")
    print("  • إدارة عليا   : admin    / admin123")
    print("  • مدير شركة 1  : manager1 / manager123")
    print("  • مدير شركة 2  : manager2 / manager123")
    print("  • موظف (صلاحيات محدودة): hr1 / hr12345")
    print("=" * 55)


if __name__ == "__main__":
    run()
