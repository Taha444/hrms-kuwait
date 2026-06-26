# -*- coding: utf-8 -*-
"""تعبئة بيانات تجريبية: شركتان مستقلتان معزولتان تمامًا.

لكل شركة: مدير + موظف شؤون (قانونية) + مندوبان + فرعان (محلات) ومسؤول لكل فرع
+ ستة موظفين، مع إقامات وحضور وإجازات تجريبية. الإدارة العليا والمالك يختاران
الشركة من شاشة الاختيار، والعزل يمنع أي تداخل بين بيانات الشركتين.

التشغيل:  python -m app.seed
"""
import secrets
import sys
from datetime import date, datetime, time, timedelta

from sqlalchemy import delete

from . import models
from .database import SessionLocal, init_db
from .security import hash_password
from .workflow import DEFAULT_REQUEST_TYPES

PW = {"manager": "manager123", "hr": "hr12345", "delegate": "deleg123",
      "supervisor": "sup12345", "employee": "emp12345"}

COMPANIES = [
    {
        "name": "شركة الخليج للتجارة", "name_en": "Gulf Trading Co.", "reg": "100200",
        "entity": "ذات مسؤولية محدودة", "divisor": 26, "lead": 30, "prefix": "1",
        "branches": [("محل السالمية", 29.3394, 48.0758), ("محل حولي", 29.3328, 48.0263)],
        "employees": [
            ("أحمد محمود علي", "مصري", "بائع", 480, "both"),
            ("راجيش كومار", "هندي", "فني", 420, "qr"),
            ("محمد حسن", "سوري", "مشرف مبيعات", 650, "gps"),
            ("سعيد القحطاني", "سعودي", "محاسب", 700, "qr"),
            ("جون سميث", "بريطاني", "مستشار", 1100, "both"),
            ("خالد العتيبي", "كويتي", "مدير فرع", 900, "none"),
        ],
    },
    {
        "name": "الوطنية للمقاولات", "name_en": "National Contracting Co.", "reg": "300400",
        "entity": "شركة شخص واحد", "divisor": 30, "lead": 45, "prefix": "2",
        "branches": [("موقع الجهراء", 29.3375, 47.6581), ("موقع الأحمدي", 29.0769, 48.0838)],
        "employees": [
            ("علي عبد الله", "مصري", "عامل", 380, "qr"),
            ("سونيل باتيل", "هندي", "كهربائي", 430, "both"),
            ("ماهر يوسف", "أردني", "مهندس موقع", 850, "gps"),
            ("فهد المطيري", "كويتي", "مدير مشروع", 1300, "none"),
            ("بيتر جونز", "فلبيني", "نجار", 360, "qr"),
            ("سارة الأحمد", "كويتية", "محاسبة", 720, "both"),
        ],
    },
]


DEFAULT_TEMPLATES = [
    ("salary_cert", "شهادة راتب", "شهادات",
     "<h2>شهادة راتب</h2>"
     "<p>التاريخ: {{date_today}} — المرجع: {{ref_no}}</p>"
     "<p>تشهد <b>{{company_name}}</b> بأن السيد/ة <b>{{employee_name}}</b> — الرقم المدني "
     "{{civil_id}} — يعمل لدينا بوظيفة <b>{{job_title}}</b> منذ {{hire_date}}، وأن راتبه "
     "الأساسي {{basic_salary}}.</p>"
     "<p>وقد أُعطيت له هذه الشهادة بناءً على طلبه لتقديمها إلى <b>{{addressed_to}}</b>.</p>"
     "<br><br><p>التوقيع والختم: ............................</p>"),
    ("work_letter", "خطاب تعريف بالعمل", "خطابات",
     "<h2>خطاب تعريف بالعمل</h2><p>التاريخ: {{date_today}}</p><p>إلى من يهمه الأمر،</p>"
     "<p>نفيدكم بأن السيد/ة <b>{{employee_name}}</b> ({{nationality}}) — الرقم المدني "
     "{{civil_id}} — يعمل لدى <b>{{company_name}}</b> بوظيفة {{job_title}} منذ {{hire_date}}.</p>"
     "<p>الغرض من الخطاب: {{purpose}}.</p>"
     "<br><br><p>مدير الموارد البشرية: ............................</p>"),
    ("custody", "إقرار استلام عهدة", "نماذج",
     "<h2>إقرار استلام عهدة</h2>"
     "<p>أقر أنا <b>{{employee_name}}</b> — الرقم المدني {{civil_id}} — بأنني استلمت من "
     "<b>{{company_name}}</b> العهدة التالية: <b>{{item}}</b> بتاريخ {{date_today}}، وأتعهد "
     "بالمحافظة عليها وإعادتها عند الطلب.</p>"
     "<br><br><p>توقيع الموظف: ............................</p>"),
]


