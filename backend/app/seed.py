# -*- coding: utf-8 -*-
"""تعبئة بيانات تجريبية: شركتان مستقلتان معزولتان تمامًا.

لكل شركة: مدير + موظف شؤون (قانونية) + مندوبان + فرعان (محلات) ومسؤول لكل فرع
+ ستة موظفين، مع إقامات وحضور وإجازات تجريبية. الإدارة العليا والمالك يختاران
الشركة من شاشة الاختيار، والعزل يمنع أي تداخل بين بيانات الشركتين.

التشغيل:  python -m app.seed
"""
import html
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


def _tpl(code: str, title_ar: str, title_en: str, body_ar: str, body_en: str,
        details: list[tuple[str, str]], signatures: list[tuple[str, str]],
        has_ack: bool = False) -> str:
    """يبني محتوى الصيغة ثنائي اللغة (HRMS-PR-001..042) وفق تصميم حزمة القوالب المعتمدة:
    نص المستند (عربي/إنجليزي)، شبكة تفاصيل الحقول (تُملأ يدوًيا على الورق كما في التصميم
    الأصلي)، إقرار اختياري، وصف توقيعات بعدد الأدوار المحددة لكل نموذج. ترويسة الشركة/التاريخ/
    المرجع وشبكة بيانات الموظف مشتركة، تُضاف من الغلاف الموحّد في routers/templates.py."""
    details_rows = "".join(
        f"<tr><td dir='rtl'>{html.escape(ar)}</td><td class='en' dir='ltr'>{html.escape(en)}</td></tr>"
        for ar, en in details
    )
    ack_html = (
        "<p class='muted'><b>الإقرار / Acknowledgment:</b> "
        "أقر بصحة البيانات الواردة أعلاه والتزامي بما ورد فيها. / "
        "I acknowledge the accuracy of the information above and my commitment to it.</p>"
    ) if has_ack else ""
    sig_cells = "".join(
        f"<td>{html.escape(en)}<br dir='rtl'>{html.escape(ar)}<br>....................<br>"
        "<span class='muted'>التوقيع والتاريخ / Signature &amp; Date</span></td>"
        for en, ar in signatures
    )
    return (
        f"<div class='doc-text'><p dir='rtl'>{html.escape(body_ar)}</p>"
        f"<p class='en' dir='ltr'>{html.escape(body_en)}</p></div>"
        f"<table class='details'>{details_rows}</table>"
        f"{ack_html}"
        f"<table class='sig-row'><tr>{sig_cells}</tr></table>"
    )


