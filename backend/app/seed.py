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


def _tpl(code: str, title: str, body: str, notes: str = "") -> str:
    """يبني نص القالب مطابقًا لبنية حزمة V1.3 الرسمية: بيانات المستند (قسم 1)، العنوان،
    النص الذي يُطبع فعليًا (منقول حرفيًا من ملف المراجعة، قسم 2)، ملاحظات قانونية/تشغيلية
    (قسم 3)، وتوقيعات ثلاثية (قسم 4)."""
    notes_html = f"<p class='muted'><b>ملاحظات:</b> {notes}</p>" if notes else ""
    data_table = (
        "<table style='width:100%;margin-bottom:14px'>"
        "<tr><td>الشركة: {{company_name}}</td><td>الفرع: {{branch_name}}</td></tr>"
        "<tr><td>اسم الموظف: {{employee_name}}</td><td>الرقم الوظيفي: {{civil_id}}</td></tr>"
        "<tr><td>الوظيفة: {{job_title}}</td><td>الجهة: {{addressed_to}}</td></tr>"
        "</table>"
    )
    return (
        f"<h2>{title}</h2>"
        f"<p class='muted'>التاريخ: {{{{date_today}}}} — المرجع: {{{{ref_no}}}} — كود: {code}</p>"
        f"{data_table}"
        f"<p>{body}</p>"
        f"{notes_html}"
        "<br><br><table style='width:100%;border:none'><tr>"
        "<td style='border:none;text-align:center'>استلام/إفادة الموظف<br>............................</td>"
        "<td style='border:none;text-align:center'>الإدارة المختصة<br>............................</td>"
        "<td style='border:none;text-align:center'>صاحب الصلاحية<br>............................</td>"
        "</tr></table>"
    )


