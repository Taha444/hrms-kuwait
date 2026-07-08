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
from .notification_templates import DEFAULT_NOTIFICATION_TEMPLATES
from .workflow import DEFAULT_REQUEST_TYPES

PW = {"manager": "manager123", "hr": "hr12345", "delegate": "deleg123",
      "supervisor": "sup12345", "employee": "emp12345", "accountant": "account123"}

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


def _tpl(code: str, title: str, body: str) -> str:
    return (
        f"<h2>{title}</h2>"
        f"<p class='muted'>التاريخ: {{{{date_today}}}} — المرجع: {{{{ref_no}}}} — كود: {code}</p>"
        f"{body}"
        "<br><br><table style='width:100%;border:none'><tr>"
        "<td style='border:none;text-align:center'>توقيع الموظف<br>............................</td>"
        "<td style='border:none;text-align:center'>توقيع/ختم الشركة<br>............................</td>"
        "</tr></table>"
    )


# 42 قالب طباعة رسمي (PRN-001..042) — حزمة V1.3 (FIX-003)
DEFAULT_TEMPLATES = [
    # الشهادات والخطابات
    ("PRN-001", "شهادة راتب", "الشهادات والخطابات", _tpl("PRN-001", "شهادة راتب",
        "<p>تشهد <b>{{company_name}}</b> بأن السيد/ة <b>{{employee_name}}</b> — الرقم المدني "
        "{{civil_id}} — يعمل لدينا بوظيفة <b>{{job_title}}</b> منذ {{hire_date}}، وأن راتبه "
        "الأساسي {{basic_salary}}.</p>"
        "<p>وقد أُعطيت له هذه الشهادة بناءً على طلبه لتقديمها إلى <b>{{addressed_to}}</b>.</p>")),
    ("PRN-002", "شهادة لمن يهمه الأمر", "الشهادات والخطابات", _tpl("PRN-002", "شهادة لمن يهمه الأمر",
        "<p>نفيد بأن السيد/ة <b>{{employee_name}}</b> ({{nationality}}) — الرقم المدني {{civil_id}} "
        "— يعمل لدى <b>{{company_name}}</b> بوظيفة {{job_title}} منذ {{hire_date}} حتى تاريخه.</p>"
        "<p>وقد أُعطيت له هذه الشهادة للاستخدام في الغرض الموضح فقط دون تضمين تفاصيل حساسة.</p>")),
    ("PRN-003", "شهادة خبرة", "الشهادات والخطابات", _tpl("PRN-003", "شهادة خبرة",
        "<p>تشهد <b>{{company_name}}</b> بأن السيد/ة <b>{{employee_name}}</b> عمل لدينا بوظيفة "
        "{{job_title}} خلال الفترة من {{hire_date}} حتى {{date_today}}، وقد أدّى مهامه بكفاءة.</p>"
        "<p>صيغة محايدة لا تتضمن أسباب الإنهاء أو أي ملاحظات داخلية غير مصرَّح بها.</p>")),
    ("PRN-004", "خطاب بنك", "الشهادات والخطابات", _tpl("PRN-004", "خطاب بنك",
        "<p>إلى: <b>{{bank_name}}</b></p>"
        "<p>نفيد بأن السيد/ة <b>{{employee_name}}</b> — الرقم المدني {{civil_id}} — يعمل لدى "
        "<b>{{company_name}}</b> بوظيفة {{job_title}} وراتبه الأساسي {{basic_salary}}.</p>"
        "<p>الغرض: {{purpose}}.</p>")),
    ("PRN-005", "عرض عمل", "الشهادات والخطابات", _tpl("PRN-005", "عرض عمل",
        "<p>يسرّ <b>{{company_name}}</b> تقديم عرض عمل للسيد/ة <b>{{employee_name}}</b> بوظيفة "
        "{{job_title}} براتب أساسي {{basic_salary}}، على أن يكون تاريخ المباشرة {{start_date}}.</p>"
        "<p>هذا العرض غير ملزم إلا بعد توقيع الطرفين وعقد العمل الرسمي.</p>")),
    ("PRN-006", "ملخص عقد عمل", "الشهادات والخطابات", _tpl("PRN-006", "ملخص عقد عمل",
        "<p>ملخص عقد العمل بين <b>{{company_name}}</b> والموظف <b>{{employee_name}}</b>: الوظيفة "
        "{{job_title}}، نوع العقد {{contract_type}}، الراتب الأساسي {{basic_salary}}، تاريخ "
        "التعيين {{hire_date}}.</p>")),

    # قرارات وإجراءات تأديبية
    ("PRN-007", "قرار نقل", "قرارات وإجراءات تأديبية", _tpl("PRN-007", "قرار نقل",
        "<p>تقرر نقل الموظف <b>{{employee_name}}</b> من <b>{{from_branch}}</b> إلى "
        "<b>{{to_branch}}</b> اعتبارًا من {{effective_date}}، بعد استيفاء موافقات الجهتين.</p>")),
    ("PRN-008", "قرار ترقية", "قرارات وإجراءات تأديبية", _tpl("PRN-008", "قرار ترقية",
        "<p>تقرر ترقية الموظف <b>{{employee_name}}</b> إلى وظيفة <b>{{new_title}}</b> اعتبارًا من "
        "{{effective_date}}، مع تعديل الراتب الأساسي إلى {{new_salary}} إن وجد.</p>")),
    ("PRN-009", "قرار تعديل راتب", "قرارات وإجراءات تأديبية", _tpl("PRN-009", "قرار تعديل راتب",
        "<p>تقرر تعديل الراتب الأساسي للموظف <b>{{employee_name}}</b> من {{basic_salary}} إلى "
        "<b>{{new_salary}}</b> اعتبارًا من {{effective_date}}.</p>")),
    ("PRN-010", "إنذار موظف", "قرارات وإجراءات تأديبية", _tpl("PRN-010", "إنذار موظف",
        "<p>بناءً على الواقعة الموضحة، يوجَّه للموظف <b>{{employee_name}}</b> إنذار بخصوص: "
        "<b>{{violation}}</b> بتاريخ {{date_today}}.</p>"
        "<p>لكم الحق في الرد أو الاعتراض خلال المهلة النظامية.</p>")),
    ("PRN-011", "محضر تحقيق", "قرارات وإجراءات تأديبية", _tpl("PRN-011", "محضر تحقيق",
        "<p>محضر تحقيق بخصوص واقعة: <b>{{subject}}</b>، بحضور: {{attendees}}.</p>"
        "<p>ملخص الأقوال والنتيجة: {{summary}}.</p>")),
    ("PRN-012", "قرار خصم", "قرارات وإجراءات تأديبية", _tpl("PRN-012", "قرار خصم",
        "<p>تقرر خصم مبلغ <b>{{amount}}</b> من مستحقات الموظف <b>{{employee_name}}</b> للسبب "
        "الموضح: {{reason}}، مع تمكينه من الرد أو الاعتراض وفق الإجراءات المعتمدة.</p>")),
    ("PRN-013", "قرار مخالفة", "قرارات وإجراءات تأديبية", _tpl("PRN-013", "قرار مخالفة",
        "<p>تسجَّل على الموظف <b>{{employee_name}}</b> مخالفة وظيفية بتاريخ {{date_today}}: "
        "<b>{{violation}}</b>، مع حفظ حقه في الرد أو الاعتراض.</p>")),
    ("PRN-014", "إقرار استلام إنذار", "قرارات وإجراءات تأديبية", _tpl("PRN-014", "إقرار استلام إنذار",
        "<p>أقر أنا <b>{{employee_name}}</b> باستلام الإنذار الموضح بتاريخ {{date_today}}. "
        "استلام الإنذار لا يعني إقرارًا بصحة مضمونه ما لم أُصرّح بذلك كتابةً.</p>")),

    # سفر وإجازات
    ("PRN-015", "طلب إجازة معتمد", "سفر وإجازات", _tpl("PRN-015", "طلب إجازة معتمد",
        "<p>اعتُمد طلب إجازة الموظف <b>{{employee_name}}</b> من {{start_date}} إلى {{end_date}} "
        "(عدد الأيام: {{days}})، نوع الإجازة: {{leave_type}}.</p>")),
    ("PRN-016", "إفادة مالية للسفر", "سفر وإجازات", _tpl("PRN-016", "إفادة مالية للسفر",
        "<p>إفادة معلوماتية عن الوضع المالي للموظف <b>{{employee_name}}</b> بخصوص طلب رقم "
        "{{request_no}} — لا تُعد موافقة أو رفضًا نهائيًا.</p>")),
    ("PRN-017", "إفادة قانونية مستندية للسفر", "سفر وإجازات",
     _tpl("PRN-017", "إفادة قانونية مستندية للسفر",
        "<p>إفادة من الشؤون القانونية بخصوص اكتمال مستندات سفر الموظف <b>{{employee_name}}</b> "
        "المرتبطة بالطلب رقم {{request_no}}.</p>")),
    ("PRN-018", "إذن خروج سفر", "سفر وإجازات", _tpl("PRN-018", "إذن خروج سفر",
        "<p>صدر إذن خروج سفر للموظف <b>{{employee_name}}</b> — جواز رقم {{passport_number}} — "
        "بعد الاعتماد النهائي لطلب رقم {{request_no}}.</p>")),
    ("PRN-019", "تكليف مندوب", "سفر وإجازات", _tpl("PRN-019", "تكليف مندوب",
        "<p>يُكلَّف المندوب <b>{{delegate_name}}</b> بإجراء: <b>{{task}}</b> المرتبط بالطلب رقم "
        "{{request_no}}، ويقتصر دوره على التنفيذ ورفع الإثبات.</p>")),

    # الإقامة والمستندات الحكومية
    ("PRN-020", "إشعار نقص مستندات", "الإقامة والمستندات الحكومية",
     _tpl("PRN-020", "إشعار نقص مستندات",
        "<p>نحيط الموظف <b>{{employee_name}}</b> علمًا بوجود نقص في المستندات التالية: "
        "<b>{{missing_docs}}</b>، ويُرجى استكمالها خلال المهلة المحددة.</p>")),
    ("PRN-021", "مذكرة تجديد إقامة", "الإقامة والمستندات الحكومية",
     _tpl("PRN-021", "مذكرة تجديد إقامة",
        "<p>مذكرة متابعة تجديد إقامة الموظف <b>{{employee_name}}</b> رقم {{permit_number}}، "
        "تنتهي بتاريخ {{expiry_date}}.</p>")),
    ("PRN-022", "مذكرة تجديد إذن عمل", "الإقامة والمستندات الحكومية",
     _tpl("PRN-022", "مذكرة تجديد إذن عمل",
        "<p>مذكرة متابعة تجديد إذن عمل الموظف <b>{{employee_name}}</b>، ينتهي بتاريخ "
        "{{expiry_date}}.</p>")),
    ("PRN-023", "مذكرة تجديد بطاقة مدنية", "الإقامة والمستندات الحكومية",
     _tpl("PRN-023", "مذكرة تجديد بطاقة مدنية",
        "<p>مذكرة متابعة تجديد البطاقة المدنية للموظف <b>{{employee_name}}</b> — الرقم المدني "
        "{{civil_id}}.</p>")),
    ("PRN-024", "مذكرة تحديث جواز", "الإقامة والمستندات الحكومية",
     _tpl("PRN-024", "مذكرة تحديث جواز",
        "<p>مذكرة تحديث بيانات جواز سفر الموظف <b>{{employee_name}}</b> — جواز رقم "
        "{{passport_number}}، ينتهي بتاريخ {{expiry_date}}.</p>")),

    # إنهاء الخدمة
    ("PRN-025", "قبول استقالة", "إنهاء الخدمة", _tpl("PRN-025", "قبول استقالة",
        "<p>تقرر قبول استقالة الموظف <b>{{employee_name}}</b> اعتبارًا من {{last_working_day}}، "
        "وفق إجراءات إخلاء الطرف المعتمدة.</p>")),
    ("PRN-026", "إخلاء طرف", "إنهاء الخدمة", _tpl("PRN-026", "إخلاء طرف",
        "<p>تم استكمال إجراءات إخلاء طرف الموظف <b>{{employee_name}}</b>: تسليم العهد "
        "وتسوية الالتزامات المالية والمستندية بتاريخ {{date_today}}.</p>")),
    ("PRN-027", "تسوية نهاية خدمة مبدئية", "إنهاء الخدمة",
     _tpl("PRN-027", "تسوية نهاية خدمة مبدئية",
        "<p>احتساب مبدئي لمكافأة نهاية خدمة الموظف <b>{{employee_name}}</b>: المستحق "
        "التقديري {{eos_amount}} د.ك، حتى الاعتماد النهائي قانونيًا وماليًا.</p>")),
    ("PRN-028", "تسوية نهاية خدمة نهائية", "إنهاء الخدمة",
     _tpl("PRN-028", "تسوية نهاية خدمة نهائية",
        "<p>الاحتساب النهائي المعتمد لمكافأة نهاية خدمة الموظف <b>{{employee_name}}</b>: "
        "المبلغ المستحق {{eos_amount}} د.ك بتاريخ {{date_today}}.</p>")),

    # تقارير وكشوفات
    ("PRN-029", "بيان رصيد إجازات", "تقارير وكشوفات", _tpl("PRN-029", "بيان رصيد إجازات",
        "<p>رصيد إجازات الموظف <b>{{employee_name}}</b> حتى تاريخ {{date_today}}: "
        "<b>{{leave_balance}}</b> يومًا.</p>")),
    ("PRN-030", "كشف حضور", "تقارير وكشوفات", _tpl("PRN-030", "كشف حضور",
        "<p>كشف حضور الموظف <b>{{employee_name}}</b> عن الفترة من {{start_date}} إلى "
        "{{end_date}}.</p>")),
    ("PRN-031", "كشف تأخير وغياب", "تقارير وكشوفات", _tpl("PRN-031", "كشف تأخير وغياب",
        "<p>كشف حالات التأخير والغياب للموظف <b>{{employee_name}}</b> عن الفترة من "
        "{{start_date}} إلى {{end_date}}.</p>")),
    ("PRN-032", "كشف رواتب مبسط", "تقارير وكشوفات", _tpl("PRN-032", "كشف رواتب مبسط",
        "<p>كشف راتب مبسط للموظف <b>{{employee_name}}</b> عن فترة {{period}}: الأساسي "
        "{{basic_salary}}، الصافي {{net_salary}}.</p>")),
    ("PRN-033", "كشف خصومات", "تقارير وكشوفات", _tpl("PRN-033", "كشف خصومات",
        "<p>كشف الخصومات المسجَّلة على الموظف <b>{{employee_name}}</b> عن فترة {{period}}: "
        "إجمالي الخصم {{amount}}.</p>")),

    # عهد ومهام
    ("PRN-034", "إقرار استلام عهدة", "عهد ومهام", _tpl("PRN-034", "إقرار استلام عهدة",
        "<p>أقر أنا <b>{{employee_name}}</b> — الرقم المدني {{civil_id}} — بأنني استلمت من "
        "<b>{{company_name}}</b> العهدة التالية: <b>{{item}}</b> بتاريخ {{date_today}}، وأتعهد "
        "بالمحافظة عليها وإعادتها عند الطلب.</p>")),
    ("PRN-035", "إقرار تسليم عهدة", "عهد ومهام", _tpl("PRN-035", "إقرار تسليم عهدة",
        "<p>أقر أنا <b>{{employee_name}}</b> بأنني سلّمت العهدة: <b>{{item}}</b> إلى "
        "<b>{{company_name}}</b> بحالتها الموضحة بتاريخ {{date_today}}.</p>")),
    ("PRN-036", "تكليف مهمة عمل خارجية", "عهد ومهام", _tpl("PRN-036", "تكليف مهمة عمل خارجية",
        "<p>يُكلَّف الموظف <b>{{employee_name}}</b> بمهمة عمل خارجية: <b>{{task}}</b> خلال "
        "الفترة من {{start_date}} إلى {{end_date}}.</p>")),
    ("PRN-037", "قرار تغيير وردية", "عهد ومهام", _tpl("PRN-037", "قرار تغيير وردية",
        "<p>تقرر تغيير وردية/جدول عمل الموظف <b>{{employee_name}}</b> إلى <b>{{new_shift}}</b> "
        "اعتبارًا من {{effective_date}}.</p>")),
    ("PRN-038", "اعتماد عمل إضافي", "عهد ومهام", _tpl("PRN-038", "اعتماد عمل إضافي",
        "<p>اعتُمد العمل الإضافي للموظف <b>{{employee_name}}</b>: عدد الساعات {{ot_hours}} خلال "
        "فترة {{period}}، وفق سياسة الشركة.</p>")),

    # إدارية وتوثيق
    ("PRN-039", "إشعار تحديث بيانات", "إدارية وتوثيق", _tpl("PRN-039", "إشعار تحديث بيانات",
        "<p>تم تحديث بيانات الموظف <b>{{employee_name}}</b> الموضحة بتاريخ {{date_today}}. "
        "بيانات التواصل الرسمية لا تحتاج مسارًا طويلًا.</p>")),
    ("PRN-040", "سجل توقيع إلكتروني", "إدارية وتوثيق", _tpl("PRN-040", "سجل توقيع إلكتروني",
        "<p>سجل اعتماد/توقيع إلكتروني على المستند: <b>{{document_ref}}</b> — الموقِّع: "
        "{{signer_name}} — بتاريخ ووقت {{signed_at}}.</p>")),
    ("PRN-041", "طلب مراجعة قانونية", "إدارية وتوثيق", _tpl("PRN-041", "طلب مراجعة قانونية",
        "<p>يُطلب من الشؤون القانونية مراجعة: <b>{{subject}}</b> المتعلق بالموظف "
        "<b>{{employee_name}}</b> قبل اتخاذ القرار النهائي.</p>")),
    ("PRN-042", "ملخص ملف موظف للطباعة", "إدارية وتوثيق", _tpl("PRN-042", "ملخص ملف موظف للطباعة",
        "<p>ملخص ملف الموظف <b>{{employee_name}}</b> — الرقم المدني {{civil_id}} — الوظيفة "
        "{{job_title}} — تاريخ التعيين {{hire_date}} — الفرع {{branch_name}}.</p>")),
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
    accountant = staff(7, "accountant", f"محاسب {cfg['name']}", PW["accountant"])  # noqa: F841
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

    # مستندات الموظف (جواز/بطاقة مدنية/عقد) — FIX-011: بيانات ديمو ناقصة سابقًا
    passport_expiry = [30, 60, 400, 15, 200, 90]
    civil_id_expiry = [45, 500, 20, 300, 10, 150]
    for i, e in enumerate(emps):
        db.add(models.Document(company_id=company.id, entity_type="employee", entity_id=e.id,
                              document_type_code="passport", title=f"جواز سفر {e.name}",
                              file_path=None, mime="application/pdf", issue_date=d(-800),
                              expiry_date=d(passport_expiry[i % len(passport_expiry)]),
                              version=1, is_current=True))
        db.add(models.Document(company_id=company.id, entity_type="employee", entity_id=e.id,
                              document_type_code="civil_id", title=f"بطاقة مدنية {e.name}",
                              file_path=None, mime="application/pdf", issue_date=d(-700),
                              expiry_date=d(civil_id_expiry[i % len(civil_id_expiry)]),
                              version=1, is_current=True))
        db.add(models.Document(company_id=company.id, entity_type="employee", entity_id=e.id,
                              document_type_code="contract", title=f"عقد عمل {e.name}",
                              file_path=None, mime="application/pdf", issue_date=e.hire_date,
                              expiry_date=None, version=1, is_current=True))
    # الراتب الفعلي (صلاحية خاصة) لأول موظفَين — يفارق الراتب الرسمي لاختبار الإخفاء المالي
    if emps:
        emps[0].actual_salary = emps[0].basic_salary + 50
    if len(emps) > 1:
        emps[1].actual_salary = emps[1].basic_salary
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
                  models.NotificationPreference, models.NotificationTemplate,
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

    # قوالب الإشعارات (74 — FIX-004)
    for nt in DEFAULT_NOTIFICATION_TEMPLATES:
        db.add(models.NotificationTemplate(**nt))

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