def civ(prefix: str, n: int) -> str:
    return prefix + str(n).zfill(11)


def d(days: int) -> date:
    return date.today() + timedelta(days=days)


def _add_attendance(db, emp, branch_id, count, late_on=None):
    """يضيف سجلات حضور لأيام العمل الماضية (الأحد..الخميس)."""
    added, i = 0, 1
    while added < count and i < 20:
        day = date.today() - timedelta(days=i)
        i += 1
        our_idx = (day.weekday() + 1) % 7  # 0=الأحد
        if our_idx > 4:  # جمعة/سبت
            continue
        late = (late_on is not None and added == late_on)
        ci = datetime(day.year, day.month, day.day, 8, 42 if late else 8, 3)
        co = datetime(day.year, day.month, day.day, 17, 8)
        worked = int((co - ci).total_seconds() // 60)
        db.add(models.AttendanceRecord(
            company_id=emp.company_id, employee_id=emp.id, branch_id=branch_id,
            check_in_at=ci, check_out_at=co, method=("gps" if emp.attendance_mode == "gps" else "qr"),
            status=("late" if late else "present"), worked_minutes=worked,
            overtime_minutes=max(worked - 540, 0),
            selfie_in_path="(تجريبي)", selfie_out_path="(تجريبي)"))
        added += 1


def build_company(db, cfg) -> dict:
    p = cfg["prefix"]
    company = models.Company(
        name=cfg["name"], name_en=cfg["name_en"], commercial_reg=cfg["reg"],
        entity_type=cfg["entity"], eos_day_divisor=cfg["divisor"], eos_max_months=18,
        alert_lead_days=cfg["lead"])
    db.add(company)
    db.flush()

    # فروع
    branches = []
    for name, lat, lng in cfg["branches"]:
        b = models.Branch(company_id=company.id, name=name, latitude=lat, longitude=lng,
                          geofence_radius_m=120, qr_secret=secrets.token_hex(16),
                          kiosk_key=secrets.token_urlsafe(24), address=name)
        db.add(b)
        branches.append(b)
    db.flush()

    shift = models.Shift(company_id=company.id, name="دوام رسمي", start_time=time(8, 0),
                         end_time=time(17, 0), work_days="0,1,2,3,4", grace_minutes=15)
    license_ = models.License(company_id=company.id, name=f"ترخيص {cfg['name']}",
                              license_no=f"LIC-{p}00", issuing_authority="الهيئة العامة للقوى العاملة",
                              status="active", issue_date=d(-600), expiry_date=d(40 if p == "1" else 200),
                              allowed_workers=8, address=cfg["branches"][0][0])
    db.add(shift)
    db.add(license_)
    db.flush()

    # طاقم الشركة
    def staff(n, role, name, pw):
        u = models.User(civil_id=civ(p, n), password_hash=hash_password(pw), full_name=name,
                        role=role, company_id=company.id, must_change_password=False)
        db.add(u); return u

    manager = staff(1, "company_manager", f"مدير {cfg['name']}", PW["manager"])
    hr = staff(2, "hr", "موظف الشؤون القانونية/الموظفين", PW["hr"])
    deleg1 = staff(3, "delegate", "المندوب الأول", PW["delegate"])
    deleg2 = staff(4, "delegate", "المندوب الثاني", PW["delegate"])
    sup1 = staff(5, "branch_supervisor", f"مسؤول {cfg['branches'][0][0]}", PW["supervisor"])
    sup2 = staff(6, "branch_supervisor", f"مسؤول {cfg['branches'][1][0]}", PW["supervisor"])
    db.flush()
    db.add(models.BranchSupervisor(company_id=company.id, branch_id=branches[0].id, user_id=sup1.id))
    db.add(models.BranchSupervisor(company_id=company.id, branch_id=branches[1].id, user_id=sup2.id))

    # موظفون
    emps = []
    for i, (name, nat, job, sal, mode) in enumerate(cfg["employees"]):
        branch = branches[i % 2]
        e = models.Employee(company_id=company.id, civil_id=civ(p, 100 + i + 1), name=name,
                            nationality=nat, worker_type=("موظف" if mode == "none" else "عامل"),
                            job_title=job, basic_salary=sal, hire_date=d(-900 - i * 120),
                            status="active", license_id=license_.id, branch_id=branch.id,
                            shift_id=shift.id, attendance_mode=mode, annual_leave_balance=30)
        db.add(e)
        emps.append(e)
    db.flush()

    # حسابات خدمة ذاتية لأول موظفين (لتجربة الحضور)
    for e in emps[:2]:
        db.add(models.User(civil_id=e.civil_id, password_hash=hash_password(PW["employee"]),
                           full_name=e.name, role="employee", company_id=company.id,
                           employee_id=e.id, must_change_password=False))

    # إقامات (بعضها قرب الانتهاء)
    for i, e in enumerate(emps):
        db.add(models.Permit(company_id=company.id, employee_id=e.id, kind="residency",
                             number=f"RES-{p}{i:03d}", start_date=d(-360),
                             expiry_date=d([8, 25, 70, 200, -5, 120][i])))
    # سجلات حضور تجريبية لأول موظفين متتبَّعين
    _add_attendance(db, emps[0], emps[0].branch_id, 5, late_on=2)
    _add_attendance(db, emps[1], emps[1].branch_id, 4)
    # إجازة معتمدة لموظف ثالث (تظهر في مراجعة الحضور)
    today = date.today()
    ls = today.replace(day=min(10, 28))
    db.add(models.Leave(company_id=company.id, employee_id=emps[2].id, leave_type="annual",
                        start_date=ls, end_date=ls + timedelta(days=2), days=3, status="approved"))

    return {"company": company, "manager_civil": manager.civil_id, "emp_civil": emps[0].civil_id}


def run():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    init_db()
    db = SessionLocal()

    # تنظيف شامل لكل الجداول
    for model in (models.AuditLog, models.ConsumedToken, models.RequestApproval,
                  models.RequestDocument, models.Appointment, models.Request, models.RequestType,
                  models.Task, models.AttendanceRecord, models.Leave, models.Deduction,
                  models.Document, models.DocumentType, models.DocumentTemplate,
                  models.Permit, models.BranchSupervisor,
                  models.Shift, models.Branch, models.Transfer, models.UserPermission,
                  models.Employee, models.License, models.User, models.Company):
        db.execute(delete(model))
    db.commit()

    # الإدارة العليا (تختار الشركة) والمالك (يرى كل الشركات)
    db.add(models.User(civil_id="000000000000", password_hash=hash_password("admin123"),
                       full_name="مدير النظام العام", role="super_admin", must_change_password=False))
    db.add(models.User(civil_id="111111111111", password_hash=hash_password("owner123"),
                       full_name="صاحب الشركات", role="company_owner", must_change_password=False))

    infos = [build_company(db, cfg) for cfg in COMPANIES]

    # أنواع الطلبات (عامة) وأنواع المستندات
    for rt in DEFAULT_REQUEST_TYPES:
        db.add(models.RequestType(company_id=None, **rt))
    for code, name, has_exp in [("passport", "جواز السفر", True), ("civil_id", "البطاقة المدنية", True),
                                ("residency", "الإقامة", True), ("work_permit", "إذن العمل", True),
                                ("contract", "عقد العمل", False)]:
        db.add(models.DocumentType(code=code, name=name, has_expiry=has_exp,
                                   lead_days_json=[180, 90, 30]))

    # صيغ/نماذج جاهزة (عامة) قابلة للتعبئة التلقائية والطباعة
    for code, name, cat, body in DEFAULT_TEMPLATES:
        db.add(models.DocumentTemplate(company_id=None, code=code, name=name,
                                       category=cat, body_html=body))

    db.commit()
    db.close()

    line = "=" * 62
    print(line)
    print(" تمت تعبئة شركتين معزولتين بنجاح")
    print(line)
    print(" الإدارة العليا (تختار الشركة):  000000000000 / admin123")
    print(" صاحب الشركات (يرى الكل):        111111111111 / owner123")
    for idx, (cfg, info) in enumerate(zip(COMPANIES, infos), start=1):
        p = cfg["prefix"]
        print(line)
        print(f" الشركة {idx}: {cfg['name']}  (رقمها في النظام: {info['company'].id})")
        print(f"   المدير            : {civ(p,1)} / {PW['manager']}")
        print(f"   الشؤون القانونية  : {civ(p,2)} / {PW['hr']}")
        print(f"   مندوب 1 / مندوب 2 : {civ(p,3)} ، {civ(p,4)} / {PW['delegate']}")
        print(f"   مسؤول فرع 1 / 2   : {civ(p,5)} ، {civ(p,6)} / {PW['supervisor']}")
        print(f"   موظف (خدمة ذاتية) : {info['emp_civil']} / {PW['employee']}")
    print(line)


if __name__ == "__main__":
    run()