# 42 قالب طباعة رسمي (PRN-001..042) — نص حرفي منقول من حزمة V1.3 الرسمية (FIX-003 / دقة كاملة)
DEFAULT_TEMPLATES = [
    ("PRN-001", "شهادة راتب", "الشهادات", _tpl("PRN-001", "شهادة راتب", "تشهد الشركة بأن الموظف المذكور يعمل لديها، وأن بيانات الراتب المصرح بإظهارها صادرة من السجلات المعتمدة حتى تاريخ الإصدار. وقد أعطيت هذه الشهادة بناًء على طلبه دون مسؤولية على الشركة عن استخدامها خارج الغرض الصادر لأجله.", "صيغة محايدة، لا تظهر راتًبا فعلًيا غير مصرح.")),
    ("PRN-002", "شهادة لمن يهمه الأمر", "الشهادات", _tpl("PRN-002", "شهادة لمن يهمه الأمر", "تشهد الشركة بأن الموظف المذكور يعمل لديها بالمسمى والفرع الموضحين حتى تاريخ إصدار هذه الشهادة، وقد أعطيت له بناًء على طلبه لتقديمها إلى من يهمه الأمر.", "لا تتضمن جزاءات أو ملاحظات داخلية.")),
    ("PRN-003", "شهادة خبرة", "الشهادات", _tpl("PRN-003", "شهادة خبرة", "تشهد الشركة بأن الموظف عمل لديها خلال الفترة الموضحة وبالمسمى المبين، وقد اكتسب خبرة في نطاق المهام العامة للوظيفة، دون أن تتضمن هذه الشهادة أي أسباب إنهاء أو جزاءات داخلية.", "صيغة خبرة محايدة.")),
    ("PRN-004", "خطاب بنك", "خطابات", _tpl("PRN-004", "خطاب بنك", "بناًء على طلب الموظف، تصدر الشركة هذا الخطاب إلى البنك الموضح لتأكيد البيانات الوظيفية والمالية المصرح بإظهارها فقط، دون أي التزام على الشركة تجاه البنك إلا في حدود ما يصرح به الخطاب.", "يحتاج مراجعة مالية عند تضمين راتب.")),
    ("PRN-005", "عرض عمل", "خطابات", _tpl("PRN-005", "عرض عمل", "يسر الشركة تقديم عرض عمل مبدئي للمرشح وفق البيانات والشروط الموضحة، ولا يعتبر العرض عقًدا نهائًيا إلا بعد استكمال التوقيع والمستندات والإجراءات الداخلية.", "ليس عقًدا نهائًيا.")),
    ("PRN-006", "ملخص عقد عمل", "عقود", _tpl("PRN-006", "ملخص عقد عمل", "هذا ملخص بيانات عقد العمل المسجلة في النظام، ويستخدم للمراجعة الداخلية ولا يغني عن نسخة العقد الرسمية الموقعة بين الطرفين.", "للديمو والمراجعة الداخلية.")),
    ("PRN-007", "قرار نقل", "قرارات", _tpl("PRN-007", "قرار نقل", "تقرر نقل الموظف إلى الجهة الموضحة اعتباًرا من التاريخ المحدد، مع تحديث موقع العمل الفعلي أو الرسمي حسب نوع القرار ودون المساس بحقوقه الأخرى.", "يميز بين الرسمي والفعلي.")),
    ("PRN-008", "قرار ترقية", "قرارات", _tpl("PRN-008", "قرار ترقية", "تقرر ترقية الموظف إلى المسمى الموضح اعتباًرا من التاريخ المحدد، وذلك بعد مراجعة الأداء واحتياج العمل واعتماد صاحب الصلاحية.", "قد يحتاج مالية عند تعديل الراتب.")),
    ("PRN-009", "قرار تعديل راتب", "قرارات مالية", _tpl("PRN-009", "قرار تعديل راتب", "تقرر تعديل راتب الموظف وفق البيانات المعتمدة، على أن يطبق من التاريخ المحدد وبعد اعتماد الجهة المالية وصاحب الصلاحية.", "سجل تدقيق إلزامي.")),
    ("PRN-010", "إنذار موظف", "إجراءات تأديبية", _tpl("PRN-010", "إنذار موظف", "تقرر توجيه إنذار للموظف بشأن الواقعة الموضحة، مع بيان حقه في الرد أو الاعتراض خلال المدة المحددة وفق سياسة الشركة.", "فصل الاستلام عن الإقرار بالمضمون.")),
    ("PRN-011", "محضر تحقيق", "إجراءات تأديبية", _tpl("PRN-011", "محضر تحقيق", "تم تحرير هذا المحضر لإثبات أقوال الأطراف والمستندات المتعلقة بالواقعة محل التحقيق، ويعد مستنًدا سرًيا لا يطلع عليه إلا المخولون.", "سري.")),
    ("PRN-012", "قرار خصم", "قرارات مالية", _tpl("PRN-012", "قرار خصم", "تقرر تطبيق خصم مالي على الموظف وفق السبب والمستند الموضحين، ولا يطبق الخصم إلا بعد الاعتماد ومراعاة الضوابط المالية وحق الموظف في الاعتراض.", "لا خصم بلا مستند.")),
    ("PRN-013", "قرار مخالفة", "إجراءات تأديبية", _tpl("PRN-013", "قرار مخالفة", "تقرر تسجيل مخالفة وظيفية على الموظف بشأن الواقعة الموضحة، مع حفظ حقه في الرد أو الاعتراض وفق السياسة المعتمدة.", "قرار تأديبي.")),
    ("PRN-014", "إقرار استلام إنذار", "إقرارات", _tpl("PRN-014", "إقرار استلام إنذار", "أقر أنا الموظف باستلام الإنذار المشار إليه، ويعد هذا الإقرار إثباًتا للاستلام فقط ولا يعني بالضرورة الإقرار بصحة ما ورد فيه ما لم أصرح بذلك.", "صياغة تحفظ حق الرد.")),
    ("PRN-015", "طلب إجازة معتمد", "إجازات", _tpl("PRN-015", "طلب إجازة معتمد", "تم اعتماد إجازة الموظف للفترة الموضحة بعد استكمال جميع المراجعات، وأصبحت النسخة جاهزة للطباعة والحفظ في ملف الموظف الورقي والإلكتروني.", "إشعار طباعة بعد الاعتماد.")),
    ("PRN-016", "إفادة مالية للسفر", "إفادات", _tpl("PRN-016", "إفادة مالية للسفر", "تفيد المالية بوجود أو عدم وجود التزامات مالية مؤثرة على طلب السفر، وتعد هذه الإفادة معلوماتية لصاحب القرار ولا تعتبر موافقة أو رفًضا نهائًيا.", "V أهم إضافة 3.1 .")),
    ("PRN-017", "إفادة قانونية مستندية للسفر", "إفادات", _tpl("PRN-017", "إفادة قانونية مستندية للسفر", "تفيد شؤون الموظفين / الشؤون القانونية بحالة الجواز والإقامة والبطاقة المدنية وأي معاملات مفتوحة قد تؤثر على السفر.", "فحص سفر.")),
    ("PRN-018", "إذن خروج سفر", "إذن سفر", _tpl("PRN-018", "إذن خروج سفر", "يصدر هذا الإذن فقط إذا كانت الإجازة معتمدة ومرتبطة بالسفر خارج الكويت، ويقتصر دور المندوب على التنفيذ ورفع الإثبات.", "لا يستخدم لإذن أثناء الدوام.")),
    ("PRN-019", "تكليف مندوب", "تكليف", _tpl("PRN-019", "تكليف مندوب", "يكلف المندوب بتنفيذ المعاملة الموضحة ورفع إثبات الإنجاز، دون أن يملك صلاحية اعتماد أصل الطلب أو تغييره.", "تنفيذ فقط.")),
    ("PRN-020", "إشعار نقص مستندات", "إخطارات", _tpl("PRN-020", "إشعار نقص مستندات", "نحيط الموظف أو المسؤول المختص بوجود نقص في المستندات الموضحة، ويرجى الاستكمال خلال المهلة المحددة لتجنب تعطيل المعاملة.", "إخطار واضح.")),
    ("PRN-021", "مذكرة تجديد إقامة", "معاملات", _tpl("PRN-021", "مذكرة تجديد إقامة", "تعد هذه المذكرة لبدء أو متابعة تجديد إقامة الموظف بعد مراجعة المستندات وتحديد نوع التجديد وحالة الاعتماد.", "مبكر / عادي.")),
    ("PRN-022", "مذكرة تجديد إذن عمل", "معاملات", _tpl("PRN-022", "مذكرة تجديد إذن عمل", "تعد هذه المذكرة لمتابعة تجديد إذن العمل أو الترخيص المرتبط بالموظف، مع تحديد المرفقات والجهة المنفذة.", "معاملة حكومية.")),
    ("PRN-023", "مذكرة تجديد بطاقة مدنية", "معاملات", _tpl("PRN-023", "مذكرة تجديد بطاقة مدنية", "تعد هذه المذكرة لمتابعة تحديث أو تجديد البطاقة المدنية وفق المستندات والمواعيد المسجلة.", "مستند رسمي.")),
    ("PRN-024", "مذكرة تحديث جواز", "معاملات", _tpl("PRN-024", "مذكرة تحديث جواز", "تستخدم هذه المذكرة لتحديث بيانات جواز السفر في ملف الموظف وتأثيره على معاملات الإقامة والسفر.", "يحتاج تحقق.")),
    ("PRN-025", "قبول استقالة", "إنهاء خدمة", _tpl("PRN-025", "قبول استقالة", "تقرر قبول استقالة الموظف وتحديد آخر يوم عمل، مع بدء إجراءات إخلاء الطرف وتسوية المستحقات وفق السياسة المعتمدة.", "لا يغلق الملف مباشرة.")),
    ("PRN-026", "إخلاء طرف", "إنهاء خدمة", _tpl("PRN-026", "إخلاء طرف", "يشهد هذا النموذج بإتمام أو متابعة بنود إخلاء الطرف وتسليم العهد والمستندات وتسوية الالتزامات قبل إغلاق ملف الموظف.", "عهد ومالية.")),
    ("PRN-027", "تسوية نهاية خدمة مبدئية", "تسويات", _tpl("PRN-027", "تسوية نهاية خدمة مبدئية", "تعد هذه التسوية مبدئية لأغراض المراجعة ولا تصبح نهائية إلا بعد اعتماد الشؤون القانونية والمالية وصاحب الصلاحية.", "مبدئية.")),
    ("PRN-028", "تسوية نهاية خدمة نهائية", "تسويات", _tpl("PRN-028", "تسوية نهاية خدمة نهائية", "تعتمد هذه التسوية النهائية بعد استكمال المراجعة القانونية والمالية والتوقيع الإلكتروني، وتحدد صافي المستحقات والالتزامات.", "نهائية بالتوقيع.")),
    ("PRN-029", "بيان رصيد إجازات", "تقارير", _tpl("PRN-029", "بيان رصيد إجازات", "يبين هذا الكشف رصيد الإجازات السنوي والمستهلك والمعلق والمتاح حتى تاريخ الإصدار وفق سجلات النظام.", "للمراجعة والطباعة.")),
    ("PRN-030", "كشف حضور", "تقارير", _tpl("PRN-030", "كشف حضور", "يبين هذا الكشف سجلات الحضور والانصراف خلال الفترة المحددة ومصدر البيانات وحالة المراجعة.", "لا يساوي جزاء تلقائي.")),
    ("PRN-031", "كشف تأخير وغياب", "تقارير", _tpl("PRN-031", "كشف تأخير وغياب", "يبين هذا الكشف حالات التأخير والغياب المسجلة خلال الفترة، ويستخدم للمراجعة قبل أي إجراء إداري.", "مراجعة قبل الجزاء.")),
    ("PRN-032", "كشف رواتب مبسط", "تقارير مالية", _tpl("PRN-032", "كشف رواتب مبسط", "يعرض هذا الكشف ملخص الرواتب للفترة المحددة للمخولين فقط، ولا يجوز تداوله خارج نطاق الصلاحية.", "سري.")),
    ("PRN-033", "كشف خصومات", "تقارير مالية", _tpl("PRN-033", "كشف خصومات", "يبين الخصومات المعتمدة وأسبابها وتواريخ تطبيقها، مع الالتزام بسجل التصدير والصلاحيات المالية.", "حساس.")),
    ("PRN-034", "إقرار استلام عهدة", "عهد", _tpl("PRN-034", "إقرار استلام عهدة", "أقر أنا الموظف باستلام العهدة الموضحة بحالتها وقيمتها التقريبية، وأتعهد بالمحافظة عليها وإعادتها عند الطلب أو انتهاء العلاقة.", "إقرار عهدة.")),
    ("PRN-035", "إقرار تسليم عهدة", "عهد", _tpl("PRN-035", "إقرار تسليم عهدة", "أقر باستلام العهدة المرتجعة من الموظف وفحص حالتها، مع تسجيل أي ملاحظات أو تلفيات وفق السياسة المعتمدة.", "إخلاء طرف.")),
    ("PRN-036", "تكليف مهمة عمل خارجية", "تكليف", _tpl("PRN-036", "تكليف مهمة عمل خارجية", "يكلف الموظف بتنفيذ مهمة خارج مقر العمل ضمن المدة والجهة الموضحة، مع تسليم تقرير أو إثبات الإنجاز.", "مصروفات عند الحاجة.")),
    ("PRN-037", "قرار تغيير وردية", "قرارات تشغيلية", _tpl("PRN-037", "قرار تغيير وردية", "تقرر تعديل وردية الموظف للفترة المحددة بناًء على احتياج العمل، مع إخطار الموظف وتحديث جدول الحضور.", "تشغيلي.")),
    ("PRN-038", "اعتماد عمل إضافي", "اعتمادات", _tpl("PRN-038", "اعتماد عمل إضافي", "تم اعتماد ساعات العمل الإضافي الموضحة بعد مراجعة الحاجة الفعلية وسجل الحضور وصلاحية الاعتماد.", "قبل الصرف.")),
    ("PRN-039", "إشعار تحديث بيانات", "إخطارات", _tpl("PRN-039", "إشعار تحديث بيانات", "نحيطكم علًما بأنه تم تحديث البيانات الموضحة في ملف الموظف بناًء على طلب أو مستند معتمد.", "يظهر غير الحساس فقط.")),
    ("PRN-040", "سجل توقيع إلكتروني", "سجلات", _tpl("PRN-040", "سجل توقيع إلكتروني", "يثبت هذا السجل توقيع أو اعتماد المستند إلكترونًيا، مع بيان هوية الموّقع ووقت العملية ومعرف التوقيع.", "Audit .")),
    ("PRN-041", "طلب مراجعة قانونية", "طلبات داخلية", _tpl("PRN-041", "طلب مراجعة قانونية", "يرجى من الشؤون القانونية مراجعة النص أو الإجراء الموضح وإبداء الرأي قبل اعتماده أو تطبيقه.", "مراجعة داخلية.")),
    ("PRN-042", "ملخص ملف موظف للطباعة", "ملف موظف", _tpl("PRN-042", "ملخص ملف موظف للطباعة", "يعرض هذا الملخص أهم بيانات ملف الموظف والمستندات والحالة الوظيفية وفق الصلاحيات المسموح بها لغرض المراجعة أو الأرشفة.", "حسب الصلاحية.")),
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