# 42 قالب طباعة رسمي ثنائي اللغة (HRMS-PR-001..042) — تصميم القوالب المعتمد.
# القوالب تستخدم {{placeholder}} syntax يعالجه محرك التعبئة في `routers/templates.py`:
# المفاتيح المعروفة (employee_name/company_name/civil_id/job_title/hire_date/basic_salary/...)
# تُملأ تلقائيًا من ملف الموظف، وأي مفتاح آخر يظهر في نموذج التعبئة لإدخاله يدويًا.
# مصدر النصوص: V1.4 Engineer Spec (Templates & Wording, ص 26-38).
DEFAULT_TEMPLATES = [
    ("HRMS-PR-001", "شهادة راتب", "Salary Certificate", "الشهادات والخطابات",
     _tpl("HRMS-PR-001", "شهادة راتب", "Salary Certificate",
          "تشهد شركة {{company_name}} بأن السيد/السيدة {{employee_name}}، حامل الرقم المدني {{civil_id}}، يعمل لديها بوظيفة {{job_title}} منذ تاريخ {{hire_date}}، ويتقاضى راتبًا أساسيًا قدره {{basic_salary}} د.ك، وبدلات {{allowances_total}} د.ك، بإجمالي شهري {{gross_salary}} د.ك. صدرت هذه الشهادة بناءً على طلبه لتقديمها إلى {{target_entity}} دون أدنى مسؤولية على الشركة تجاه الغير.",
          "{{company_name}} certifies that Mr./Ms. {{employee_name}}, Civil ID {{civil_id}}, has been employed as {{job_title}} since {{hire_date}} and receives a basic salary of KWD {{basic_salary}}, allowances of KWD {{allowances_total}}, totaling KWD {{gross_salary}} monthly. This certificate is issued upon request for submission to {{target_entity}} without liability to third parties.",
          [("[____] /KWD البدلات [____] /KWD الراتب الأساسي د.ك د.ك", "Basic Salary Allowances"), ("[Bank/Embassy/Other] الجهة الموجه إليها [____] /KWD الإجمالي د.ك", "Total Salary Addressed To")],
          [("Prepared by HR", "إعداد الموارد البشرية"), ("Manager Review", "مراجعة المدير"), ("Authorized Signatory", "المخول بالتوقيع")], has_ack=False)),
    ("HRMS-PR-002", "شهادة لمن يهمه الأمر", "To Whom It May Concern Certificate", "الشهادات والخطابات",
     _tpl("HRMS-PR-002", "شهادة لمن يهمه الأمر", "To Whom It May Concern Certificate",
          "إلى من يهمه الأمر: تشهد شركة {{company_name}} بأن السيد/السيدة {{employee_name}} يعمل لديها بوظيفة {{job_title}} منذ {{hire_date}} وما زال على رأس عمله حتى تاريخ إصدار هذا الخطاب. صدرت هذه الإفادة بناءً على طلبه لتقديمها إلى {{target_entity}} لغرض {{purpose}}.",
          "To whom it may concern: {{company_name}} confirms that Mr./Ms. {{employee_name}} is employed as {{job_title}} since {{hire_date}} and remains actively employed as of the issue date. Issued upon request for submission to {{target_entity}} for the purpose of {{purpose}}.",
          [("[Fixed/Unlimited] نوع العقد [DD/MM/YYYY] تاريخ التعيين", "Joining Date Contract Type"), ("[ ] الغرض [Active] حالة الموظف", "Employment Status Purpose")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-003", "شهادة خبرة", "Experience Certificate", "الشهادات والخطابات",
     _tpl("HRMS-PR-003", "شهادة خبرة", "Experience Certificate",
          "تشهد شركة {{company_name}} بأن السيد/السيدة {{employee_name}} قد عمل لديها خلال الفترة من {{service_start}} إلى {{service_end}} بوظيفة {{job_title}}، وأدى المهام الموكلة إليه وفق سجلات الشركة. صدرت هذه الشهادة بناءً على طلبه.",
          "{{company_name}} certifies that Mr./Ms. {{employee_name}} worked from {{service_start}} to {{service_end}} as {{job_title}} and performed the assigned duties according to company records. Issued upon request.",
          [("[ ] القسم الأخير [From] [To] فترة الخدمة", "Service Period Last Department"), ("[Optional] التقييم العام [ ] سبب انتهاء الخدمة", "Reason for Leaving General Rating")],
          [("Prepared by HR", "إعداد الموارد البشرية"), ("Legal Review", "مراجعة الشؤون القانونية"), ("Authorized Signatory", "المخول بالتوقيع")], has_ack=False)),
    ("HRMS-PR-004", "شهادة حالة وظيفية", "Employment Status Certificate", "الشهادات والخطابات",
     _tpl("HRMS-PR-004", "شهادة حالة وظيفية", "Employment Status Certificate",
          "تفيد شركة {{company_name}} بأن بيانات الحالة الوظيفية للموظف/ة {{employee_name}} (رقم مدني {{civil_id}}) كما هي مبينة في هذا المستند حتى تاريخ إصداره، وتم استخراجها مباشرة من نظام الموارد البشرية.",
          "{{company_name}} confirms that the employment status of {{employee_name}} (Civil ID {{civil_id}}) shown in this document is accurate as of the issue date and has been extracted from the HRMS.",
          [("", "Active/Leave/Suspended/["), ("[DD/MM/YYYY] تاريخ بداية الحالة الحالة", "Status ]Ended Status Start Date"), ("[ ] المسؤول المباشر [Fulltime/Parttime] الدوام", "Work Schedule Line Manager")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-005", "خطاب عدم ممانعة", "No Objection Certificate", "الشهادات والخطابات",
     _tpl("HRMS-PR-005", "خطاب عدم ممانعة", "No Objection Certificate",
          "تشهد شركة {{company_name}} بأنها لا تمانع في {{purpose}} للموظف/ة {{employee_name}}، بشرط عدم تعارضه مع التزاماته الوظيفية وسياسات الشركة، ودون ترتيب أي التزام مالي أو قانوني إضافي على الشركة ما لم يذكر خلاف ذلك صراحة.",
          "{{company_name}} has no objection to {{purpose}} for {{employee_name}}, provided it does not conflict with employment obligations or company policy and creates no additional financial or legal liability unless expressly stated.",
          [("[From] [To] الفترة [ ] الغرض", "Purpose Period"), ("[ ] الجهة المستفيدة [ ] الشروط", "Conditions Beneficiary Entity")],
          [("Prepared By", "إعداد"), ("Legal Review", "مراجعة قانونية"), ("Manager Approval", "اعتماد المدير")], has_ack=False)),
    ("HRMS-PR-006", "بيان بيانات موظف", "Employee Data Statement", "الشهادات والخطابات",
     _tpl("HRMS-PR-006", "بيان بيانات موظف", "Employee Data Statement",
          "بيان بيانات الموظف/ة {{employee_name}} (رقم مدني {{civil_id}}، وظيفة {{job_title}}، تاريخ التعيين {{hire_date}}، نوع العقد {{contract_type}}) مستخرج من نظام الموارد البشرية ويعرض البيانات المسجلة وقت الإصدار. أي تعديل لاحق يخضع لسجل التدقيق والصلاحيات المعتمدة.",
          "Employee data statement for {{employee_name}} (Civil ID {{civil_id}}, Job {{job_title}}, Hire Date {{hire_date}}, Contract {{contract_type}}) generated from the HRMS at issue time. Subsequent changes are subject to audit logs and approved permissions.",
          [("[ ] نوع العقد [DD/MM/YYYY] تاريخ التعيين", "Joining Date Contract Type"), ("[____] /KWD الراتب الفعلي [____] /KWD الراتب الرسمي د.ك د.ك", "Official Salary Actual Salary"), ("[ ] مكان العمل الفعلي [ ] مكان العمل الرسمي", "Official Work Location Actual Work Location"), ("[DD/MM/YYYY] انتهاء الإقامة [ ] رقم الإقامة", ". Residency No Residency Expiry")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-007", "شهادة مدة خدمة", "Length of Service Certificate", "الشهادات والخطابات",
     _tpl("HRMS-PR-007", "شهادة مدة خدمة", "Length of Service Certificate",
          "تشهد شركة {{company_name}} بأن مدة خدمة الموظف/ة {{employee_name}} المحتسبة وفق سجلات الشركة تمتد من {{hire_date}} حتى {{as_of_date}}، بإجمالي {{service_duration}} من الخدمة الفعلية.",
          "{{company_name}} certifies that {{employee_name}} has completed service from {{hire_date}} to {{as_of_date}}, totaling {{service_duration}} of actual service according to company records.",
          [("[DD/MM/YYYY] تاريخ االحتساب [DD/MM/YYYY] تاريخ بداية الخدمة", "Service Start Calculation Date"), ("[None/Details] فترات االنقطاع [Y/M/D] مدة الخدمة", "Service Length Excluded Periods")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-008", "خطاب تحويل راتب للبنك", "Bank Salary Transfer Letter", "الشهادات والخطابات",
     _tpl("HRMS-PR-008", "خطاب تحويل راتب للبنك", "Bank Salary Transfer Letter",
          "السادة {{bank_name}} المحترمين، نفيدكم بأن الموظف/ة {{employee_name}} يعمل لدى شركة {{company_name}} بوظيفة {{job_title}} منذ {{hire_date}} وبإجمالي راتب شهري {{gross_salary}} د.ك، وقد تقرر تحويل راتبه الشهري إلى الحساب رقم {{iban}} اعتبارًا من راتب شهر {{effective_month}}، وذلك دون التزام مالي إضافي على الشركة تجاه البنك.",
          "Dear {{bank_name}}, we confirm that {{employee_name}} is employed by {{company_name}} as {{job_title}} since {{hire_date}} with a total monthly salary of KWD {{gross_salary}}. The monthly salary shall be transferred to account {{iban}} effective from payroll month {{effective_month}}, without additional liability on the company toward the bank.",
          [("[ ] اسم البنك", "IBAN/"), ("[ ] رقم الحساب", "Bank Name Account / IBAN"), ("[DD/MM/YYYY] تاريخ البدء [____] /KWD راتب التحويل د.ك", "Transfer Salary Effective Date")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-009", "إفادة استمرارية راتب", "Salary Continuity Confirmation", "الشهادات والخطابات",
     _tpl("HRMS-PR-009", "إفادة استمرارية راتب", "Salary Continuity Confirmation",
          "تفيد شركة {{company_name}} بأن الموظف/ة {{employee_name}} ما زال على رأس عمله، وأن راتبه يصرف وفق دورة الرواتب المعتمدة بالشركة، مع خضوع أي تغيير لاحق للقرارات والسياسات الداخلية.",
          "{{company_name}} confirms that {{employee_name}} remains actively employed and receives salary according to the company payroll cycle. Any future change is subject to internal decisions and policies.",
          [("[Bank/Cash] طريقة الصرف [Monthly] دورة الصرف", "Payroll Cycle Payment Method"), ("[Active] الحالة [MM/YYYY] آخر راتب مصروف", "Last Payroll Month Status")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-010", "خطاب موجه لجهة رسمية", "Official Entity Letter", "الشهادات والخطابات",
     _tpl("HRMS-PR-010", "خطاب موجه لجهة رسمية", "Official Entity Letter",
          "السادة {{target_entity}} المحترمين، بالإشارة إلى طلبكم بشأن {{subject}}، نفيدكم بأن بيانات الموظف/ة {{employee_name}} (رقم مدني {{civil_id}}، وظيفة {{job_title}}) صحيحة وفق سجلات شركة {{company_name}} حتى تاريخ إصدار هذا الخطاب. وتفضلوا بقبول فائق الاحترام.",
          "Dear {{target_entity}}, with reference to your request regarding {{subject}}, we confirm that the information of {{employee_name}} (Civil ID {{civil_id}}, Job {{job_title}}) is accurate per {{company_name}} records as of the issue date. Yours faithfully.",
          [("[ ] الموضوع [ ] الجهة", "Entity Subject"), ("[ ] المرفقات [ ] رقم المرجع الخارجي", "External Reference Attachments")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-011", "خطاب عرض وظيفي", "Employment Offer Letter", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-011", "خطاب عرض وظيفي", "Employment Offer Letter",
          "يسر شركة {{company_name}} أن تقدم للسيد/السيدة {{candidate_name}} عرضًا للعمل بوظيفة {{job_title}} في {{location}} اعتبارًا من {{start_date}}، براتب أساسي {{basic_salary}} د.ك وبدلات {{allowances}} د.ك، وفق الشروط الموضحة أدناه. يصبح العرض نافذًا بعد توقيع الطرفين واستكمال المستندات والموافقات المطلوبة.",
          "{{company_name}} is pleased to offer Mr./Ms. {{candidate_name}} employment as {{job_title}} at {{location}} effective {{start_date}}, with a basic salary of KWD {{basic_salary}} and allowances of KWD {{allowances}}, subject to the terms below. The offer becomes effective upon signature by both parties and completion of required documents and approvals.",
          [("[____] /KWD إجمالي الراتب [____] /KWD الراتب الأساسي د.ك د.ك", "Basic Salary Total Package"), ("[DD/MM/YYYY] تاريخ المباشرة [ ] فترة التجربة", "Probation Start Date"), ("[DD/MM/YYYY] مدة صلاحية العرض [ ] ساعات العمل", "Working Hours Offer Validity")],
          [("Prepared by HR", "إعداد الموارد البشرية"), ("Manager Approval", "اعتماد المدير"), ("Candidate Acceptance", "قبول المرشح")], has_ack=True)),
    ("HRMS-PR-012", "إشعار تجديد عقد", "Contract Renewal Notice", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-012", "إشعار تجديد عقد", "Contract Renewal Notice",
          "نحيط الموظف/ة {{employee_name}} علمًا بأن الشركة ترغب في تجديد عقد العمل اعتبارًا من {{start_date}} ولمدة {{duration}}، وفق الشروط والتعديلات الموضحة أدناه. يرجى إبداء الموافقة أو الملاحظات خلال {{response_days}} أيام عمل.",
          "{{employee_name}} is notified that the company intends to renew the employment contract effective {{start_date}} for {{duration}}, subject to the terms and amendments below. Please confirm acceptance or comments within {{response_days}} working days.",
          [("[____] /KWD الراتب الجديد [ ] مدة التجديد د.ك ........................", "Renewal Period New Salary"), ("[ ] مكان العمل [ ] المسمى الوظيفي", "Job Title Work Location"), ("[ ] مالحظات [DD/MM/YYYY] آخر موعد للرد", "Response Deadline Notes")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-013", "إشعار عدم تجديد عقد", "Contract Non-Renewal Notice", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-013", "إشعار عدم تجديد عقد", "Contract Non-Renewal Notice",
          "يُخطر الموظف/ة {{employee_name}} بأن عقد العمل الحالي لن يتم تجديده بعد تاريخ انتهائه في {{expiry_date}}. يستمر الموظف في أداء واجباته وتسليم العهد والمستندات حتى آخر يوم عمل، مع استكمال إجراءات التسوية وإخلاء الطرف.",
          "{{employee_name}} is notified that the current employment contract will not be renewed after its expiry on {{expiry_date}}. Duties, handover, final settlement, and clearance procedures must be completed through the last working day.",
          [("[DD/MM/YYYY] آخر يوم عمل [DD/MM/YYYY] تاريخ انتهاء العقد", "Contract Expiry Last Working Day"), ("[ ] إجراءات التسليم [ ] فترة الإشعار", "Notice Period Handover Requirements")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-014", "قبول استقالة", "Resignation Acceptance", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-014", "قبول استقالة", "Resignation Acceptance",
          "بالإشارة إلى الاستقالة المقدمة من الموظف/ة {{employee_name}} بتاريخ {{resignation_date}}، تقرر قبولها على أن يكون آخر يوم عمل هو {{last_working_day}} بعد تطبيق فترة الإخطار {{notice_period}}. يبدأ فورًا مسار إخلاء الطرف وتسوية المستحقات وفق الإجراءات المعتمدة.",
          "With reference to the resignation submitted by {{employee_name}} on {{resignation_date}}, the resignation is accepted and the last working day shall be {{last_working_day}} after applying the notice period {{notice_period}}. Clearance and final settlement procedures begin immediately.",
          [("[DD/MM/YYYY] آخر يوم عمل [DD/MM/YYYY] تاريخ تقديم االستقالة", "Resignation Date Last Working Day"), ("[Pending/Completed] حالة التسوية [ ] فترة الإشعار", "Notice Period Settlement Status")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-015", "قرار إنهاء خدمة", "Employment Termination Decision", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-015", "قرار إنهاء خدمة", "Employment Termination Decision",
          "استنادًا إلى الصلاحيات المعتمدة ونتيجة {{termination_reason}} (مرجع {{reference}})، تقرر إنهاء خدمة الموظف/ة {{employee_name}} اعتبارًا من {{effective_date}}. تستكمل إجراءات التسليم والتسوية النهائية وإخلاء الطرف، مع حفظ حق الموظف في التظلم وفق سياسة الشركة.",
          "Based on approved authority and {{termination_reason}} (ref {{reference}}), the employment of {{employee_name}} is terminated effective {{effective_date}}. Handover, final settlement, and clearance shall be completed while preserving the employee's right to appeal under company policy.",
          [("", "Decision/Investigation/["), ("المرجع [ ] سبب الإنهاء", "Reason Reference ]Contract"), ("[DD/MM/YYYY] حق التظلم حتى [DD/MM/YYYY] تاريخ النفاذ", "Effective Date Appeal Deadline")],
          [("Prepared by HR", "إعداد الموارد البشرية"), ("Legal Review", "مراجعة الشؤون القانونية"), ("Authorized Approval", "اعتماد صاحب الصلاحية")], has_ack=True)),
    ("HRMS-PR-016", "قرار نقل موظف", "Employee Transfer Decision", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-016", "قرار نقل موظف", "Employee Transfer Decision",
          "تقرر نقل الموظف/ة {{employee_name}} من {{old_location}} إلى {{new_location}} بصفة {{transfer_type}} اعتبارًا من {{effective_date}}. يتم تحديث المسؤول المباشر ومكان العمل الفعلي والصلاحيات والعهد المرتبطة بالوظيفة الجديدة، ويظل باقي شروط العمل دون تغيير ما لم يذكر خلاف ذلك.",
          "{{employee_name}} is transferred from {{old_location}} to {{new_location}} as {{transfer_type}} effective {{effective_date}}. Reporting line, actual work location, permissions, and assigned assets shall be updated accordingly; other terms remain unchanged unless stated otherwise.",
          [("[Department/Branch] إلى [Department/Branch] من", "From To"), ("[DD/MM/YYYY] تاريخ النفاذ [ ] المسؤول الجديد", "New Line Manager Effective Date"), ("[ ] مالحظات [____ No/Yes] تغيير الراتب", ": ........................"), ("", "Salary Change Notes")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-017", "قرار تكليف بفرع أو موقع عمل", "Branch / Work Location Assignment", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-017", "قرار تكليف بفرع أو موقع عمل", "Branch / Work Location Assignment",
          "يُكلف الموظف/ة {{employee_name}} بالعمل في {{location}} خلال الفترة من {{start_date}} إلى {{end_date}}، تحت إشراف {{manager_name}}، مع الالتزام بساعات العمل والتعليمات الخاصة بالموقع.",
          "{{employee_name}} is assigned to work at {{location}} from {{start_date}} to {{end_date}} under the supervision of {{manager_name}}, subject to the location's working hours and instructions.",
          [("[ ] الموقع الفعلي [ ] الموقع الرسمي", "Official Location Actual Location"), ("[ ] المسؤول [From] [To] فترة التكليف", "Assignment Period Supervisor")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-018", "قرار ترقية", "Promotion Decision", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-018", "قرار ترقية", "Promotion Decision",
          "تقديرًا للأداء والكفاءة، تقرر ترقية الموظف/ة {{employee_name}} من وظيفة {{old_title}} إلى وظيفة {{new_title}} اعتبارًا من {{effective_date}}. يطبق أثر الدرجة والراتب وفق الاعتماد المالي المرفق، مع استمرار باقي شروط العقد.",
          "In recognition of performance and competence, {{employee_name}} is promoted from {{old_title}} to {{new_title}} effective {{effective_date}}. Grade and salary impact apply per the attached financial approval; other contract terms continue.",
          [("[ ] المسمى الجديد [ ] المسمى السابق", "Previous Title New Title"), ("[____] /KWD الراتب الجديد [____] /KWD الراتب السابق د.ك د.ك", "Previous Salary New Salary"), ("[DD/MM/YYYY] تاريخ النفاذ [ ] الدرجة المستوى", "Grade / Level Effective Date")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-019", "قرار تعديل راتب", "Salary Adjustment Decision", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-019", "قرار تعديل راتب", "Salary Adjustment Decision",
          "تقرر تعديل راتب الموظف/ة {{employee_name}} من {{old_salary}} د.ك إلى {{new_salary}} د.ك اعتبارًا من {{effective_date}}، وذلك بسبب {{reason}}. يعتمد القرار من الإدارة والموارد البشرية والمالية، ويثبت التغيير في سجل التدقيق (before/after).",
          "The salary of {{employee_name}} is adjusted from KWD {{old_salary}} to KWD {{new_salary}} effective {{effective_date}}, due to {{reason}}. Approved by Management, HR, and Finance, with the change recorded in the audit log (before/after).",
          [("[____] الراتب الرسمي الجديد [____] الراتب الرسمي السابق د.ك د.ك", "Previous Official Salary New Official Salary"), ("[____] الراتب الفعلي الجديد [____] الراتب الفعلي السابق د.ك د.ك", "Previous Actual Salary New Actual Salary"), ("[MM/YYYY] شهر التطبيق [ ] سبب التعديل", "Reason Payroll Month")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-020", "قرار بدل أو مكافأة", "Allowance / Bonus Decision", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-020", "قرار بدل أو مكافأة", "Allowance / Bonus Decision",
          "تقرر منح الموظف/ة {{employee_name}} بدل/مكافأة بقيمة {{amount}} د.ك عن {{reason}} خلال الفترة {{period}}، على أن تُصرف وفق دورة الرواتب والإجراءات المالية المعتمدة.",
          "{{employee_name}} is granted an allowance/bonus of KWD {{amount}} for {{reason}} during the period {{period}}, payable per the approved payroll and finance process.",
          [("[____] /KWD القيمة [Allowance/Bonus] النوع د.ك", "Type Amount"), ("[Payroll/Separate] طريقة الصرف [ ] الفترة", "Period Payment Method"), ("[Yes/No] خاضع لالستقطاع [ ] السبب", "Reason Subject to Deduction")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-021", "قرار خصم", "Deduction Decision", "الإجراءات التأديبية",
     _tpl("HRMS-PR-021", "قرار خصم", "Deduction Decision",
          "بناءً على المرجع/المخالفة {{reference}} وبعد مراجعة المستندات، تقرر خصم مبلغ {{amount}} د.ك من مستحقات الموظف/ة {{employee_name}}، على أن ينفذ في راتب شهر {{payroll_month}}، مع إتاحة حق التظلم وفق السياسة المعتمدة.",
          "Based on {{reference}} and review of supporting records, a deduction of KWD {{amount}} is imposed on {{employee_name}}, to be applied in payroll month {{payroll_month}}, with the right to appeal under approved policy.",
          [("[ ] القيمة [Amount/Days] نوع الخصم", "Deduction Type Value"), ("[MM/YYYY] شهر التنفيذ [ ] المرجع", "Reference Payroll Month"), ("[None/Submitted] حالة التظلم [DD/MM/YYYY] آخر موعد للتظلم", "Appeal Deadline Appeal Status")],
          [("Prepared by Admin", "إعداد الشؤون الإدارية"), ("Legal Review", "مراجعة قانونية"), ("Manager Approval", "اعتماد المدير")], has_ack=True)),
    ("HRMS-PR-022", "إنذار موظف", "Employee Warning Notice", "الإجراءات التأديبية",
     _tpl("HRMS-PR-022", "إنذار موظف", "Employee Warning Notice",
          "بالإشارة إلى الواقعة بتاريخ {{incident_date}} المتعلقة بـ {{incident_summary}}، يوجه إلى الموظف/ة {{employee_name}} هذا الإنذار بضرورة الالتزام بسياسات العمل والتعليمات المعتمدة. تكرار المخالفة سبب لاتخاذ الإجراء المناسب وفق النظام. توقيع الموظف أدناه يفيد العلم والاستلام ولا يعد إقرارًا بصحة الواقعة.",
          "With reference to the incident on {{incident_date}} related to {{incident_summary}}, {{employee_name}} is issued this warning to comply with company policies and instructions. Recurrence justifies further action per the internal rules. The employee's signature acknowledges receipt only and does not constitute admission of the incident.",
          [("[DD/MM/YYYY] تاريخ الواقعة [First/Second] نوع الإنذار", "Warning Level Incident Date"), ("[ ] الإجراء التصحيحي [ ] المخالفة", "Violation Corrective Action"), ("[ ] مرجع السياسة [ ] فترة المتابعة", "Monitoring Period Policy Reference")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-023", "إنذار نهائي", "Final Warning Notice", "الإجراءات التأديبية",
     _tpl("HRMS-PR-023", "إنذار نهائي", "Final Warning Notice",
          "نظرًا لتكرار/جسامة المخالفة الموضحة أدناه (المرجع {{reference}})، يوجه إلى الموظف/ة {{employee_name}} إنذار نهائي. ويعد أي تكرار أو عدم التزام خلال فترة المتابعة سببًا لاتخاذ إجراء أشد وفق القرارات والسياسات المعتمدة.",
          "Due to the repeated/serious violation detailed below (ref {{reference}}), {{employee_name}} is issued a final warning. Any recurrence or failure to comply during the monitoring period may result in stronger action under approved policies.",
          [("[ ] المخالفة الحالية [References] الإنذارات السابقة", "Previous Warnings Current Violation"), ("[ ] فترة المتابعة [ ] الإجراء المطلوب", "Required Action Monitoring Period"), ("[ ] مرجع التحقيق [ ] نتيجة عدم االلتزام", "Consequence . Investigation Ref")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-024", "استدعاء للتحقيق الإداري", "Administrative Investigation Summons", "الإجراءات التأديبية",
     _tpl("HRMS-PR-024", "استدعاء للتحقيق الإداري", "Administrative Investigation Summons",
          "يطلب من الموظف/ة {{employee_name}} الحضور أمام {{investigator}} في {{investigation_date}} بمكان {{location}} لمناقشة موضوع {{subject}}. يحق للموظف تقديم مستنداته وإفادته، ويثبت عدم الحضور دون عذر في سجل التحقيق.",
          "{{employee_name}} is required to attend an administrative investigation before {{investigator}} on {{investigation_date}} at {{location}} regarding {{subject}}. The employee may submit documents and statements; absence without valid reason shall be recorded.",
          [("[DD/MM/YYYYHHMM] التاريخ والوقت [ ] موضوع التحقيق", "........................ :"), ("", "Subject Date & Time"), ("[ ] المحقق اللجنة [ ] المكان", "Location Investigator / Committee"), ("[ ] رقم القضية [ ] المستندات المطلوبة", "Required Documents . Case No")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-025", "قرار إيقاف مؤقت لحين التحقيق", "Temporary Suspension Pending Investigation", "الإجراءات التأديبية",
     _tpl("HRMS-PR-025", "قرار إيقاف مؤقت لحين التحقيق", "Temporary Suspension Pending Investigation",
          "تقرر إيقاف الموظف/ة {{employee_name}} مؤقتًا عن {{suspension_scope}} اعتبارًا من {{start_date}} وحتى {{end_date}} أو انتهاء التحقيق، حفاظًا على سير التحقيق والمصلحة التشغيلية، دون اعتبار القرار حسمًا للنتيجة النهائية.",
          "{{employee_name}} is temporarily suspended from {{suspension_scope}} effective {{start_date}} until {{end_date}} or investigation completion, to protect the investigation and operations. This does not predetermine the final outcome.",
          [("[DD/MM/YYYY] تاريخ البدء [Full/Partial] نطاق الإيقاف", "Suspension Scope Start Date"), ("[Asapproved] الوضع المالي [ ] المدة المتوقعة", "Expected Duration Pay Status"), ("[ ] مرجع التحقيق [Suspend/Retain] العهد الصلاحيات", "Assets / Access . Investigation Ref")],
          [("Prepared By", "إعداد"), ("Legal Review", "مراجعة قانونية"), ("Authorized Approval", "اعتماد صاحب الصلاحية")], has_ack=True)),
    ("HRMS-PR-026", "تكليف واعتماد عمل إضافي", "Overtime Assignment & Approval", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-026", "تكليف واعتماد عمل إضافي", "Overtime Assignment & Approval",
          "اعتمد عمل إضافي للموظف/ة {{employee_name}} بتاريخ {{overtime_date}} لمدة {{hours}} ساعة بسبب {{reason}}. معدل/قيمة الاستحقاق {{rate_or_amount}}. لا تحتسب الساعات إلا بعد التحقق من الحضور، ولا ترحّل للراتب قبل اعتماد المدير والمالية.",
          "Overtime for {{employee_name}} is approved on {{overtime_date}} for {{hours}} hours due to {{reason}}. Rate/entitlement: {{rate_or_amount}}. Hours are recognized only after attendance verification, and shall not be posted to payroll before manager and finance approval.",
          [("[HHMM HHMM] من - إلى [DD/MM/YYYY] التاريخ", ": - :"), ("", "Date From - To"), ("[ ] سبب العمل الإضافي [____] عدد الساعات", "Hours Reason"), ("[____] الساعات المعتمدة [Payment/TimeOff] طريقة التعويض", "Compensation Approved Hours")],
          [("Line Manager Request", "طلب المسؤول المباشر"), ("Attendance Verification", "تحقق الحضور"), ("Final Approval", "االعتماد النهائي")], has_ack=True)),
    ("HRMS-PR-027", "قرار اعتماد إجازة", "Leave Approval Decision", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-027", "قرار اعتماد إجازة", "Leave Approval Decision",
          "اعتمدت إجازة الموظف/ة {{employee_name}} من نوع {{leave_type}} خلال الفترة من {{start_date}} إلى {{end_date}} بإجمالي {{days_count}} يومًا. الرصيد قبل الإجازة {{balance_before}} يومًا وبعدها {{balance_after}} يومًا، وتاريخ العودة المتوقع {{return_date}}. البديل المعتمد إن وجد: {{replacement_employee}}.",
          "Leave for {{employee_name}} of type {{leave_type}} is approved from {{start_date}} to {{end_date}}, total {{days_count}} days. Balance before: {{balance_before}} days, after: {{balance_after}} days. Expected return: {{return_date}}. Approved replacement (if any): {{replacement_employee}}.",
          [("[DD/MM/YYYY] من تاريخ [Annual/Sick/Other] نوع الإجازة", "Leave Type From Date"), ("[____] عدد األيام [DD/MM/YYYY] إلى تاريخ", "To Date Number of Days"), ("[____] الرصيد بعد [____] الرصيد قبل", "Balance Before Balance After")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-028", "إشعار عودة من إجازة", "Return from Leave Notice", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-028", "إشعار عودة من إجازة", "Return from Leave Notice",
          "يفيد هذا الإشعار بأن الموظف/ة {{employee_name}} باشر العمل بعد الإجازة بتاريخ {{return_date}} في الساعة {{return_time}}. تحدث حالته الوظيفية والحضور وفق سجل المباشرة.",
          "This notice confirms that {{employee_name}} resumed work after leave on {{return_date}} at {{return_time}}. Employment and attendance status shall be updated accordingly.",
          [("[DD/MM/YYYY] الإجازة إلى [DD/MM/YYYY] الإجازة من", "Leave From Leave To"), ("[DD/MM/YYYY] تاريخ المباشرة الفعلي [DD/MM/YYYY] تاريخ المباشرة المتوقع", "Expected Return Actual Return"), ("[ ] مالحظات المسؤول [ ] التأخير إن وجد", "Delay, if any Manager Notes")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-029", "بيان رصيد الإجازات", "Leave Balance Statement", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-029", "بيان رصيد الإجازات", "Leave Balance Statement",
          "بيان رصيد إجازات الموظف/ة {{employee_name}} حتى تاريخ {{as_of_date}}: الرصيد المستحق {{entitled_days}} يومًا، المستهلك {{consumed_days}} يومًا، والمتبقي {{remaining_days}} يومًا. أي رصيد سالب أو استثناء يظهر معه سبب وسياسة المعالجة.",
          "Leave balance for {{employee_name}} as of {{as_of_date}}: entitled {{entitled_days}} days, used {{consumed_days}} days, remaining {{remaining_days}} days. Any negative balance or exception is shown with its reason and policy handling.",
          [("[____] /syaD استحقاق السنة [____] /syaD الرصيد المرحل يوم يوم", "Carried Forward Annual Entitlement"), ("[____] /syaD المعلق [____] /syaD المستخدم يوم يوم", "Used Pending"), ("[____] /syaD الرصيد المتاح [____ /+] التعديالت يوم -", "Adjustments Available Balance")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-030", "كشف حضور شهري", "Monthly Attendance Statement", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-030", "كشف حضور شهري", "Monthly Attendance Statement",
          "كشف حضور الموظف/ة {{employee_name}} عن الفترة {{period}}: أيام العمل {{working_days}}، الحضور {{present_days}}، الغياب {{absent_days}}، التأخير {{late_minutes}} دقيقة، الخروج المبكر {{early_minutes}} دقيقة، والعمل الإضافي {{overtime_hours}} ساعة. يعتمد بعد مراجعة الاستثناءات.",
          "Attendance for {{employee_name}} for period {{period}}: workdays {{working_days}}, present {{present_days}}, absent {{absent_days}}, late {{late_minutes}} min, early departure {{early_minutes}} min, overtime {{overtime_hours}} hrs. Approved after reviewing exceptions.",
          [("[____] أيام الحضور [____] أيام العمل", "Working Days Present Days"), ("[____] مرات التأخير [____] أيام الغياب", "Absent Days Late Occurrences"), ("[____] الساعات الإضافية [____] الخروج المبكر", "Early Departures Overtime Hours"), ("[____] المخالفات المفتوحة [____] إجمالي ساعات العمل", "Total Worked Hours Open Exceptions")],
          [("System Generated", "إعداد النظام"), ("Supervisor Review", "مراجعة المشرف"), ("HR Approval", "اعتماد الموارد البشرية")], has_ack=False)),
    ("HRMS-PR-031", "تأكيد تعديل سجل حضور", "Attendance Record Adjustment Confirmation", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-031", "تأكيد تعديل سجل حضور", "Attendance Record Adjustment Confirmation",
          "تم تعديل سجل الحضور الخاص بالموظف/ة {{employee_name}} عن تاريخ {{date}} بناءً على الطلب رقم {{request_no}} والمرجع {{reference}}، مع الاحتفاظ بالقيمة السابقة {{old_value}} والجديدة {{new_value}} في سجل التدقيق. سبب التعديل: {{reason}}.",
          "The attendance record for {{employee_name}} on {{date}} has been adjusted per request {{request_no}} and reference {{reference}}. Previous value {{old_value}} and new value {{new_value}} are retained in the audit log. Reason: {{reason}}.",
          [("", "Checkin/Checkout/["), ("[ ] القيمة السابقة نوع التعديل", "Adjustment Type ]Absence Previous Value"), ("[ ] سبب التعديل [ ] القيمة الجديدة", "New Value Reason"), ("[ ] المرفق الداعم [ ] رقم الطلب", ". Request No Supporting Attachment")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-032", "كشف راتب شهري مبسط", "Simplified Monthly Payroll Statement", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-032", "كشف راتب شهري مبسط", "Simplified Monthly Payroll Statement",
          "كشف رواتب الفترة {{period}}: الأساسي {{basic_total}} د.ك، البدلات {{allowances_total}} د.ك، الإضافي {{overtime_total}} د.ك، خصم الغياب {{absence_deduction}} د.ك، السلف/الأقساط {{loan_deductions}} د.ك، الخصومات الأخرى {{other_deductions}} د.ك، وصافي الرواتب {{net_total}} د.ك. حالة المسيّر: {{payroll_status}}.",
          "Payroll statement for {{period}}: basic {{basic_total}} KWD, allowances {{allowances_total}} KWD, overtime {{overtime_total}} KWD, absence deduction {{absence_deduction}} KWD, loans {{loan_deductions}} KWD, other deductions {{other_deductions}} KWD, net {{net_total}} KWD. Payroll status: {{payroll_status}}.",
          [("[____] البدلات [____] الراتب الأساسي د.ك د.ك", "Basic Salary Allowances"), ("[____] المكافآت [____] العمل الإضافي د.ك د.ك", "Overtime Bonuses"), ("[____] السلف [____] الخصومات د.ك د.ك", "Deductions Advances"), ("[Bank/Cash] طريقة الدفع [____] صافي الراتب د.ك", "Net Salary Payment Method")],
          [("Prepared by Accounts", "إعداد المحاسبة"), ("HR Review", "مراجعة الموارد البشرية"), ("Manager Approval", "اعتماد المدير")], has_ack=False)),
    ("HRMS-PR-033", "إشعار نقص مستندات", "Missing Documents Notice", "المعاملات الحكومية والمستندات",
     _tpl("HRMS-PR-033", "إشعار نقص مستندات", "Missing Documents Notice",
          "نحيط الموظف/ة {{employee_name}} علمًا بأن ملفه يحتاج إلى المستندات التالية: {{missing_documents}}. يرجى رفعها قبل {{deadline}} من خلال {{submission_method}}، وإلا قد يتعذر استكمال المعاملة المرتبطة.",
          "{{employee_name}} is notified that the file requires the following documents: {{missing_documents}}. Please upload or submit them by {{deadline}} via {{submission_method}}, otherwise the related transaction may be suspended.",
          [("[ ] المستندات الناقصة [ ] نوع المعاملة", "Transaction Type Missing Documents"), ("[HRMS/Physical] طريقة التسليم [DD/MM/YYYY] آخر موعد", "Deadline Submission Method"), ("[AwaitingDocuments] حالة المعاملة [ ] المسؤول", "Responsible Officer Transaction Status")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-034", "تفويض تجديد إقامة", "Residency Renewal Authorization", "المعاملات الحكومية والمستندات",
     _tpl("HRMS-PR-034", "تفويض تجديد إقامة", "Residency Renewal Authorization",
          "تفوض شركة {{company_name}} المندوب {{delegate_name}} باستكمال إجراءات تجديد إقامة الموظف/ة {{employee_name}} (رقم مدني {{civil_id}}، إقامة رقم {{residency_no}} المنتهية في {{expiry_date}}). نوع التجديد {{renewal_type}} وسببه {{reason}}، تحت ملف الشركة رقم {{company_file_no}}.",
          "{{company_name}} authorizes delegate {{delegate_name}} to complete the residency renewal of {{employee_name}} (Civil ID {{civil_id}}, Residency {{residency_no}} expiring {{expiry_date}}). Renewal type: {{renewal_type}}, reason: {{reason}}, under company file {{company_file_no}}.",
          [("", "Early days/Normal["), ("", "30-90"), ("[DD/MM/YYYY] انتهاء الإقامة نوع التجديد", "Renewal Type ]<= days Residency Expiry"), ("", "30"), ("[ ] رقم ملف الشركة [ ] مدة التجديد", "Renewal Period . Company File No"), ("", "Passport/Permit/Photo/["), ("المرفقات [ ] المندوب المكلف", "Assigned Delegate Attachments ]Other")],
          [("Legal Affairs", "الشؤون القانونية"), ("Company Manager", "مدير الشركة"), ("Delegate", "المندوب")], has_ack=False)),
    ("HRMS-PR-035", "تفويض تجديد إذن عمل", "Work Permit Renewal Authorization", "المعاملات الحكومية والمستندات",
     _tpl("HRMS-PR-035", "تفويض تجديد إذن عمل", "Work Permit Renewal Authorization",
          "يرجى تجديد إذن العمل رقم {{permit_no}} للموظف/ة {{employee_name}} قبل تاريخ {{expiry_date}} تحت ملف الشركة {{company_file_no}}. الجهة الحكومية {{government_entity}} والرسوم المقدرة {{estimated_fees}}. يكلف المندوب {{delegate_name}} برفع المستندات والنتيجة النهائية في النظام.",
          "Please renew work permit {{permit_no}} for {{employee_name}} before {{expiry_date}} under company file {{company_file_no}}. Government entity: {{government_entity}}, estimated fees: {{estimated_fees}}. Delegate {{delegate_name}} shall upload documents and final outcome.",
          [("[DD/MM/YYYY] تاريخ االنتهاء [ ] رقم إذن العمل", ". Work Permit No Expiry Date"), ("[ ] الترخيص [ ] ملف الشركة", "Company File License"), ("[DD/MM/YYYY] موعد الإنجاز [ ] المندوب", "Delegate Target Completion"), ("", "| / | |")],
          [("Employee/Legal", "شؤون الموظفين القانونية"), ("Manager Approval", "اعتماد المدير"), ("Delegate Execution", "تنفيذ المندوب"), ("Affairs", "")], has_ack=False)),
    ("HRMS-PR-036", "إشعار تحديث البطاقة المدنية أو الجواز", "Civil ID / Passport Update Notice", "المعاملات الحكومية والمستندات",
     _tpl("HRMS-PR-036", "إشعار تحديث البطاقة المدنية أو الجواز", "Civil ID / Passport Update Notice",
          "تم استلام جواز/بطاقة جديدة للموظف/ة {{employee_name}} بدل {{old_passport_no}}. الرقم الجديد {{new_passport_no}}، تاريخ الإصدار {{issue_date}} والانتهاء {{expiry_date}}. يرجى تقديم النسخة قبل {{deadline}} وتحديث الملف الإلكتروني، وفحص أثر التغيير على الإقامة والتصاريح.",
          "New passport/civil ID received for {{employee_name}} replacing {{old_passport_no}}. New number {{new_passport_no}}, issued {{issue_date}}, expiring {{expiry_date}}. Please submit the copy by {{deadline}}, update the electronic file, and check the impact on residency and permits.",
          [("[ ] الرقم الحالي [CivilID/Passport] نوع المستند", "Document Type Current Number"), ("[Upload/SubmitOriginal] المطلوب [DD/MM/YYYY] تاريخ االنتهاء", "Expiry Date Required Action"), ("[Pending/Received] حالة االستالم [DD/MM/YYYY] آخر موعد", "Deadline Receipt Status")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-037", "تكليف مندوب بمعاملة حكومية", "Government Transaction Delegate Assignment", "المعاملات الحكومية والمستندات",
     _tpl("HRMS-PR-037", "تكليف مندوب بمعاملة حكومية", "Government Transaction Delegate Assignment",
          "يكلف المندوب {{delegate_name}} بمتابعة معاملة {{transaction_type}} الخاصة بـ {{employee_or_company}} لدى {{government_entity}}، مرجع رقم {{reference}}. المستندات المسلمة: {{documents_list}}، الموعد المستهدف {{due_date}}. يلتزم المندوب بتحديث حالة المعاملة وإرفاق إيصالاتها والمستند النهائي وإعادة أي عهد.",
          "Delegate {{delegate_name}} is assigned transaction {{transaction_type}} for {{employee_or_company}} at {{government_entity}}, ref {{reference}}. Delivered documents: {{documents_list}}, target date {{due_date}}. The delegate shall update status, attach receipts and final documents, and return any originals or assets.",
          [("[ ] الجهة الحكومية [ ] نوع المعاملة", "Transaction Type Government Entity"), ("[DD/MM/YYYY] الموعد النهائي [ ] رقم المرجع", ". Reference No Deadline"), ("[ ] النتيجة المطلوبة [ ] العهد المبالغ", "Assets / Amounts Required Outcome")],
          [("Task Creator", "إنشاء المهمة"), ("Delegate Acceptance", "استلام المندوب"), ("Closure Approval", "اعتماد الإغالق")], has_ack=True)),
    ("HRMS-PR-038", "التسوية النهائية ونهاية الخدمة", "Final Settlement & End of Service", "إنهاء الخدمة والتسليم",
     _tpl("HRMS-PR-038", "التسوية النهائية ونهاية الخدمة", "Final Settlement & End of Service",
          "التسوية النهائية للموظف/ة {{employee_name}} حتى آخر يوم عمل {{last_working_day}}. أساس الاحتساب {{salary_basis}} د.ك، إجمالي المستحقات {{entitlements_total}} د.ك، الخصومات {{deductions_total}} د.ك، وصافي المستحق {{net_amount}} د.ك. يقر الموظف بالاستلام بعد بيان التفاصيل، مع حفظ الحقوق النظامية.",
          "Final settlement for {{employee_name}} through last working day {{last_working_day}}. Salary basis {{salary_basis}} KWD, total entitlements {{entitlements_total}} KWD, deductions {{deductions_total}} KWD, net payable {{net_amount}} KWD. The employee acknowledges receipt after detailing, preserving statutory rights.",
          [("[____] راتب مستحق [____] مكافأة نهاية الخدمة د.ك د.ك", "End of Service Benefit Outstanding Salary"), ("[____] مستحقات أخرى [____] بدل إجازات د.ك د.ك", "Leave Encashment Other Entitlements"), ("[____] سلف متبقية [____] خصومات عهد د.ك د.ك", "Deductions / Assets Outstanding Advances"), ("[____] الصافي النهائي [____] إجمالي المستحق د.ك د.ك", "Gross Payable Net Settlement")],
          [("Prepared by HR", "إعداد الموارد البشرية"), ("Accounts Review", "مراجعة المحاسبة"), ("Approval & Payment", "االعتماد والصرف")], has_ack=True)),
    ("HRMS-PR-039", "شهادة إخلاء طرف", "Clearance Certificate", "إنهاء الخدمة والتسليم",
     _tpl("HRMS-PR-039", "شهادة إخلاء طرف", "Clearance Certificate",
          "تفيد الإدارات الموضحة أدناه بأن الموظف/ة {{employee_name}} قد سلّم العهد {{assets_list}} والمستندات وأنهى الالتزامات المسجلة. الحالة المالية: {{finance_status}}. توقيعات الأقسام: {{department_signoffs}}. يعتمد إخلاء الطرف بعد اكتمال جميع الجهات دون استثناء.",
          "The departments below confirm that {{employee_name}} has returned assigned assets {{assets_list}} and documents and settled recorded obligations. Finance status: {{finance_status}}. Department signoffs: {{department_signoffs}}. Final clearance is approved only after all sections are completed.",
          [("[Cleared/Pending] المحاسبة [Cleared/Pending] تقنية المعلومات", "IT Accounts"), ("[Cleared/Pending] الفرع الإدارة [Cleared/Pending] المخازن العهد", "Assets / Stores Branch / Department"), ("[Cleared/Pending] الموارد البشرية [Cleared/Pending] الشؤون القانونية", "Legal Affairs HR")],
          [("Department Officer", "مسؤول القسم"), ("HR Review", "مراجعة الموارد البشرية"), ("Final Clearance", "اعتماد الإخلاء")], has_ack=True)),
    ("HRMS-PR-040", "محضر تسليم عهدة", "Asset Handover Record", "إنهاء الخدمة والتسليم",
     _tpl("HRMS-PR-040", "محضر تسليم عهدة", "Asset Handover Record",
          "بتاريخ {{date}} تم تسليم/استلام العهد التالية {{assets_list}} بين الطرفين، بعد معاينتها بحالة {{return_condition}}. المستلم {{employee_name}} يتحمل مسؤولية المحافظة عليها واستخدامها لأغراض العمل، وإعادتها عند الطلب أو انتهاء الخدمة. الأضرار/النواقص: {{issues}}.",
          "On {{date}}, the assets {{assets_list}} were handed over/received between the parties after inspection with condition {{return_condition}}. Recipient {{employee_name}} is responsible for safekeeping and business use, and shall return them on request or end of service. Damages/shortages: {{issues}}.",
          [("[ ] الرقم التسلسلي [Laptop/Phone/Keys/Other] نوع العهدة", "Asset Type . Serial No"), ("[ ] الملحقات [New/Good/Damaged] الحالة عند التسليم", "Condition Accessories"), ("[ ] إلى الموظف [ ] من الموظف", "From Employee To Employee")],
          [("Handed Over By", "المسلم"), ("Received By", "المستلم"), ("Asset Controller", "مسؤول العهد")], has_ack=True)),
    ("HRMS-PR-041", "محضر استلام وتسليم مستندات", "Document Receipt & Handover Record", "إنهاء الخدمة والتسليم",
     _tpl("HRMS-PR-041", "محضر استلام وتسليم مستندات", "Document Receipt & Handover Record",
          "يرجى من الشؤون القانونية مراجعة {{subject_or_document}} بسبب {{review_reason}}. المرفقات {{attachments}}، والمطلوب {{requested_opinion}}. تسجل النتيجة والتوصية والقيود على الاطلاع في الملف.",
          "Please have Legal Affairs review {{subject_or_document}} for {{review_reason}}. Attachments: {{attachments}}, requested opinion: {{requested_opinion}}. Result, recommendation, and access restrictions shall be recorded in the file.",
          [("", "Passport/CivilID/Contract/["), ("[ ] الرقم نوع المستند", "Document Type ]Other . Document No"), ("[ ] الغرض [ ] أصل أم نسخة", "Original / Copy Purpose"), ("[DD/MM/YYYY] موعد الإعادة [DD/MM/YYYY] تاريخ االستالم", "Receipt Date Return Date")],
          [("Handed Over By", "المسلم"), ("Received By", "المستلم"), ("Witness / Reviewer", "الشاهد / المراجع")], has_ack=True)),
    ("HRMS-PR-042", "سجل اعتماد التوقيع الإلكتروني", "Electronic Signature Approval Record", "إنهاء الخدمة والتسليم",
     _tpl("HRMS-PR-042", "سجل اعتماد التوقيع الإلكتروني", "Electronic Signature Approval Record",
          "سجل التوقيع الإلكتروني للمستند {{document_reference}} (بصمة {{document_hash}}): الموقعون {{signers}}، أوقات التوقيع {{timestamps}}، وعناوين الأجهزة/الجلسة {{technical_metadata}} عند توفرها. لا يعتد بأي تعديل لاحق دون إنشاء إصدار جديد.",
          "Electronic signature record for document {{document_reference}} (hash {{document_hash}}): signers {{signers}}, timestamps {{timestamps}}, and session/device metadata {{technical_metadata}} where available. Subsequent changes require a new version.",
          [("[ ] رقم المستند [ ] نوع المستند", "Document Type . Document No"), ("[ ] رمز التحقق [ ] الإصدار", "1.0 ........................"), ("", "Version Verification Code"), ("[Approved/Rejected] حالة االعتماد [DD/MM/YYYYHHMM] تاريخ الإنشاء", ":"), ("", "Created At Approval Status")],
          [("Electronic Creator", "منشئ إلكتروني"), ("Electronic Reviewer", "المراجع الإلكتروني"), ("Electronic Approver", "المعتمد الإلكتروني")], has_ack=False)),
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
    accountant = staff(7, "accountant", f"محاسب {cfg['name']}", PW["accountant"])
    db.flush()
    db.add(models.BranchSupervisor(company_id=company.id, branch_id=branches[0].id, user_id=sup1.id))
    db.add(models.BranchSupervisor(company_id=company.id, branch_id=branches[1].id, user_id=sup2.id))

    # المحاسب موظف أيًضا (له ملف وحضور خاص به مثل أي موظف)، بمسمى وظيفي "محاسب"
    accountant_emp = models.Employee(
        company_id=company.id, civil_id=civ(p, 7), name=accountant.full_name,
        nationality="كويتي", worker_type="موظف", job_title="محاسب", basic_salary=750,
        hire_date=d(-500), status="active", license_id=license_.id, branch_id=branches[0].id,
        shift_id=shift.id, attendance_mode="both", annual_leave_balance=30)
    db.add(accountant_emp)
    db.flush()
    accountant.employee_id = accountant_emp.id

    # موظفون
    emps = []
    for i, (name, nat, job, sal, mode) in enumerate(cfg["employees"]):
        branch = branches[i % 2]
        # SEC2-17: mode='none' يجب أن يكون مصحوبًا بإعفاء موثّق (مدير مقره الميداني/إداري
        # مرن)، ليس القيمة الافتراضية الصامتة.
        is_exempt = mode == "none"
        exempt_reason = "مدير مقره ميداني — إشراف بلا شفت ثابت" if is_exempt else None
        e = models.Employee(company_id=company.id, civil_id=civ(p, 100 + i + 1), name=name,
                            nationality=nat, worker_type=("موظف" if mode == "none" else "عامل"),
                            job_title=job, basic_salary=sal, hire_date=d(-900 - i * 120),
                            status="active", license_id=license_.id, branch_id=branch.id,
                            shift_id=shift.id, attendance_mode=mode, annual_leave_balance=30,
                            attendance_exempt=is_exempt,
                            attendance_exempt_reason=exempt_reason)
        db.add(e)
        emps.append(e)
    db.flush()

    # هيكل تنظيمي (P0-07): إدارات فعلية + مدير مباشر لكل موظف — بيانات ديمو كانت بلا
    # أقسام ولا مديرين إطلاًقا رغم وجود الحقول (Employee.department_id/direct_manager_id).
    depts = [
        models.Department(company_id=company.id, branch_id=branches[0].id,
                          name="المبيعات والتشغيل", manager_user_id=manager.id),
        models.Department(company_id=company.id, branch_id=branches[1].id,
                          name="الشؤون الفنية", manager_user_id=manager.id),
        models.Department(company_id=company.id, branch_id=branches[0].id,
                          name="الإدارة والحسابات", manager_user_id=manager.id),
    ]
    for dept in depts:
        db.add(dept)
    db.flush()
    # أول موظف بمسمى إشرافي (مدير فرع/مشرف/مدير مشروع) يصبح المدير المباشر للبقية
    lead = next((e for e in emps if any(w in e.job_title for w in ("مدير", "مشرف"))), None)
    for i, e in enumerate(emps):
        e.department_id = depts[i % len(depts)].id
        if lead and e.id != lead.id:
            e.direct_manager_id = lead.id

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
    # سجلات حضور تجريبية (P0-07: توسيع التغطية لتشمل أكثر من موظفَين فقط)
    _add_attendance(db, emps[0], emps[0].branch_id, 5, late_on=2)
    _add_attendance(db, emps[1], emps[1].branch_id, 4)
    _add_attendance(db, emps[3], emps[3].branch_id, 3)
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
                  models.Employee, models.Department, models.License, models.User, models.Company):
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
    for code, name, name_en, cat, body in DEFAULT_TEMPLATES:
        db.add(models.DocumentTemplate(company_id=None, code=code, name=name, name_en=name_en,
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
