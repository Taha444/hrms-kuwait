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


# 42 قالب طباعة رسمي ثنائي اللغة (HRMS-PR-001..042) — تصميم القوالب المعتمد (استبدال كامل لتصميم PRN السابق)
DEFAULT_TEMPLATES = [
    ("HRMS-PR-001", "شهادة راتب", "Salary Certificate", "الشهادات والخطابات",
     _tpl("HRMS-PR-001", "شهادة راتب", "Salary Certificate",
          "تشهد شركة اسم الشركة بأن السيد السيدة اسم الموظف ، حامل الرقم المدني الرقم المدني ، يعمل لديها بوظيفة المسمى الوظيفي منذ تاريخ تاريخ التعيين ، ويتقاضى راتبا شهريا إجماليا قدره المبلغ د.ك. وقد أصدرت هذه الشهادة بناء على طلبه طلبها دون أدنى مسؤولية على الشركة تجاه الغير.",
          "certifies that Mr./Ms. ]Employee Name[, Civil ID ]Civil ID[, has been employed as ]Job Title[ since ]Joining Date[ and receives a total monthly salary of KWD ]Amount[. This Company Name certificate is issued upon request without liability to third parties",
          [("[____] /KWD البدلات [____] /KWD الراتب الأساسي د.ك د.ك", "Basic Salary Allowances"), ("[Bank/Embassy/Other] الجهة الموجه إليها [____] /KWD الإجمالي د.ك", "Total Salary Addressed To")],
          [("Prepared by HR", "إعداد الموارد البشرية"), ("Manager Review", "مراجعة المدير"), ("Authorized Signatory", "المخول بالتوقيع")], has_ack=False)),
    ("HRMS-PR-002", "شهادة لمن يهمه الأمر", "To Whom It May Concern Certificate", "الشهادات والخطابات",
     _tpl("HRMS-PR-002", "شهادة لمن يهمه الأمر", "To Whom It May Concern Certificate",
          "إلى من يهمه الأمر، تفيد شركة اسم الشركة بأن السيد السيدة اسم الموظف يعمل لديها بصفة المسمى الوظيفي ، وأن علاقته الوظيفية قائمة حتى تاريخ إصدار هذه الشهادة. أعطيت له لها بناء على طلبه طلبها لاستخدامها فيما خصصت له.",
          "/ / s To whom it may concern, ]Company Name[ confirms that Mr./Ms. ]Employee Name[ is employed as ]Job Title[ and remains actively employed as of the issue date. Issued upon request for its intended purpose",
          [("[Fixed/Unlimited] نوع العقد [DD/MM/YYYY] تاريخ التعيين", "Joining Date Contract Type"), ("[ ] الغرض [Active] حالة الموظف", "Employment Status Purpose")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-003", "شهادة خبرة", "Experience Certificate", "الشهادات والخطابات",
     _tpl("HRMS-PR-003", "شهادة خبرة", "Experience Certificate",
          "تشهد شركة اسم الشركة بأن السيد السيدة اسم الموظف قد عمل لديها خلال الفترة من من إلى إلى بوظيفة المسمى الوظيفي . وقد أدى أدت المهام الموكلة إليه إليها وفق سجلات الشركة. أصدرت هذه الشهادة بناء على طلبه طلبها.",
          "s / / ] [ . ] [ certifies that Mr./Ms. ]Employee Name[ worked from ]From[ to ]To[ as ]Job Title[ and performed the assigned duties according to company records. Issued upon request Company Name",
          [("[ ] القسم الأخير [From] [To] فترة الخدمة", "Service Period Last Department"), ("[Optional] التقييم العام [ ] سبب انتهاء الخدمة", "Reason for Leaving General Rating")],
          [("Prepared by HR", "إعداد الموارد البشرية"), ("Legal Review", "مراجعة الشؤون القانونية"), ("Authorized Signatory", "المخول بالتوقيع")], has_ack=False)),
    ("HRMS-PR-004", "شهادة حالة وظيفية", "Employment Status Certificate", "الشهادات والخطابات",
     _tpl("HRMS-PR-004", "شهادة حالة وظيفية", "Employment Status Certificate",
          "تفيد شركة اسم الشركة بأن بيانات الحالة الوظيفية للموظف الموضح أعاله كما هي مبينة في هذا المستند حتى تاريخ الإصدار، وقد تم استخراجها من نظام الموارد البشرية.",
          ". ] [ confirms that the employment status shown in this document is accurate as of the issue date and has been extracted from the HRMS Company Name",
          [("", "Active/Leave/Suspended/["), ("[DD/MM/YYYY] تاريخ بداية الحالة الحالة", "Status ]Ended Status Start Date"), ("[ ] المسؤول المباشر [Fulltime/Parttime] الدوام", "Work Schedule Line Manager")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-005", "خطاب عدم ممانعة", "No Objection Certificate", "الشهادات والخطابات",
     _tpl("HRMS-PR-005", "خطاب عدم ممانعة", "No Objection Certificate",
          "تشهد شركة اسم الشركة بأنها لا تمانع في وصف الغرض للموظف اسم الموظف ، وذلك بشرط عدم تعارضه مع التزاماته الوظيفية وسياسات الشركة، ودون ترتيب أي التزام مالي أو قانوني إضافي على الشركة ما لم يذكر خالف ذلك صراحة.",
          "has no objection to ]Purpose[ for ]Employee Name[, provided it does not conflict with employment obligations or company policy and creates no additional financial or legal Company Name liability unless expressly stated",
          [("[From] [To] الفترة [ ] الغرض", "Purpose Period"), ("[ ] الجهة المستفيدة [ ] الشروط", "Conditions Beneficiary Entity")],
          [("Prepared By", "إعداد"), ("Legal Review", "مراجعة قانونية"), ("Manager Approval", "اعتماد المدير")], has_ack=False)),
    ("HRMS-PR-006", "بيان بيانات موظف", "Employee Data Statement", "الشهادات والخطابات",
     _tpl("HRMS-PR-006", "بيان بيانات موظف", "Employee Data Statement",
          "هذا البيان مستخرج من ملف الموظف في نظام الموارد البشرية ويعرض البيانات المسجلة وقت الإصدار. أي تعديل الحق يخضع لسجل التدقيق والصلاحيات المعتمدة.",
          "This statement is generated from the employee file in the HRMS and reflects the data recorded at the time of issue. Subsequent changes are subject to audit logs and approved permissions",
          [("[ ] نوع العقد [DD/MM/YYYY] تاريخ التعيين", "Joining Date Contract Type"), ("[____] /KWD الراتب الفعلي [____] /KWD الراتب الرسمي د.ك د.ك", "Official Salary Actual Salary"), ("[ ] مكان العمل الفعلي [ ] مكان العمل الرسمي", "Official Work Location Actual Work Location"), ("[DD/MM/YYYY] انتهاء الإقامة [ ] رقم الإقامة", ". Residency No Residency Expiry")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-007", "شهادة مدة خدمة", "Length of Service Certificate", "الشهادات والخطابات",
     _tpl("HRMS-PR-007", "شهادة مدة خدمة", "Length of Service Certificate",
          "تشهد شركة اسم الشركة بأن مدة خدمة الموظف اسم الموظف المحتسبة وفق سجلات الشركة تمتد من تاريخ التعيين حتى تاريخ االحتساب ، بإجمالي مدة قدرها السنوات األشهر األيام .",
          ". ] [ certifies that ]Employee Name[ has completed service from ]Joining Date[ to ]Calculation Date[, totaling ]Years/Months/Days[ according to company records Company Name",
          [("[DD/MM/YYYY] تاريخ االحتساب [DD/MM/YYYY] تاريخ بداية الخدمة", "Service Start Calculation Date"), ("[None/Details] فترات االنقطاع [Y/M/D] مدة الخدمة", "Service Length Excluded Periods")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-008", "خطاب تحويل راتب للبنك", "Bank Salary Transfer Letter", "الشهادات والخطابات",
     _tpl("HRMS-PR-008", "خطاب تحويل راتب للبنك", "Bank Salary Transfer Letter",
          "السادة اسم البنك المحترمون، نحيطكم علما بأن الموظف اسم الموظف يعمل لدى شركة اسم الشركة ، وقد تقرر تحويل راتبه الشهري إلى الحساب الموضح أدناه اعتبارا من راتب شهر الشهر السنة ، وذلك وفق الإجراءات الداخلية المعتمدة.",
          "Dear ]Bank Name[, please be informed that ]Employee Name[ is employed by ]Company Name[. The monthly salary shall be transferred to the account below effective from the payroll month ]Month/Year[, subject to approved internal procedures",
          [("[ ] اسم البنك", "IBAN/"), ("[ ] رقم الحساب", "Bank Name Account / IBAN"), ("[DD/MM/YYYY] تاريخ البدء [____] /KWD راتب التحويل د.ك", "Transfer Salary Effective Date")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-009", "إفادة استمرارية راتب", "Salary Continuity Confirmation", "الشهادات والخطابات",
     _tpl("HRMS-PR-009", "إفادة استمرارية راتب", "Salary Continuity Confirmation",
          "تفيد شركة اسم الشركة بأن الموظف اسم الموظف ما زال على رأس عمله، وأن راتبه يصرف وفق دورة الرواتب المعتمدة بالشركة، مع خضوع أي تغيير الحق للقرارات والسياسات الداخلية.",
          "confirms that ]Employee Name[ remains actively employed and receives salary according to the company payroll cycle. Any future change is subject to internal decisions and Company Name policies",
          [("[Bank/Cash] طريقة الصرف [Monthly] دورة الصرف", "Payroll Cycle Payment Method"), ("[Active] الحالة [MM/YYYY] آخر راتب مصروف", "Last Payroll Month Status")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-010", "خطاب موجه لجهة رسمية", "Official Entity Letter", "الشهادات والخطابات",
     _tpl("HRMS-PR-010", "خطاب موجه لجهة رسمية", "Official Entity Letter",
          "السادة اسم الجهة المحترمون، بالإشارة إلى طلبكم موضوع الموضوع ، نفيدكم بأن بيانات الموظف الموضح أعاله صحيحة وفق سجلات شركة اسم الشركة حتى تاريخ إصدار هذا الخطاب. وتفضلوا بقبول فائق االحترام.",
          "Dear ]Entity Name[, with reference to ]Subject[, we confirm that the above employee information is accurate according to ]Company Name[ records as of the issue date. Yours faithfully",
          [("[ ] الموضوع [ ] الجهة", "Entity Subject"), ("[ ] المرفقات [ ] رقم المرجع الخارجي", "External Reference Attachments")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-011", "خطاب عرض وظيفي", "Employment Offer Letter", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-011", "خطاب عرض وظيفي", "Employment Offer Letter",
          "يسر شركة اسم الشركة أن تقدم للسيد السيدة اسم المرشح عرضا للعمل بوظيفة المسمى الوظيفي في مكان العمل ، وفق الشروط الموضحة أدناه. يصبح العرض نافذا بعد توقيع الطرفين واستكمال المستندات والموافقات المطلوبة.",
          "is pleased to offer Mr./Ms. ]Candidate Name[ employment as ]Job Title[ at ]Work Location[, subject to the terms below. The offer becomes effective upon signature by both Company Name parties and completion of required documents and approvals",
          [("[____] /KWD إجمالي الراتب [____] /KWD الراتب الأساسي د.ك د.ك", "Basic Salary Total Package"), ("[DD/MM/YYYY] تاريخ المباشرة [ ] فترة التجربة", "Probation Start Date"), ("[DD/MM/YYYY] مدة صلاحية العرض [ ] ساعات العمل", "Working Hours Offer Validity")],
          [("Prepared by HR", "إعداد الموارد البشرية"), ("Manager Approval", "اعتماد المدير"), ("Candidate Acceptance", "قبول المرشح")], has_ack=True)),
    ("HRMS-PR-012", "إشعار تجديد عقد", "Contract Renewal Notice", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-012", "إشعار تجديد عقد", "Contract Renewal Notice",
          "نحيط الموظف اسم الموظف علما بأن الشركة ترغب في تجديد عقد العمل اعتبارا من تاريخ البدء ولمدة المدة ، وفق الشروط والتعديالت الموضحة أدناه. يرجى إبداء الموافقة أو الملاحظات خلال عدد أيام عمل.",
          "is hereby notified that the company intends to renew the employment contract effective ]Start Date[ for ]Duration[, subject to the terms and amendments below. Please confirm Employee Name acceptance or comments within ]Number[ working days",
          [("[____] /KWD الراتب الجديد [ ] مدة التجديد د.ك ........................", "Renewal Period New Salary"), ("[ ] مكان العمل [ ] المسمى الوظيفي", "Job Title Work Location"), ("[ ] مالحظات [DD/MM/YYYY] آخر موعد للرد", "Response Deadline Notes")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-013", "إشعار عدم تجديد عقد", "Contract Non-Renewal Notice", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-013", "إشعار عدم تجديد عقد", "Contract Non-Renewal Notice",
          "يخطر الموظف اسم الموظف بأن عقد العمل الحالي لن يتم تجديده بعد تاريخ انتهائه في تاريخ االنتهاء . ويستمر الموظف في أداء واجباته وتسليم العهد والمستندات حتى آخر يوم عمل، مع استكمال إجراءات التسوية وإخلاء الطرف.",
          "is notified that the current employment contract will not be renewed after its expiry on ]Expiry Date[. Duties, handover, final settlement, and clearance procedures must be Employee Name completed through the last working day",
          [("[DD/MM/YYYY] آخر يوم عمل [DD/MM/YYYY] تاريخ انتهاء العقد", "Contract Expiry Last Working Day"), ("[ ] إجراءات التسليم [ ] فترة الإشعار", "Notice Period Handover Requirements")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-014", "قبول استقالة", "Resignation Acceptance", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-014", "قبول استقالة", "Resignation Acceptance",
          "بالإشارة إلى االستقالة المقدمة من الموظف اسم الموظف بتاريخ تاريخ الطلب ، تقرر قبولها، على أن يكون آخر يوم عمل هو التاريخ . ويلتزم الموظف باستكمال التسليم وإخلاء الطرف وتسوية المستحقات وفق الإجراءات المعتمدة.",
          "With reference to the resignation submitted by ]Employee Name[ on ]Request Date[, the resignation is accepted and the last working day shall be ]Date[. Handover, clearance, and final settlement must be completed under approved procedures",
          [("[DD/MM/YYYY] آخر يوم عمل [DD/MM/YYYY] تاريخ تقديم االستقالة", "Resignation Date Last Working Day"), ("[Pending/Completed] حالة التسوية [ ] فترة الإشعار", "Notice Period Settlement Status")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-015", "قرار إنهاء خدمة", "Employment Termination Decision", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-015", "قرار إنهاء خدمة", "Employment Termination Decision",
          "استنادا إلى الصلاحيات المعتمدة ونتيجة سبب الإنهاء المرجع ، تقرر إنهاء خدمة الموظف اسم الموظف اعتبارا من التاريخ . تستكمل إجراءات التسليم والتسوية النهائية وإخلاء الطرف، مع حفظ حق الموظف في التظلم وفق سياسة الشركة.",
          "Based on approved authority and ]Reason/Reference[, the employment of ]Employee Name[ is terminated effective ]Date[. Handover, final settlement, and clearance shall be completed, while preserving the employee’s right to appeal under company policy",
          [("", "Decision/Investigation/["), ("المرجع [ ] سبب الإنهاء", "Reason Reference ]Contract"), ("[DD/MM/YYYY] حق التظلم حتى [DD/MM/YYYY] تاريخ النفاذ", "Effective Date Appeal Deadline")],
          [("Prepared by HR", "إعداد الموارد البشرية"), ("Legal Review", "مراجعة الشؤون القانونية"), ("Authorized Approval", "اعتماد صاحب الصلاحية")], has_ack=True)),
    ("HRMS-PR-016", "قرار نقل موظف", "Employee Transfer Decision", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-016", "قرار نقل موظف", "Employee Transfer Decision",
          "تقرر نقل الموظف اسم الموظف من القسم الفرع الحالي إلى القسم الفرع الجديد اعتبارا من التاريخ ، مع تحديث المسؤول المباشر ومكان العمل الفعلي والصلاحيات والعهد المرتبطة بالوظيفة الجديدة.",
          "is transferred from ]Current Department/Branch[ to ]New Department/Branch[ effective ]Date[. Reporting line, actual work location, permissions, and assigned assets shall be Employee Name updated accordingly",
          [("[Department/Branch] إلى [Department/Branch] من", "From To"), ("[DD/MM/YYYY] تاريخ النفاذ [ ] المسؤول الجديد", "New Line Manager Effective Date"), ("[ ] مالحظات [____ No/Yes] تغيير الراتب", ": ........................"), ("", "Salary Change Notes")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-017", "قرار تكليف بفرع أو موقع عمل", "Branch / Work Location Assignment", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-017", "قرار تكليف بفرع أو موقع عمل", "Branch / Work Location Assignment",
          "يكلف الموظف اسم الموظف بالعمل في الفرع الموقع خلال الفترة من من إلى إلى ، تحت إشراف اسم المسؤول ، مع االلتزام بساعات العمل والتعليمات الخاصة بالموقع.",
          ". ] [ is assigned to work at ]Branch/Location[ from ]From[ to ]To[ under the supervision of ]Manager Name[, subject to the location’s working hours and instructions Employee Name",
          [("[ ] الموقع الفعلي [ ] الموقع الرسمي", "Official Location Actual Location"), ("[ ] المسؤول [From] [To] فترة التكليف", "Assignment Period Supervisor")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-018", "قرار ترقية", "Promotion Decision", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-018", "قرار ترقية", "Promotion Decision",
          "تقديرا للأداء والكفاءة، تقرر ترقية الموظف اسم الموظف من وظيفة الحالية إلى وظيفة الجديدة اعتبارا من التاريخ ، وتُعدَّل البيانات الوظيفية والمالية والصلاحيات وفق التفاصيل أدناه.",
          "In recognition of performance and competence, ]Employee Name[ is promoted from ]Current Role[ to ]New Role[ effective ]Date[. Employment data, compensation, and permissions shall be updated as detailed below",
          [("[ ] المسمى الجديد [ ] المسمى السابق", "Previous Title New Title"), ("[____] /KWD الراتب الجديد [____] /KWD الراتب السابق د.ك د.ك", "Previous Salary New Salary"), ("[DD/MM/YYYY] تاريخ النفاذ [ ] الدرجة المستوى", "Grade / Level Effective Date")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-019", "قرار تعديل راتب", "Salary Adjustment Decision", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-019", "قرار تعديل راتب", "Salary Adjustment Decision",
          "تقرر تعديل راتب الموظف اسم الموظف اعتبارا من التاريخ وفق التفاصيل أدناه. يطبق التعديل في دورة الرواتب المحددة بعد اكتمال االعتماد، مع توثيق الراتب الرسمي والراتب الفعلي كلٌّ على حدة.",
          "The salary of ]Employee Name[ is adjusted effective ]Date[ as detailed below. The change shall be applied in the designated payroll cycle after approval, with official and actual salary recorded separately",
          [("[____] الراتب الرسمي الجديد [____] الراتب الرسمي السابق د.ك د.ك", "Previous Official Salary New Official Salary"), ("[____] الراتب الفعلي الجديد [____] الراتب الفعلي السابق د.ك د.ك", "Previous Actual Salary New Actual Salary"), ("[MM/YYYY] شهر التطبيق [ ] سبب التعديل", "Reason Payroll Month")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-020", "قرار بدل أو مكافأة", "Allowance / Bonus Decision", "العقود والقرارات الوظيفية",
     _tpl("HRMS-PR-020", "قرار بدل أو مكافأة", "Allowance / Bonus Decision",
          "تقرر منح الموظف اسم الموظف بدل مكافأة بقيمة المبلغ د.ك، وذلك عن السبب الفترة ، على أن تصرف وفق دورة الرواتب والإجراءات المالية المعتمدة.",
          ". ] [ is granted an ]Allowance/Bonus[ of KWD ]Amount[ for ]Reason/Period[, payable according to the approved payroll and finance process Employee Name",
          [("[____] /KWD القيمة [Allowance/Bonus] النوع د.ك", "Type Amount"), ("[Payroll/Separate] طريقة الصرف [ ] الفترة", "Period Payment Method"), ("[Yes/No] خاضع لالستقطاع [ ] السبب", "Reason Subject to Deduction")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-021", "قرار خصم", "Deduction Decision", "الإجراءات التأديبية",
     _tpl("HRMS-PR-021", "قرار خصم", "Deduction Decision",
          "بناء على المرجع المخالفة وبعد مراجعة المستندات، تقرر خصم مبلغ المبلغ د.ك عدد األيام من مستحقات الموظف اسم الموظف ، على أن ينفذ في راتب شهر الشهر ، مع إتاحة حق التظلم وفق السياسة المعتمدة.",
          "Based on ]Reference/Violation[ and review of supporting records, a deduction of KWD ]Amount[ / ]Days[ is imposed on ]Employee Name[, to be applied in payroll month ]Month[, with the right to appeal under approved policy",
          [("[ ] القيمة [Amount/Days] نوع الخصم", "Deduction Type Value"), ("[MM/YYYY] شهر التنفيذ [ ] المرجع", "Reference Payroll Month"), ("[None/Submitted] حالة التظلم [DD/MM/YYYY] آخر موعد للتظلم", "Appeal Deadline Appeal Status")],
          [("Prepared by Admin", "إعداد الشؤون الإدارية"), ("Legal Review", "مراجعة قانونية"), ("Manager Approval", "اعتماد المدير")], has_ack=True)),
    ("HRMS-PR-022", "إنذار موظف", "Employee Warning Notice", "الإجراءات التأديبية",
     _tpl("HRMS-PR-022", "إنذار موظف", "Employee Warning Notice",
          "يوجه إلى الموظف اسم الموظف إنذار بسبب وصف المخالفة الواقعة بتاريخ التاريخ . يطلب االلتزام بالتعليمات والسياسات وعدم تكرار المخالفة، وإال قد تتخذ إجراءات تصاعدية وفق النظام الداخلي.",
          "is issued a warning for ]Violation Description[ occurring on ]Date[. The employee must comply with company policies and avoid recurrence; otherwise, progressive action may Employee Name be taken under internal rules",
          [("[DD/MM/YYYY] تاريخ الواقعة [First/Second] نوع الإنذار", "Warning Level Incident Date"), ("[ ] الإجراء التصحيحي [ ] المخالفة", "Violation Corrective Action"), ("[ ] مرجع السياسة [ ] فترة المتابعة", "Monitoring Period Policy Reference")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-023", "إنذار نهائي", "Final Warning Notice", "الإجراءات التأديبية",
     _tpl("HRMS-PR-023", "إنذار نهائي", "Final Warning Notice",
          "نظرا لتكرار جسامة المخالفة الموضحة أدناه، يوجه إلى الموظف اسم الموظف إنذار نهائي. ويعد أي تكرار أو عدم التزام خلال فترة المتابعة سببا التخاذ إجراء أشد وفق القرارات والسياسات المعتمدة.",
          "Due to the repeated/serious violation detailed below, ]Employee Name[ is issued a final warning. Any recurrence or failure to comply during the monitoring period may result in stronger action under approved policies",
          [("[ ] المخالفة الحالية [References] الإنذارات السابقة", "Previous Warnings Current Violation"), ("[ ] فترة المتابعة [ ] الإجراء المطلوب", "Required Action Monitoring Period"), ("[ ] مرجع التحقيق [ ] نتيجة عدم االلتزام", "Consequence . Investigation Ref")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-024", "استدعاء للتحقيق الإداري", "Administrative Investigation Summons", "الإجراءات التأديبية",
     _tpl("HRMS-PR-024", "استدعاء للتحقيق الإداري", "Administrative Investigation Summons",
          "يطلب من الموظف اسم الموظف الحضور أمام لجنة مسؤول التحقيق في التاريخ والمكان المحددين أدناه لمناقشة موضوع الموضوع . يجوز للموظف تقديم مستنداته وإفادته، ويثبت عدم الحضور دون عذر في سجل التحقيق.",
          "is required to attend an administrative investigation at the date and place below regarding ]Subject[. The employee may submit documents and statements; absence without Employee Name valid reason shall be recorded",
          [("[DD/MM/YYYYHHMM] التاريخ والوقت [ ] موضوع التحقيق", "........................ :"), ("", "Subject Date & Time"), ("[ ] المحقق اللجنة [ ] المكان", "Location Investigator / Committee"), ("[ ] رقم القضية [ ] المستندات المطلوبة", "Required Documents . Case No")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-025", "قرار إيقاف مؤقت لحين التحقيق", "Temporary Suspension Pending Investigation", "الإجراءات التأديبية",
     _tpl("HRMS-PR-025", "قرار إيقاف مؤقت لحين التحقيق", "Temporary Suspension Pending Investigation",
          "تقرر إيقاف الموظف اسم الموظف مؤقتا عن العمل بعض الصلاحيات اعتبارا من التاريخ وحتى التاريخ انتهاء التحقيق ، حفاظا على سير التحقيق والمصلحة التشغيلية، دون اعتبار القرار حسما للنتيجة النهائية.",
          "is temporarily suspended from ]Work/Specific Permissions[ effective ]Date[ until ]Date/Investigation Completion[ to protect the investigation and operations. This does not Employee Name predetermine the final outcome",
          [("[DD/MM/YYYY] تاريخ البدء [Full/Partial] نطاق الإيقاف", "Suspension Scope Start Date"), ("[Asapproved] الوضع المالي [ ] المدة المتوقعة", "Expected Duration Pay Status"), ("[ ] مرجع التحقيق [Suspend/Retain] العهد الصلاحيات", "Assets / Access . Investigation Ref")],
          [("Prepared By", "إعداد"), ("Legal Review", "مراجعة قانونية"), ("Authorized Approval", "اعتماد صاحب الصلاحية")], has_ack=True)),
    ("HRMS-PR-026", "تكليف واعتماد عمل إضافي", "Overtime Assignment & Approval", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-026", "تكليف واعتماد عمل إضافي", "Overtime Assignment & Approval",
          "يكلف الموظف اسم الموظف بأداء عمل إضافي في التاريخ الفترة المحددة لتنفيذ المهمة . لا تحتسب الساعات إال بعد التحقق من الحضور واعتماد المسؤول المباشر والجهة المخولة.",
          "is assigned overtime during the specified date/period to perform ]Task[. Hours are recognized only after attendance verification and approval by the line manager and Employee Name authorized party",
          [("[HHMM HHMM] من - إلى [DD/MM/YYYY] التاريخ", ": - :"), ("", "Date From - To"), ("[ ] سبب العمل الإضافي [____] عدد الساعات", "Hours Reason"), ("[____] الساعات المعتمدة [Payment/TimeOff] طريقة التعويض", "Compensation Approved Hours")],
          [("Line Manager Request", "طلب المسؤول المباشر"), ("Attendance Verification", "تحقق الحضور"), ("Final Approval", "االعتماد النهائي")], has_ack=True)),
    ("HRMS-PR-027", "قرار اعتماد إجازة", "Leave Approval Decision", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-027", "قرار اعتماد إجازة", "Leave Approval Decision",
          "تمت الموافقة على إجازة الموظف اسم الموظف وفق النوع والفترة الموضحين أدناه. يلتزم الموظف بتسليم األعمال قبل المغادرة والعودة في الموعد المحدد، ويحدث رصيد الإجازة تلقائيا بعد االعتماد.",
          "The leave request of ]Employee Name[ is approved according to the type and period below. Work handover must be completed before departure and the employee must return on time. Leave balance shall be updated upon approval",
          [("[DD/MM/YYYY] من تاريخ [Annual/Sick/Other] نوع الإجازة", "Leave Type From Date"), ("[____] عدد األيام [DD/MM/YYYY] إلى تاريخ", "To Date Number of Days"), ("[____] الرصيد بعد [____] الرصيد قبل", "Balance Before Balance After")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-028", "إشعار عودة من إجازة", "Return from Leave Notice", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-028", "إشعار عودة من إجازة", "Return from Leave Notice",
          "يفيد هذا الإشعار بأن الموظف اسم الموظف قد باشر العمل بعد الإجازة بتاريخ التاريخ في الساعة الوقت . تح Cدث حالته الوظيفية والحضور وفق سجل المباشرة.",
          "This notice confirms that ]Employee Name[ resumed work after leave on ]Date[ at ]Time[. Employment and attendance status shall be updated accordingly",
          [("[DD/MM/YYYY] الإجازة إلى [DD/MM/YYYY] الإجازة من", "Leave From Leave To"), ("[DD/MM/YYYY] تاريخ المباشرة الفعلي [DD/MM/YYYY] تاريخ المباشرة المتوقع", "Expected Return Actual Return"), ("[ ] مالحظات المسؤول [ ] التأخير إن وجد", "Delay, if any Manager Notes")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-029", "بيان رصيد الإجازات", "Leave Balance Statement", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-029", "بيان رصيد الإجازات", "Leave Balance Statement",
          "هذا البيان يوضح رصيد إجازات الموظف حتى تاريخ تاريخ االحتساب وفق السجلات المعتمدة في النظام. أي طلبات معلقة أو تعديالت قيد المراجعة تظهر بشكل منفصل.",
          "This statement shows the employee leave balance as of ]Calculation Date[ according to approved HRMS records. Pending requests or adjustments are shown separately",
          [("[____] /syaD استحقاق السنة [____] /syaD الرصيد المرحل يوم يوم", "Carried Forward Annual Entitlement"), ("[____] /syaD المعلق [____] /syaD المستخدم يوم يوم", "Used Pending"), ("[____] /syaD الرصيد المتاح [____ /+] التعديالت يوم -", "Adjustments Available Balance")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-030", "كشف حضور شهري", "Monthly Attendance Statement", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-030", "كشف حضور شهري", "Monthly Attendance Statement",
          "كشف حضور الموظف عن شهر الشهر السنة مستخرج من سجلات الحضور المعتمدة، ويشمل أيام العمل والغياب والتأخير والخروج المبكر والعمل الإضافي.",
          "Monthly attendance statement for ]Month/Year[ generated from approved attendance records, including workdays, absence, lateness, early departure, and overtime",
          [("[____] أيام الحضور [____] أيام العمل", "Working Days Present Days"), ("[____] مرات التأخير [____] أيام الغياب", "Absent Days Late Occurrences"), ("[____] الساعات الإضافية [____] الخروج المبكر", "Early Departures Overtime Hours"), ("[____] المخالفات المفتوحة [____] إجمالي ساعات العمل", "Total Worked Hours Open Exceptions")],
          [("System Generated", "إعداد النظام"), ("Supervisor Review", "مراجعة المشرف"), ("HR Approval", "اعتماد الموارد البشرية")], has_ack=False)),
    ("HRMS-PR-031", "تأكيد تعديل سجل حضور", "Attendance Record Adjustment Confirmation", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-031", "تأكيد تعديل سجل حضور", "Attendance Record Adjustment Confirmation",
          "تم تعديل سجل الحضور الخاص بالموظف اسم الموظف عن تاريخ التاريخ بناء على الطلب والمرجع الموضحين أدناه، مع االحتفاظ بالقيم قبل وبعد التعديل في سجل التدقيق.",
          "The attendance record for ]Employee Name[ on ]Date[ has been adjusted based on the approved request and reference below. Previous and new values are retained in the audit log",
          [("", "Checkin/Checkout/["), ("[ ] القيمة السابقة نوع التعديل", "Adjustment Type ]Absence Previous Value"), ("[ ] سبب التعديل [ ] القيمة الجديدة", "New Value Reason"), ("[ ] المرفق الداعم [ ] رقم الطلب", ". Request No Supporting Attachment")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=False)),
    ("HRMS-PR-032", "كشف راتب شهري مبسط", "Simplified Monthly Payroll Statement", "الحضور والإجازات والرواتب",
     _tpl("HRMS-PR-032", "كشف راتب شهري مبسط", "Simplified Monthly Payroll Statement",
          "هذا الكشف يوضح عناصر راتب الموظف عن شهر الشهر السنة كما تم اعتمادها في دورة الرواتب. لا يعد مستندا مصرفيا إال بعد توقيع وختم الجهة المخولة.",
          "This statement shows the approved payroll components for ]Month/Year[. It is not a bank document unless signed and stamped by the authorized party",
          [("[____] البدلات [____] الراتب الأساسي د.ك د.ك", "Basic Salary Allowances"), ("[____] المكافآت [____] العمل الإضافي د.ك د.ك", "Overtime Bonuses"), ("[____] السلف [____] الخصومات د.ك د.ك", "Deductions Advances"), ("[Bank/Cash] طريقة الدفع [____] صافي الراتب د.ك", "Net Salary Payment Method")],
          [("Prepared by Accounts", "إعداد المحاسبة"), ("HR Review", "مراجعة الموارد البشرية"), ("Manager Approval", "اعتماد المدير")], has_ack=False)),
    ("HRMS-PR-033", "إشعار نقص مستندات", "Missing Documents Notice", "المعاملات الحكومية والمستندات",
     _tpl("HRMS-PR-033", "إشعار نقص مستندات", "Missing Documents Notice",
          "نحيط الموظف اسم الموظف علما بأن ملفه معاملته رقم المرجع ينقصها المستندات الموضحة أدناه. يرجى رفع أو تسليم المستندات قبل الموعد لتجنب تأخير المعاملة أو توقفها.",
          ". ] [ is notified that file/transaction ]Reference[ is missing the documents listed below. Please upload or submit them by ]Deadline[ to avoid delay or suspension of the transaction Employee Name",
          [("[ ] المستندات الناقصة [ ] نوع المعاملة", "Transaction Type Missing Documents"), ("[HRMS/Physical] طريقة التسليم [DD/MM/YYYY] آخر موعد", "Deadline Submission Method"), ("[AwaitingDocuments] حالة المعاملة [ ] المسؤول", "Responsible Officer Transaction Status")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-034", "تفويض تجديد إقامة", "Residency Renewal Authorization", "المعاملات الحكومية والمستندات",
     _tpl("HRMS-PR-034", "تفويض تجديد إقامة", "Residency Renewal Authorization",
          "تفوض شركة اسم الشركة الجهة المندوب الموضح أدناه باستكمال إجراءات تجديد إقامة الموظف اسم الموظف ، وفق مدة الصلاحية والمستندات المعتمدة، مع تحديث النظام عند كل مرحلة من مراحل المعاملة.",
          "authorizes the party/delegate below to complete the residency renewal of ]Employee Name[ based on approved validity and documents, with HRMS status updated at each Company Name stage",
          [("", "Early days/Normal["), ("", "30-90"), ("[DD/MM/YYYY] انتهاء الإقامة نوع التجديد", "Renewal Type ]<= days Residency Expiry"), ("", "30"), ("[ ] رقم ملف الشركة [ ] مدة التجديد", "Renewal Period . Company File No"), ("", "Passport/Permit/Photo/["), ("المرفقات [ ] المندوب المكلف", "Assigned Delegate Attachments ]Other")],
          [("Legal Affairs", "الشؤون القانونية"), ("Company Manager", "مدير الشركة"), ("Delegate", "المندوب")], has_ack=False)),
    ("HRMS-PR-035", "تفويض تجديد إذن عمل", "Work Permit Renewal Authorization", "المعاملات الحكومية والمستندات",
     _tpl("HRMS-PR-035", "تفويض تجديد إذن عمل", "Work Permit Renewal Authorization",
          "تعتمد مباشرة إجراءات تجديد إذن العمل الخاص بالموظف اسم الموظف وفق الملف والترخيص المبينين أدناه، ويكلف المندوب برفع المستندات والنتيجة النهائية في النظام.",
          "The work permit renewal process for ]Employee Name[ is authorized under the company file and license below. The delegate shall upload supporting documents and final outcome to the HRMS",
          [("[DD/MM/YYYY] تاريخ االنتهاء [ ] رقم إذن العمل", ". Work Permit No Expiry Date"), ("[ ] الترخيص [ ] ملف الشركة", "Company File License"), ("[DD/MM/YYYY] موعد الإنجاز [ ] المندوب", "Delegate Target Completion"), ("", "| / | |")],
          [("Employee/Legal", "شؤون الموظفين القانونية"), ("Manager Approval", "اعتماد المدير"), ("Delegate Execution", "تنفيذ المندوب"), ("Affairs", "")], has_ack=False)),
    ("HRMS-PR-036", "إشعار تحديث البطاقة المدنية أو الجواز", "Civil ID / Passport Update Notice", "المعاملات الحكومية والمستندات",
     _tpl("HRMS-PR-036", "إشعار تحديث البطاقة المدنية أو الجواز", "Civil ID / Passport Update Notice",
          "يلزم تحديث بيانات البطاقة المدنية جواز السفر للموظف اسم الموظف بسبب انتهاء تغيير بيانات إصدار جديد . يرجى تقديم النسخة الجديدة قبل التاريخ وتحديث الملف الإلكتروني.",
          ". ] [ must update ]Civil ID/Passport[ details due to ]Expiry/Data Change/New Issue[. Please submit the new copy by ]Date[ and update the electronic employee file Employee Name",
          [("[ ] الرقم الحالي [CivilID/Passport] نوع المستند", "Document Type Current Number"), ("[Upload/SubmitOriginal] المطلوب [DD/MM/YYYY] تاريخ االنتهاء", "Expiry Date Required Action"), ("[Pending/Received] حالة االستالم [DD/MM/YYYY] آخر موعد", "Deadline Receipt Status")],
          [("Prepared By", "إعداد"), ("Reviewed By", "مراجعة"), ("Approved By", "اعتماد")], has_ack=True)),
    ("HRMS-PR-037", "تكليف مندوب بمعاملة حكومية", "Government Transaction Delegate Assignment", "المعاملات الحكومية والمستندات",
     _tpl("HRMS-PR-037", "تكليف مندوب بمعاملة حكومية", "Government Transaction Delegate Assignment",
          "يكلف المندوب اسم المندوب بتنفيذ المعاملة الحكومية الموضحة أدناه لصالح الشركة الموظف ، مع االلتزام بتحديث حالة المهمة، وإرفاق الإيصاالت والمستند النهائي، وإعادة أي عهد أو مستندات أصلية.",
          "is assigned to complete the government transaction below for ]Company/Employee[, update task status, attach receipts and final documents, and return any originals or Delegate Name assigned assets",
          [("[ ] الجهة الحكومية [ ] نوع المعاملة", "Transaction Type Government Entity"), ("[DD/MM/YYYY] الموعد النهائي [ ] رقم المرجع", ". Reference No Deadline"), ("[ ] النتيجة المطلوبة [ ] العهد المبالغ", "Assets / Amounts Required Outcome")],
          [("Task Creator", "إنشاء المهمة"), ("Delegate Acceptance", "استلام المندوب"), ("Closure Approval", "اعتماد الإغالق")], has_ack=True)),
    ("HRMS-PR-038", "التسوية النهائية ونهاية الخدمة", "Final Settlement & End of Service", "إنهاء الخدمة والتسليم",
     _tpl("HRMS-PR-038", "التسوية النهائية ونهاية الخدمة", "Final Settlement & End of Service",
          "يوضح هذا المستند التسوية النهائية للموظف اسم الموظف حتى آخر يوم عمل التاريخ . تم احتساب البنود وفق البيانات المعتمدة في النظام، على أن تخضع المبالغ للمراجعة النهائية والتوقيعات المخولة قبل الصرف.",
          "This document summarizes the final settlement of ]Employee Name[ through the last working day ]Date[. Amounts are calculated from approved HRMS data and remain subject to final review and authorized signatures before payment",
          [("[____] راتب مستحق [____] مكافأة نهاية الخدمة د.ك د.ك", "End of Service Benefit Outstanding Salary"), ("[____] مستحقات أخرى [____] بدل إجازات د.ك د.ك", "Leave Encashment Other Entitlements"), ("[____] سلف متبقية [____] خصومات عهد د.ك د.ك", "Deductions / Assets Outstanding Advances"), ("[____] الصافي النهائي [____] إجمالي المستحق د.ك د.ك", "Gross Payable Net Settlement")],
          [("Prepared by HR", "إعداد الموارد البشرية"), ("Accounts Review", "مراجعة المحاسبة"), ("Approval & Payment", "االعتماد والصرف")], has_ack=True)),
    ("HRMS-PR-039", "شهادة إخلاء طرف", "Clearance Certificate", "إنهاء الخدمة والتسليم",
     _tpl("HRMS-PR-039", "شهادة إخلاء طرف", "Clearance Certificate",
          "تفيد الإدارات الموضحة أدناه بإتمام الموظف اسم الموظف تسليم العهد والمستندات وإغالق االلتزامات المسجلة عليه، ويعتمد إخلاء الطرف النهائي بعد اكتمال جميع األقسام دون استثناء.",
          "The departments below confirm that ]Employee Name[ has returned assigned assets and documents and settled recorded obligations. Final clearance is approved only after all sections are completed",
          [("[Cleared/Pending] المحاسبة [Cleared/Pending] تقنية المعلومات", "IT Accounts"), ("[Cleared/Pending] الفرع الإدارة [Cleared/Pending] المخازن العهد", "Assets / Stores Branch / Department"), ("[Cleared/Pending] الموارد البشرية [Cleared/Pending] الشؤون القانونية", "Legal Affairs HR")],
          [("Department Officer", "مسؤول القسم"), ("HR Review", "مراجعة الموارد البشرية"), ("Final Clearance", "اعتماد الإخلاء")], has_ack=True)),
    ("HRMS-PR-040", "محضر تسليم عهدة", "Asset Handover Record", "إنهاء الخدمة والتسليم",
     _tpl("HRMS-PR-040", "محضر تسليم عهدة", "Asset Handover Record",
          "تم في التاريخ الموضح تسليم استلام العهد المبينة أدناه بين الطرفين، بعد معاينتها وإثبات حالتها. يتحمل المستلم مسؤولية المحافظة عليها واستخدامها في أغراض العمل وإعادتها عند الطلب.",
          "On the date shown, the assets below were handed over/received between the parties after inspection and condition recording. The recipient is responsible for proper business use, safekeeping, and return upon request",
          [("[ ] الرقم التسلسلي [Laptop/Phone/Keys/Other] نوع العهدة", "Asset Type . Serial No"), ("[ ] الملحقات [New/Good/Damaged] الحالة عند التسليم", "Condition Accessories"), ("[ ] إلى الموظف [ ] من الموظف", "From Employee To Employee")],
          [("Handed Over By", "المسلم"), ("Received By", "المستلم"), ("Asset Controller", "مسؤول العهد")], has_ack=True)),
    ("HRMS-PR-041", "محضر استلام وتسليم مستندات", "Document Receipt & Handover Record", "إنهاء الخدمة والتسليم",
     _tpl("HRMS-PR-041", "محضر استلام وتسليم مستندات", "Document Receipt & Handover Record",
          "يثبت هذا المحضر استلام تسليم المستندات األصلية أو النسخ الموضحة أدناه. لا يجوز استخدام المستندات إال للغرض المحدد، ويجب إعادتها أو حفظها وفق سياسة إدارة الوثائق.",
          "This record confirms receipt/handover of the original documents or copies listed below. Documents may only be used for the stated purpose and must be returned or stored according to document management policy",
          [("", "Passport/CivilID/Contract/["), ("[ ] الرقم نوع المستند", "Document Type ]Other . Document No"), ("[ ] الغرض [ ] أصل أم نسخة", "Original / Copy Purpose"), ("[DD/MM/YYYY] موعد الإعادة [DD/MM/YYYY] تاريخ االستالم", "Receipt Date Return Date")],
          [("Handed Over By", "المسلم"), ("Received By", "المستلم"), ("Witness / Reviewer", "الشاهد / المراجع")], has_ack=True)),
    ("HRMS-PR-042", "سجل اعتماد التوقيع الإلكتروني", "Electronic Signature Approval Record", "إنهاء الخدمة والتسليم",
     _tpl("HRMS-PR-042", "سجل اعتماد التوقيع الإلكتروني", "Electronic Signature Approval Record",
          "يوثق هذا السجل اعتماد المستند إلكترونيا من أصحاب الصلاحية الموضحين أدناه. يرتبط كل اعتماد بهوية المستخدم والتاريخ والوقت وعنوان الجهاز الجلسة ورمز التحقق، وال يعتد بأي تعديل الحق دون إنشاء إصدار جديد.",
          "This record documents electronic approval by the authorized users below. Each approval is linked to user identity, date/time, session/device reference, and verification code. Subsequent changes require a new version",
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
