# -*- coding: utf-8 -*-
"""كتالوج قوالب الإشعارات (FIX-004) — 74 قالبًا مسمّى تغطي كل أحداث دورة حياة النظام
مع فئة (category)، نوع الحدث (event_type يطابق Task.type)، القناة الافتراضية،
ومهلة SLA بالساعات (للتصعيد إن لم تُعالَج المهمة). body_text يدعم {{placeholders}}.
"""

CAT_ATTENDANCE = "الحضور والإجازات"
CAT_RESIDENCY = "الإقامة والمعاملات الحكومية"
CAT_FINANCE = "الرواتب والمالية"
CAT_GRIEVANCE = "الشكاوى والتظلمات"
CAT_APPROVALS = "الموافقات وسير العمل"
CAT_DOCS = "المستندات والطباعة والأرشفة"
CAT_SECURITY = "الأمان والتدقيق"
CAT_CAREER = "التطوير الوظيفي"
CAT_SYSTEM = "النظام والتذكيرات"
CAT_GENERAL = "عام"


def _n(code, name, category, event_type, channel, sla, body):
    return {"code": code, "name": name, "category": category, "event_type": event_type,
            "channel_default": channel, "sla_hours": sla, "body_text": body}


DEFAULT_NOTIFICATION_TEMPLATES = [
    # الحضور والإجازات (10)
    _n("NTF-001", "طلب إجازة بانتظار اعتمادك", CAT_ATTENDANCE, "request_stage", "in_app", 24,
      "بانتظار موافقتك على طلب إجازة {{employee_name}} من {{start_date}} إلى {{end_date}}."),
    _n("NTF-002", "اعتماد إجازة الموظف", CAT_ATTENDANCE, "request_update", "in_app", None,
      "تم اعتماد طلب إجازتك من {{start_date}} إلى {{end_date}}."),
    _n("NTF-003", "طلب إذن أثناء الدوام", CAT_ATTENDANCE, "request_stage", "in_app", 12,
      "بانتظار موافقتك على إذن أثناء الدوام لـ{{employee_name}}."),
    _n("NTF-004", "طلب مغادرة مبكرة", CAT_ATTENDANCE, "request_stage", "in_app", 12,
      "طلب مغادرة مبكرة من {{employee_name}} بتاريخ {{date}}."),
    _n("NTF-005", "تبرير تأخير مُقدَّم", CAT_ATTENDANCE, "request_stage", "in_app", 24,
      "قدّم {{employee_name}} تبريرًا لتأخيره بتاريخ {{date}}."),
    _n("NTF-006", "طلب تصحيح سجل حضور", CAT_ATTENDANCE, "request_stage", "in_app", 48,
      "طلب تصحيح سجل حضور من {{employee_name}} بتاريخ {{date}}."),
    _n("NTF-007", "طلب تغيير وردية", CAT_ATTENDANCE, "request_stage", "in_app", 48,
      "طلب تغيير وردية من {{employee_name}} إلى {{new_shift}}."),
    _n("NTF-008", "طلب عمل إضافي", CAT_ATTENDANCE, "request_stage", "in_app", 24,
      "طلب اعتماد عمل إضافي من {{employee_name}}: {{ot_hours}} ساعة."),
    _n("NTF-009", "تذكير بموعد انتهاء الإجازة", CAT_ATTENDANCE, "doc_expiring", "in_app", None,
      "إجازتك تنتهي بتاريخ {{end_date}} — يُتوقَّع عودتك للعمل."),
    _n("NTF-010", "غياب غير مبرَّر", CAT_ATTENDANCE, "request_update", "in_app", 24,
      "سُجِّل غياب غير مبرَّر للموظف {{employee_name}} بتاريخ {{date}}."),

    # الإقامة والمعاملات الحكومية (10)
    _n("NTF-011", "تجديد الإقامة قارب على الانتهاء", CAT_RESIDENCY, "renew_residency", "in_app", None,
      "إقامة {{employee_name}} تنتهي خلال {{days_left}} يومًا ({{expiry_date}})."),
    _n("NTF-012", "تجديد إذن العمل قارب على الانتهاء", CAT_RESIDENCY, "renew_work_permit", "in_app", None,
      "إذن عمل {{employee_name}} ينتهي خلال {{days_left}} يومًا."),
    _n("NTF-013", "ترخيص قارب على الانتهاء", CAT_RESIDENCY, "license_expiring", "in_app", None,
      "الترخيص {{license_name}} ينتهي خلال {{days_left}} يومًا."),
    _n("NTF-014", "تجاوز سعة الترخيص", CAT_RESIDENCY, "capacity_exceeded", "in_app", 24,
      "عدد العمالة على ترخيص {{license_name}} يتجاوز المسموح."),
    _n("NTF-015", "بانتظار رفع عقود التجديد", CAT_RESIDENCY, "renew_residency", "in_app", 48,
      "حُوّلت معاملة تجديد إقامة {{employee_name}} إليك — ارفع العقود."),
    _n("NTF-016", "بانتظار توقيعك على عقود التجديد", CAT_RESIDENCY, "doc_expiring", "in_app", 72,
      "حمّل عقدي التجديد ووقّعهما وارفع النسختين الموقّعتين."),
    _n("NTF-017", "تم تجديد الإقامة — ارفع البطاقة المدنية", CAT_RESIDENCY, "doc_expiring", "in_app", 168,
      "استخرج البطاقة المدنية الجديدة وارفع صورة منها."),
    _n("NTF-018", "إذن مغادرة البلاد جاهز", CAT_RESIDENCY, "exit_permit", "in_app", None,
      "تم إنهاء إجراءات إذن مغادرة {{employee_name}}."),
    _n("NTF-019", "معاملة حكومية جديدة", CAT_RESIDENCY, "request_stage", "in_app", 24,
      "فُتحت معاملة حكومية جديدة: {{transaction_type}} لـ{{employee_name}}."),
    _n("NTF-020", "تحديث بيانات جواز/بطاقة مدنية", CAT_RESIDENCY, "request_update", "in_app", None,
      "تم تحديث بيانات {{document_type}} للموظف {{employee_name}}."),

    # الرواتب والمالية (8)
    _n("NTF-021", "مسيّر الرواتب جاهز للمراجعة", CAT_FINANCE, "payroll_ready", "in_app", 48,
      "مسيّر رواتب {{period}} جاهز للمراجعة والاعتماد."),
    _n("NTF-022", "قسيمة راتبك جاهزة", CAT_FINANCE, "payroll_ready", "in_app", None,
      "قسيمة راتب {{period}} متاحة للعرض."),
    _n("NTF-023", "طلب سلفة/قرض بانتظار الاعتماد", CAT_FINANCE, "request_stage", "in_app", 48,
      "طلب سلفة/قرض من {{employee_name}} بمبلغ {{amount}}."),
    _n("NTF-024", "طلب استرداد مصروفات", CAT_FINANCE, "request_stage", "in_app", 48,
      "طلب استرداد مصروفات من {{employee_name}} بمبلغ {{amount}}."),
    _n("NTF-025", "اعتراض على الراتب", CAT_FINANCE, "request_stage", "in_app", 72,
      "اعتراض من {{employee_name}} على راتب فترة {{period}}."),
    _n("NTF-026", "اعتراض على خصم", CAT_FINANCE, "request_stage", "in_app", 72,
      "اعتراض من {{employee_name}} على خصم بمبلغ {{amount}}."),
    _n("NTF-027", "تسوية نهاية الخدمة جاهزة", CAT_FINANCE, "eos_ready", "in_app", 72,
      "تسوية نهاية خدمة {{employee_name}} جاهزة للاعتماد: {{eos_amount}} د.ك."),
    _n("NTF-028", "تم صرف بدل/ميزة", CAT_FINANCE, "request_update", "in_app", None,
      "تمت الموافقة على بدل/ميزة لـ{{employee_name}}: {{amount}}."),

    # الشكاوى والتظلمات (4)
    _n("NTF-029", "شكوى/تظلم جديد", CAT_GRIEVANCE, "grievance_filed", "in_app", 24,
      "قُدِّمت شكوى/تظلم جديد يتطلب مراجعة سرية."),
    _n("NTF-030", "تم استلام شكواك", CAT_GRIEVANCE, "grievance_filed", "in_app", None,
      "تم استلام شكواك وستُعالَج بسرية تامة."),
    _n("NTF-031", "تحديث على الشكوى", CAT_GRIEVANCE, "grievance_update", "in_app", None,
      "طرأ تحديث على الشكوى المقدَّمة."),
    _n("NTF-032", "اعتراض على مخالفة", CAT_GRIEVANCE, "request_stage", "in_app", 48,
      "اعتراض من {{employee_name}} على مخالفة مسجَّلة."),

    # الموافقات وسير العمل (10)
    _n("NTF-033", "بانتظار موافقتك", CAT_APPROVALS, "request_stage", "in_app", 24,
      "طلب {{request_type}} من {{employee_name}} بانتظار موافقتك."),
    _n("NTF-034", "تحديث على طلبك", CAT_APPROVALS, "request_update", "in_app", None,
      "وصل طلبك ({{request_type}}) إلى مرحلة: {{stage_label}}."),
    _n("NTF-035", "تم رفض طلبك", CAT_APPROVALS, "request_update", "in_app", None,
      "تم رفض طلبك ({{request_type}}). السبب: {{reason}}."),
    _n("NTF-036", "تم إلغاء طلبك", CAT_APPROVALS, "request_update", "in_app", None,
      "تم إلغاء طلبك ({{request_type}}) من قبل الإدارة."),
    _n("NTF-037", "اكتمل طلبك", CAT_APPROVALS, "request_update", "in_app", None,
      "تم إنهاء جميع مراحل طلبك ({{request_type}}) بنجاح."),
    _n("NTF-038", "مطلوب حضورك للتوقيع", CAT_APPROVALS, "appointment", "whatsapp", 72,
      "برجاء مراجعة شؤون الموظفين لإتمام طلبك بالتوقيع في {{scheduled_at}}."),
    _n("NTF-039", "جاهز للاستلام", CAT_APPROVALS, "pickup_ready", "in_app", 48,
      "طلبك ({{request_type}}) جاهز للاستلام من شؤون الموظفين."),
    _n("NTF-040", "طلب نقل داخلي", CAT_APPROVALS, "request_stage", "in_app", 48,
      "طلب نقل داخلي لـ{{employee_name}} إلى {{to_branch}}."),
    _n("NTF-041", "طلب ترقية أو تعديل راتب", CAT_APPROVALS, "request_stage", "in_app", 72,
      "طلب ترقية/تعديل راتب لـ{{employee_name}}."),
    _n("NTF-042", "طلب استقالة مُقدَّم", CAT_APPROVALS, "request_stage", "in_app", 24,
      "قدّم {{employee_name}} طلب استقالة بتاريخ خروج مقترح {{last_working_day}}."),

    # المستندات والطباعة والأرشفة (8)
    _n("NTF-043", "مستند جاهز للطباعة", CAT_DOCS, "print_ready", "in_app", None,
      "المستند ({{document_name}}) جاهز للطباعة والحفظ."),
    _n("NTF-044", "تم تسجيل الطباعة", CAT_DOCS, "print_done", "in_app", None,
      "تم تسجيل طباعة المستند ({{document_name}}) بواسطة {{actor_name}}."),
    _n("NTF-045", "تم أرشفة المستند", CAT_DOCS, "file_done", "in_app", None,
      "تم أرشفة المستند ({{document_name}}) في ملف الموظف."),
    _n("NTF-046", "نقص في مستندات الطلب", CAT_DOCS, "doc_missing", "in_app", 72,
      "يوجد نقص في مستندات الطلب رقم {{request_no}} — يرجى الاستكمال."),
    _n("NTF-047", "رفع مستند جديد", CAT_DOCS, "doc_uploaded", "in_app", None,
      "تم رفع مستند جديد لملف {{employee_name}}: {{document_name}}."),
    _n("NTF-048", "طلب نسخة من ملف/مستند", CAT_DOCS, "request_stage", "in_app", 48,
      "طلب نسخة من ({{document_name}}) لـ{{employee_name}}."),
    _n("NTF-049", "تحديث بيانات موظف", CAT_DOCS, "data_updated", "in_app", None,
      "تم تحديث بيانات {{employee_name}}: {{field}}."),
    _n("NTF-050", "طلب مراجعة قانونية", CAT_DOCS, "request_stage", "in_app", 72,
      "طلب مراجعة قانونية بخصوص: {{subject}}."),

    # الأمان والتدقيق (6)
    _n("NTF-051", "محاولة دخول غير مصرَّح بها", CAT_SECURITY, "security_alert", "in_app", 4,
      "رُصدت محاولة دخول فاشلة متكررة للحساب {{civil_id}}."),
    _n("NTF-052", "تم قفل الحساب", CAT_SECURITY, "security_alert", "in_app", None,
      "تم قفل حساب {{civil_id}} بعد محاولات دخول فاشلة متكررة."),
    _n("NTF-053", "وصول خارج النطاق المسموح", CAT_SECURITY, "security_alert", "in_app", 24,
      "حاول {{user_name}} الوصول لبيانات خارج نطاقه المصرَّح."),
    _n("NTF-054", "بدء انتحال هوية", CAT_SECURITY, "security_alert", "in_app", None,
      "بدأ {{actor_name}} تصفّح النظام كـ{{target_name}} (انتحال هوية مُراقَب)."),
    _n("NTF-055", "تعديل صلاحيات مستخدم", CAT_SECURITY, "security_alert", "in_app", None,
      "تم تعديل صلاحيات المستخدم {{user_name}} بواسطة {{actor_name}}."),
    _n("NTF-056", "تصدير تقرير حساس", CAT_SECURITY, "security_alert", "in_app", None,
      "تم تصدير تقرير حساس ({{report_name}}) بواسطة {{actor_name}}. السبب: {{reason}}."),

    # التطوير الوظيفي (5)
    _n("NTF-057", "طلب تدريب", CAT_CAREER, "request_stage", "in_app", 72,
      "طلب حضور تدريب من {{employee_name}}: {{training_name}}."),
    _n("NTF-058", "تم تعيينك لتدريب", CAT_CAREER, "training_assigned", "in_app", None,
      "تم تكليفك بحضور تدريب: {{training_name}} بتاريخ {{date}}."),
    _n("NTF-059", "قرار ترقية معتمَد", CAT_CAREER, "promotion_decided", "in_app", None,
      "تمت ترقيتك إلى {{new_title}} اعتبارًا من {{effective_date}}."),
    _n("NTF-060", "قرار نقل معتمَد", CAT_CAREER, "transfer_decided", "in_app", None,
      "تم اعتماد نقلك إلى {{to_branch}} اعتبارًا من {{effective_date}}."),
    _n("NTF-061", "انتهاء فترة التجربة", CAT_CAREER, "probation_ending", "in_app", 168,
      "فترة تجربة {{employee_name}} تنتهي بتاريخ {{date}} — يلزم قرار."),

    # النظام والتذكيرات (8)
    _n("NTF-062", "مهمة جديدة بانتظارك", CAT_SYSTEM, "task_assigned", "in_app", None,
      "لديك مهمة جديدة: {{task_title}}."),
    _n("NTF-063", "تذكير بمهمة متأخرة", CAT_SYSTEM, "task_overdue", "in_app", None,
      "المهمة ({{task_title}}) تجاوزت المهلة المحددة."),
    _n("NTF-064", "إشعار نقص مستندات إدارية", CAT_SYSTEM, "doc_missing", "in_app", 72,
      "نقص مستندات إدارية لملف {{employee_name}}."),
    _n("NTF-065", "تكليف مندوب بمهمة", CAT_SYSTEM, "delegate_task", "in_app", 48,
      "تم تكليفك بمهمة: {{task}} مرتبطة بالطلب رقم {{request_no}}."),
    _n("NTF-066", "تكليف مؤقت بموقع أو فرع", CAT_SYSTEM, "request_stage", "in_app", 48,
      "تكليف مؤقت لـ{{employee_name}} بموقع {{location}}."),
    _n("NTF-067", "مهمة عمل خارجية", CAT_SYSTEM, "request_stage", "in_app", 48,
      "طلب مهمة عمل خارجية من {{employee_name}}: {{task}}."),
    _n("NTF-068", "صيانة/تحديث النظام", CAT_SYSTEM, "system_notice", "in_app", None,
      "سيخضع النظام لصيانة بتاريخ {{date}} من {{start_time}} إلى {{end_time}}."),
    _n("NTF-069", "تذكير بتغيير كلمة المرور", CAT_SYSTEM, "system_notice", "in_app", None,
      "يُرجى تحديث كلمة مرورك للحساب {{civil_id}}."),

    # عام (5)
    _n("NTF-070", "طلب عام أو اقتراح", CAT_GENERAL, "request_stage", "in_app", 72,
      "طلب عام/اقتراح من {{employee_name}}: {{subject}}."),
    _n("NTF-071", "إنذار وظيفي صادر", CAT_GENERAL, "warning_issued", "in_app", None,
      "صدر لك إنذار وظيفي بخصوص: {{violation}}."),
    _n("NTF-072", "تسجيل مخالفة وظيفية", CAT_GENERAL, "violation_logged", "in_app", None,
      "سُجِّلت عليك مخالفة وظيفية بتاريخ {{date}}: {{violation}}."),
    _n("NTF-073", "إصدار خصم", CAT_GENERAL, "deduction_issued", "in_app", None,
      "صدر خصم بمبلغ {{amount}} — السبب: {{reason}}."),
    _n("NTF-074", "إعلان عام للشركة", CAT_GENERAL, "announcement", "in_app", None,
      "{{announcement_text}}"),
]
