# -*- coding: utf-8 -*-
"""نظام الصلاحيات (Permission-based) — كل صلاحية تمثل فعلًا محددًا (Action).

الأدوار:
- super_admin    : الإدارة العليا — يتجاوز كل الصلاحيات ويشرف على كل الشركات.
- company_owner  : صاحب الشركات — عرض + موافقات عبر كل شركاته.
- company_manager: مدير شركة — صلاحيات واسعة داخل شركته.
- branch_supervisor: مسؤول فرع — أول معتمِد لطلبات موظفي فرعه.
- hr             : موارد بشرية — الاعتماد النهائي والطباعة والأرشفة.
- delegate       : المندوب / الشؤون القانونية — تجديدات وإذن المغادرة.
- employee       : خدمة ذاتية — لا يملك إلا ما يُسنَد إليه.
"""

# كتالوج الصلاحيات (الفعل: الوصف العربي)
PERMISSIONS: dict[str, str] = {
    "view_employee": "عرض الموظفين",
    "create_employee": "إضافة موظف",
    "edit_employee": "تعديل موظف",
    "delete_employee": "حذف موظف",
    "manage_branches": "إدارة الفروع والمواقع",
    "manage_departments": "إدارة الإدارات/الأقسام",
    "manage_licenses": "إدارة التراخيص",
    "manage_permits": "إدارة الإقامات وأذونات العمل",
    "upload_documents": "رفع المستندات",
    "view_documents": "عرض وتنزيل المستندات",
    "manage_deductions": "إدارة الخصومات",
    "manage_leaves": "إدارة الإجازات",
    "manage_attendance": "إدارة الحضور والانصراف",
    "view_attendance": "عرض الحضور",
    "record_attendance": "تسجيل الحضور (خدمة ذاتية)",
    "run_payroll": "تشغيل مسيّر الرواتب",
    "view_payroll": "عرض الرواتب",
    "calculate_eos": "حساب مكافأة نهاية الخدمة",
    "view_reports": "عرض التقارير",
    "export_reports": "تصدير التقارير",
    "view_audit": "عرض سجل التدقيق",
    "terminate_employee": "إنهاء خدمة موظف",
    "approve_termination": "اعتماد إنهاء خدمة موظف (سلطة مستقلة عن التحضير)",
    "view_tasks": "عرض المهام والتنبيهات",
    "manage_tasks": "إدارة المهام",
    "submit_request": "تقديم الطلبات (خدمة ذاتية)",
    # V2.2 §4.5 (AP-01) — مهجورة: صلاحية اعتماد واحدة لكل الأنواع تعني أن من
    # يعتمد إجازة يعتمد خصًما وتظلًما وإنهاء خدمة. تبقى مقبولة للتوافق مع منح
    # صريحة قائمة، ولا تُمنح لدور جديد.
    "approve_request": "اعتماد الطلبات (عام — مهجور)",
    # الصلاحيات المفصولة: مجال قرار واحد لكل صلاحية. المصفوفة أدناه مشتقّة من
    # approval_chain_json الفعلية لا مخمَّنة، فلا يفقد دور شيًئا كان يعتمده.
    "approve_leave": "اعتماد الحضور والإجازات",
    "approve_certificate": "اعتماد الشهادات والخطابات",
    "approve_finance": "اعتماد الطلبات المالية",
    "approve_government": "اعتماد المعاملات الحكومية والإقامات",
    "approve_personnel": "اعتماد بيانات الموظف والتطوير الوظيفي",
    "approve_grievance": "اعتماد الشكاوى والتظلمات",
    "approve_exit": "اعتماد العقود وإنهاء الخدمة",
    "approve_general": "اعتماد الطلبات العامة والنماذج الإدارية",
    # V2.2 §13.3 (AC-03) — إتمام خطوة تحقّق لا قرار. من يتحقّق من صحة البيانات
    # ليس من يقرّر صرف المال؛ الخلط بينهما هو ما يجعل الفصل بين الواجبات ورًقا.
    "complete_validation": "إتمام خطوات التحقق",
    "manage_request_types": "إدارة أنواع الطلبات وسلاسل الموافقات",
    "manage_templates": "إدارة الصيغ والنماذج وطباعتها",
    "process_delegate_tasks": "إجراءات المندوب (تجديد/إذن مغادرة)",
    "manage_users": "إدارة المستخدمين والصلاحيات",
    "manage_company": "إدارة بيانات الشركة",
    "manage_companies": "إدارة جميع الشركات (إدارة عليا)",
    "transfer_employee": "نقل موظف بين الشركات",
    "view_actual_salary": "عرض الراتب الفعلي",
    "edit_actual_salary": "تعديل الراتب الفعلي",
    # QA-01 — تدخّل إداري لاعتماد مرحلة ليست لصاحبها.
    # كان تجاوًزا ضمنًيا داخل can_decide لكل مدير شركة ومالك، فصار المدير معتمِد
    # كل المراحل وامتلأ صندوقه بكل الطلبات — وهو نفسه سبب عدم وصول الطلب
    # لمسؤول الفرع (QA-02). صار صلاحية مسمّاة لا تُمنح لأي دور افتراضًا، ويُسجَّل
    # كل استخدام لها في التدقيق كما تشترط SKILL-3.
    "override_approval": "تجاوز إداري: اعتماد مرحلة ليست لصاحبها (يُسجَّل)"}

# قوالب صلاحيات جاهزة
PERMISSION_TEMPLATES: dict[str, dict] = {
    "hr_officer": {
        "label": "موظف موارد بشرية",
        "perms": ["view_employee", "create_employee", "edit_employee", "manage_permits",
                  "manage_leaves", "upload_documents", "view_documents", "view_attendance",
                  "approve_request", "view_tasks", "view_reports", "submit_request"]},
    "branch_supervisor": {
        "label": "مسؤول فرع",
        "perms": ["view_employee", "view_attendance", "approve_request", "view_tasks",
                  "view_reports", "submit_request"]},
    "delegate": {
        "label": "مندوب / شؤون قانونية",
        "perms": ["view_employee", "view_documents", "upload_documents", "manage_permits",
                  "process_delegate_tasks", "view_tasks", "submit_request"]},
    "viewer": {
        "label": "مطّلع فقط",
        "perms": ["view_employee", "view_reports", "view_tasks", "view_documents"]},
    "payroll": {
        "label": "مسؤول رواتب",
        "perms": ["view_employee", "manage_deductions", "manage_attendance", "view_attendance",
                  "run_payroll", "view_payroll", "calculate_eos", "view_reports", "export_reports"]},
    "company_admin": {
        "label": "مدير شركة (كل الصلاحيات)",
        "perms": [p for p in PERMISSIONS if p != "manage_companies"]}}

# صلاحيات افتراضية لكل دور (يُمنحها النظام تلقائيًا دون الحاجة لإسناد فردي)
_ALL = set(PERMISSIONS.keys())
_COMPANY_ALL = {p for p in PERMISSIONS if p != "manage_companies"}

ROLE_DEFAULT_PERMS: dict[str, set[str]] = {
    "super_admin": _ALL | {"manage_companies"},
    # المالك: دور رقابي للاطلاع فقط (متابعة الشركات/الفروع/الأداء/التقارير) — لا أعمال تشغيلية.
    # يشمل الاطلاع على سجل التدقيق والرواتب (رقابة/حوكمة) دون أي صلاحية تنفيذ (FIX-010).
    "company_owner": {"view_employee", "view_reports", "export_reports", "view_tasks",
                      "view_actual_salary", "view_audit", "view_payroll", "view_documents",
                      "view_attendance"},
    # مدير الشركة: التشغيل اليومي فقط — موظفون/فروع/إدارات/إجازات/طلبات/تقارير/مستخدمو شركته.
    # لا رواتب/خصومات (المحاسب)، لا EOS/إنهاء خدمة (HR)، لا إقامات/تراخيص (PRO)،
    # لا إعدادات نظام/شركات/قوالب/تدقيق/نقل بين الشركات (الإدارة العليا).
    # submit_request: لنفسه فقط. كان يبدأ نيابًة عن الموظف طلبات إدارية (ترقية،
    # نقل، تجديد عقد...) حتى قُصر التقديم نيابًة على HR وحده — انظر ON_BEHALF_ROLES.
    # تلك الطلبات صار يفتحها HR.
    # ATT-03: record_attendance نُزعت بقرار العميل — لا شاشة حضور للمدير.
    # كانت تُمنح له ليبصم لنفسه (P0-#4)، لكنه يعتمد الطلبات ويمنح الصلاحيات،
    # فبصمه لنفسه يخلط الرقابة بالخضوع لها. view_attendance تبقى للمتابعة.
    "company_manager": {
        "complete_validation",
        "approve_certificate",
        "approve_exit",
        "approve_finance",
        "approve_general",
        "approve_government",
        "approve_grievance",
        "approve_leave",
        "approve_personnel","view_employee", "create_employee", "edit_employee", "delete_employee",
                        "view_documents", "upload_documents", "manage_leaves", "view_attendance",
                        "manage_branches", "manage_departments",
                        "view_reports", "export_reports", "view_tasks", "manage_tasks",
                        # QA §6: مرحلة "Authorized Approval" في إنهاء الخدمة — جهة ثالثة
                        # غير من حسب التسوية (المالية) وغير من فتح الحالة (HR).
                        "approve_termination",
                        # المدير يعتمد الطلبات ولا يرفعها — قرار تنظيمي:
                        # سلطة الاعتماد وسلطة الطلب لا تجتمعان في يد واحدة.
                        # طلباته الشخصية تُرفع نيابًة عنه من الشؤون القانونية.
                        "manage_users"},
    # محاسب الشركة: الرواتب والخصومات + الراتب الفعلي (مالي)، وهو أيًضا موظف له ملف
    # وحضور خاص به (submit_request/record_attendance) مثل أي موظف آخر بالشركة.
    # approve_request إلزامي (P0-01): المحاسب معتمِد فعلي في مراحل كثيرة (السلف/القروض
    # والاعتماد المالي في REQOT/REQBANK/REQADV/REQEXP/REQPAY/REQDED/ADMDED/REQCLR/REQEOS)،
    # وبدونها كان /decide و/received يرفضانه بـ403 فتتوقف الطلبات المالية عنده للأبد رغم
    # أن can_decide يتحقق أصًلا من كونه معتمِد المرحلة الفعلي.
    "accountant": {
        "complete_validation",
        "approve_exit",
        "approve_finance",
        "approve_general",
        "approve_leave",
        "approve_personnel","view_employee", "view_payroll", "run_payroll", "manage_deductions",
                   "view_actual_salary", "edit_actual_salary",
                   "view_reports", "export_reports", "view_tasks",
                   "submit_request", "record_attendance",
                   # PILOT-P0-8: المحاسب هو المُعتمِد المالي لإنهاء الخدمة (فصل السلطات عن HR)
                   "approve_termination",
                   # QA §6: مرحلة "Finance Calculation" في دورة إنهاء الخدمة — المالية
                   # تحسب التسوية من سجل الموظف، وHR يفتح الحالة، وجهة ثالثة تعتمد.
                   "calculate_eos",
                   # PILOT-P0-11a: المحاسب يحتاج مراجعة الحضور قبل قفل الرواتب (منع تشغيل رواتب
                   # على بيانات ناقصة). لا يحق له تعديل السجلات (manage_attendance يبقى مع HR).
                   "view_attendance"},
    # مسؤول الفرع: إدارة فرعه فقط — متابعة موظفيه، مراجعة الطلبات، رفع التقارير.
    # النطاق مقيّد بفروعه (resolve_scope=multi) فلا يرى بيانات الفروع الأخرى.
    # submit_request: لنفسه فقط. كان يبدأ طلبات تشغيلية عن موظفيه (تغيير وردية،
    # مهمة خارجية...) قبل قصر التقديم نيابًة على HR — انظر ON_BEHALF_ROLES.
    # P0-#4: أضفنا record_attendance — مسؤول الفرع موظف أيضًا (يبصم لنفسه).
    "branch_supervisor": {
        "complete_validation",
        "approve_finance",
        "approve_general",
        "approve_government",
        "approve_leave",
        "approve_personnel","view_employee", "view_attendance",
                          "record_attendance",  # للـMy Attendance الشخصية
                          "view_tasks", "view_reports", "export_reports", "submit_request"},
    # الشؤون القانونية/HR: مسؤول عن الموظفين فقط (لا حكومة/إقامات/تراخيص).
    # دورة حياة الموظف: إضافة/تعديل/عقود (مستندات)/إجازات/إنذارات/خصومات/EOS + خطابات الإنذار (قوالب).
    # approve_request مطلوب لأن HR مرحلة في سلسلة طلبات الموظفين (مراجعة/توقيع/استلام).
    # submit_request إلزامي (P0-05): HR هو من يبدأ فعليًا معظم الإجراءات الداخلية (REQEOS،
    # REQCLR، ADMEMP/ADMACTUAL/ADMDED/ADMVIO/ADMWARN/ADMTASK/ADMMISS/ADMSIGN) نيابًة عن
    # الموظف؛ بدونها لم يكن أي منها قابًلا للإنشاء أصًلا (لا HR ولا company_manager كان
    # يملك submit_request)، وهو السبب الحقيقي وراء توقّف REQEOS/REQCLR (P0-05).
    "hr": {
        "approve_certificate",
        "approve_exit",
        # AC-03 — لا approve_finance: HR يتحقّق ولا يقرّر صرف المال.
        # خطوته في "اعتراض على خصم" تحقّق تعاقدي، وتُنجَز بـcomplete_validation.
        "complete_validation",
        "approve_general",
        "approve_government",
        "approve_grievance",
        "approve_leave",
        "approve_personnel","view_employee", "create_employee", "edit_employee",
           "view_documents", "upload_documents",
           "manage_leaves", "manage_deductions", "calculate_eos", "terminate_employee",
           "manage_templates", "view_tasks",
           "view_attendance", "manage_attendance",  # تصحيح واعتماد سجلات الحضور (FIX-015)
           # لا record_attendance: HR معفي من البصم بقرار العميل. كانت تُمنح له
           # ليبصم لنفسه (P0-#4)، لكنه الجهة التي تصحّح سجلات الحضور وتعتمدها —
           # فبصمه لنفسه يجمع الإثبات والاعتماد في يد واحدة. يبقى معه
           # view_attendance وmanage_attendance لأداء دوره الرقابي.
           "submit_request"},
    # PRO / المندوب: كل المعاملات الحكومية فقط (إقامات/أذونات/تراخيص/جهات/تجديدات/ملاحظات/مواعيد).
    # لا رواتب/عقود/EOS/إجازات/خصومات/تقارير HR. submit_request (P0-05): يبدأ معاملات
    # حكومية (ADMLIC، REQWP...) نيابًة عن الموظف — ولهذا هو في ON_BEHALF_ROLES مع HR:
    # تجديد الإقامة وإذن العمل يفتحهما المندوب باسم الموظف بحكم طبيعة عمله.
    # R2-B: create_employee أُلغي — PRO لا يُنشئ موظفين (HR فقط). صلاحية إنشاء تُسبب
    # ظهور "موظف جديد" في القائمة الجانبية وتفتح فورمًا يعرض حقول (راتب/تاريخ تعيين/عقد)
    # ممنوعة على المندوب أصلاً في الرؤية.
    "delegate": {
        "approve_general",
        "approve_government",
        "approve_leave","view_employee", "view_documents", "upload_documents",
                 "manage_permits", "manage_licenses", "process_delegate_tasks", "submit_request",
                 "view_tasks", "manage_tasks"},
    # موظف إداري مرن: بلا صلاحيات افتراضية — تُمنح بالكامل عبر مصفوفة الأذونات
    "admin_employee": set(),
    # الموظف: خدمة ذاتية فقط (لا إحصائيات شركة)
    "employee": {"submit_request", "record_attendance", "view_tasks"}}

ROLES = list(ROLE_DEFAULT_PERMS.keys())

# المستوى الهرمي لكل دور (الأعلى يدير الأدنى فقط)
ROLE_LEVEL: dict[str, int] = {
    "super_admin": 100,
    "company_owner": 80,
    "company_manager": 60,
    "hr": 40,
    "branch_supervisor": 40,
    "accountant": 35,
    "delegate": 30,
    "admin_employee": 20,
    "employee": 10}

# الأدوار التي يحق لها تقديم طلب باسم موظف آخر ("تقديم نيابةً عن").
#
# قرار العميل: HR والمندوب فقط.
#   - HR: الجهة المخوَّلة بفتح الإجراءات الداخلية باسم الموظفين والمسؤولين جميعًا.
#   - المندوب (PRO): المعاملات الحكومية (تجديد إقامة، إذن عمل، ترخيص) يفتحها
#     باسم الموظف بحكم طبيعة عمله — لا يملك الموظف نفسه أن يبدأها.
# وكل دور آخر — بما فيه مدير الشركة والمحاسب ومسؤول الفرع — يقدّم لنفسه فقط
# مهما كانت صلاحياته الأخرى.
#
# لماذا لا تكفي view_employee التي كانت الواجهة تستعملها بوابةً: صلاحية *رؤية*
# الموظفين ليست تفويضًا بالتصرّف باسمهم. المحاسب يملكها لأنه يشغّل الرواتب،
# فورث معها قائمةً تضم المدير العام وHR — وكان يفتح لهم طلبات فعلًا.
#
# وقبل ذلك لم يكن على الخادم فحص أصلًا: assert_same_company وحدها كانت الحارس،
# فأي حساب يملك submit_request (أي كل الحسابات) كان يقدّر يقدّم باسم أي موظف
# في شركته عبر POST مباشر — حتى الموظف العادي الذي يُرفض بـ403 من رؤية القائمة.
ON_BEHALF_ROLES = {"hr", "delegate"}

# الأدوار التي يُلزَم أصحابها بالتحقق الثنائي (SEC-02).
# المعيار: من يملك بيانات غيره أو يتصرّف باسمه. صاحب الشركة يرى كل الشركات،
# والمدير يعدّل الموظفين ويمنح الصلاحيات، وHR يفتح الطلبات باسم الموظفين
# ويصحّح الحضور، والمندوب يدير المعاملات الحكومية. سرقة أيٍّ من هذه الحسابات
# بكلمة مرور وحدها تكفي لاختراق بيانات الشركة كلها.
# الموظف والمحاسب ومسؤول الفرع يبقى التفعيل لهم اختياريًا.
TWOFA_REQUIRED_ROLES = {"super_admin", "company_owner", "company_manager",
                        "hr", "delegate"}


def requires_2fa(role: str) -> bool:
    return role in TWOFA_REQUIRED_ROLES


def can_submit_on_behalf(role: str) -> bool:
    """هل يحق لهذا الدور تقديم طلب باسم موظف غير نفسه؟"""
    return role == "super_admin" or role in ON_BEHALF_ROLES


# الأدوار التي ترتبط بملف موظف وتبصم حضورًا (خدمة ذاتية)
ATTENDANCE_ROLES = {"employee"}

# الأدوار التي ترى كل الشركات (تختار بينها)
CROSS_COMPANY_ROLES = {"super_admin", "company_owner"}


def is_cross_company_user(user) -> bool:
    """R9 §16 — يشمل حاملي flag is_cross_company (متعدد الشركات).
    مثال: مندوب يخدم شركتين مثل محمد فاروق. للاستخدام في deps.py
    بدل الفحص المباشر user.role in CROSS_COMPANY_ROLES."""
    if user.role in CROSS_COMPANY_ROLES:
        return True
    return bool(getattr(user, "is_cross_company", False))

# تسمية عربية لكل دور — تُستخدم لعرض سلسلة الاعتماد في المستندات المطبوعة (PDF/HTML) بدل
# رمز الدور التقني الخام (P0-04: لا يظهر company_manager/hr/branch_supervisor في مستند رسمي).
ROLE_LABEL_AR: dict[str, str] = {
    "branch_supervisor": "المسؤول المباشر", "company_manager": "المدير العام",
    "hr": "شؤون الموظفين/القانونية", "delegate": "المندوب", "accountant": "المحاسب",
    "company_owner": "صاحب الشركة", "super_admin": "الإدارة العليا", "employee": "الموظف"}


def role_level(role: str) -> int:
    return ROLE_LEVEL.get(role, 0)


def can_manage_role(actor_role: str, target_role: str) -> bool:
    """يحق للمستخدم إدارة من هم أدنى منه مستوى فقط (والإدارة العليا تدير الجميع)."""
    if actor_role == "super_admin":
        return True
    return role_level(actor_role) > role_level(target_role)


#: أدوار لا تُوجَّه إليها إنذارات وظيفية. الإنذار أداة انضباط يوجّهها صاحب
#: السلطة إلى من تحته؛ وتوجيهه إلى المدير يقلب التسلسل — ويجعل الشؤون
#: القانونية، وهي تحت إدارته، طرًفا يؤدّبه.
WARNING_EXEMPT_ROLES = {"company_manager", "company_owner", "super_admin"}


def may_receive_warning(role: str) -> bool:
    """هل يجوز توجيه إنذار لصاحب هذا الدور؟"""
    return role not in WARNING_EXEMPT_ROLES


def effective_permissions(role: str, assigned: set[str]) -> set[str]:
    """الصلاحيات الفعّالة = الافتراضية للدور + المُسندة صراحةً (غير المنتهية)."""
    if role == "super_admin":
        return _ALL | {"manage_companies"}
    return ROLE_DEFAULT_PERMS.get(role, set()) | (assigned or set())


def has_permission(role: str, assigned: set[str], perm: str) -> bool:
    if role == "super_admin":
        return True
    return perm in effective_permissions(role, assigned)


# ===========================================================================
# نظام الأذونات الدقيق: مصفوفة (صفحة × فعل) لكل مستخدم — متوافق خلفيًا.
# من ليس له منح دقيقة لصفحة معيّنة يبقى على صلاحيات دوره الافتراضية.
# ===========================================================================
ACTIONS_AR = {
    "read": "قراءة", "add": "إضافة", "edit": "تعديل", "delete": "حذف",
    "print": "طباعة", "export": "تصدير", "approve": "اعتماد"}

# ربط الصلاحية القديمة بـ (الصفحة، الفعل) — فقط ما نريد التحكم الدقيق فيه
LEGACY_TO_PA: dict[str, tuple[str, str]] = {
    "view_employee": ("employees", "read"),
    "create_employee": ("employees", "add"),
    "edit_employee": ("employees", "edit"),
    "delete_employee": ("employees", "delete"),
    "view_reports": ("reports", "read"),
    "export_reports": ("reports", "export"),
    "approve_request": ("requests", "approve"),
    "submit_request": ("requests", "add"),
    "view_documents": ("documents", "read"),
    "upload_documents": ("documents", "add"),
    "view_attendance": ("attendance", "read"),
    "record_attendance": ("attendance", "add"),
    "manage_permits": ("permits", "edit"),
    "manage_licenses": ("licenses", "edit"),
    "view_payroll": ("payroll", "read"),
    "run_payroll": ("payroll", "add"),
    "manage_templates": ("templates", "edit"),
    "manage_users": ("users", "edit"),
    "view_audit": ("audit", "read"),
    "manage_branches": ("branches", "edit"),
    "calculate_eos": ("eos", "read")}
PA_TO_LEGACY: dict[tuple[str, str], str] = {v: k for k, v in LEGACY_TO_PA.items()}

PAGE_LABELS = {
    "employees": "الموظفون", "reports": "التقارير", "requests": "الطلبات",
    "documents": "المستندات", "attendance": "الحضور", "permits": "الإقامات",
    "licenses": "التراخيص", "payroll": "الرواتب", "templates": "الصيغ",
    "users": "المستخدمون", "audit": "سجل التدقيق", "branches": "الفروع", "eos": "نهاية الخدمة"}

# السطح الكامل للأفعال المتاحة لكل صفحة — المرجع الوحيد لبناء المصفوفة وفرضها.
# يشمل الأفعال السبعة [قراءة، إضافة، تعديل، حذف، طباعة، تصدير، اعتماد] حيثما تنطبق.
PAGE_ACTIONS: dict[str, list[str]] = {
    "employees":  ["read", "add", "edit", "delete", "print", "export"],
    "reports":    ["read", "export", "print"],
    "requests":   ["read", "add", "approve", "print"],
    "documents":  ["read", "add", "delete", "print"],
    "attendance": ["read", "add", "export"],
    "permits":    ["read", "edit", "print"],
    "licenses":   ["read", "edit", "print"],
    "payroll":    ["read", "add", "export", "print"],
    "templates":  ["read", "edit", "print"],
    "users":      ["read", "edit"],
    "audit":      ["read", "export"],
    "branches":   ["read", "edit"],
    "eos":        ["read", "print"]}

# الأفعال المشتقّة: عند غياب منح مخصّصة، تَرِث افتراضيًا من فعل أساس بنفس الصفحة.
# (من يستطيع العرض يطبع/يصدّر افتراضيًا؛ من يستطيع التعديل يعتمد) — قابلة للإلغاء بالمصفوفة.
_DERIVED_ACTION_BASE = {"print": "read", "export": "read", "approve": "edit"}


def permission_matrix_catalog() -> list[dict]:
    """قائمة الصفحات وأفعالها المتاحة (لبناء واجهة المصفوفة)."""
    order = ["read", "add", "edit", "delete", "print", "export", "approve"]
    return [{"code": p, "label": PAGE_LABELS.get(p, p),
             "actions": [a for a in order if a in set(acts)]}
            for p, acts in sorted(PAGE_ACTIONS.items())]


def has_page_action(role: str, assigned: set[str], page: str, action: str) -> bool:
    """يتحقق من صلاحية (صفحة، فعل): المنح الدقيقة تتقدّم، وإلا دور المستخدم.

    ترتيب الحسم: super_admin ← منح المصفوفة المخصّصة ← الصلاحية القديمة المكافئة ←
    فعل مشتقّ يرث من فعل أساس (طباعة/تصدير←قراءة، اعتماد←تعديل).
    """
    if role == "super_admin":
        return True
    page_grants = {c.split(".", 1)[1] for c in assigned if c.startswith(page + ".")}
    if page_grants:  # للمستخدم مصفوفة مخصّصة لهذه الصفحة → تتحكّم وحدها
        return action in page_grants
    legacy = PA_TO_LEGACY.get((page, action))
    if legacy:
        return legacy in ROLE_DEFAULT_PERMS.get(role, set()) or legacy in assigned
    # فعل بلا صلاحية قديمة مكافئة (طباعة/تصدير/اعتماد) → يرث من فعل الأساس
    base = _DERIVED_ACTION_BASE.get(action)
    if base and base != action:
        return has_page_action(role, assigned, page, base)
    return False


def check_legacy(role: str, assigned: set[str], perm: str) -> bool:
    """نقطة التحقق الموحّدة: تحوّل الصلاحية القديمة لمصفوفة دقيقة إن أمكن."""
    pa = LEGACY_TO_PA.get(perm)
    if pa:
        return has_page_action(role, assigned, pa[0], pa[1])
    return has_permission(role, assigned, perm)

# ===========================================================================
# V2.2 §4.5 (AP-01) — مجال القرار لكل فئة طلب.
#
# ROOT CAUSE: صلاحية واحدة `approve_request` تحكم كل الأنواع — فمن يعتمد
# إجازة يملك اعتماد خصم وتظلّم وإنهاء خدمة، والفصل بين الواجبات (SoD) يصير
# اسًما بلا أثر. المواصفة تطلب صلاحية لكل نوع قرار.
#
# الخريطة مشتقّة من فئات الكتالوج، والمنح في ROLE_DEFAULT_PERMS مشتقّة من
# approval_chain_json الفعلية — فلا يفقد دور صلاحية كان يمارسها.
# ===========================================================================
DECISION_DOMAIN_BY_CATEGORY: dict[str, str] = {
    "الحضور والإجازات": "approve_leave",
    "الشهادات والخطابات": "approve_certificate",
    "الطلبات المالية": "approve_finance",
    "الإقامة والمعاملات الحكومية": "approve_government",
    "بيانات الموظف والمستندات": "approve_personnel",
    "التطوير الوظيفي": "approve_personnel",
    "الشكاوى والتظلمات": "approve_grievance",
    "العقود وإنهاء الخدمة": "approve_exit",
    "طلبات عامة": "approve_general",
    "نماذج إدارية": "approve_general"}


def decision_permission(category: str | None) -> str:
    """الصلاحية المطلوبة للقرار في هذه الفئة — العامة لما لا فئة له."""
    return DECISION_DOMAIN_BY_CATEGORY.get(category or "", "approve_general")


# كل صلاحيات القرار — يستخدمها حرّاس المسارات بدل الصلاحية العامة المهجورة.
# بلا هذه المجموعة كان نزع approve_request من الأدوار يُغلق /decide على الجميع.
APPROVAL_PERMS: tuple[str, ...] = (
    "approve_leave", "approve_certificate", "approve_finance", "approve_government",
    "approve_personnel", "approve_grievance", "approve_exit", "approve_general",
    "complete_validation", "approve_request",
)


def can_complete_stage(role: str, assigned: set[str], category: str | None,
                       step_type: str | None) -> bool:
    """V2.2 §13.3 (AC-03) — التحقق شيء والقرار شيء آخر.

    ROOT CAUSE: كل خطوة في السلسلة كانت "اعتماًدا"، فمن يتحقّق من صحة بيانات
    الخصم يحتاج صلاحية القرار المالي نفسها التي يحتاجها من يقرّر صرفه. ومتى
    مُنحت له لأجل خطوة التحقق، صار يملك القرار في كل الطلبات المالية.

    خطوة VALIDATION تُنجَز بـcomplete_validation؛ والقرار وحده يحتاج صلاحية
    مجاله.
    """
    if role == "super_admin":
        return True
    perms = effective_permissions(role, assigned)
    if (step_type or "").upper() == "VALIDATION":
        return "complete_validation" in perms or "approve_request" in perms
    return can_decide_category(role, assigned, category)


def can_decide_category(role: str, assigned: set[str], category: str | None) -> bool:
    """هل يملك هذا المستخدم قرار هذه الفئة؟

    يُقبل approve_request المهجورة للتوافق مع منح صريحة قائمة على حسابات
    فعلية — إسقاطها فجأة يوقف اعتماد أنواع كاملة في الإنتاج، وهو ما تمنعه
    قاعدة "لا تغيّر سلوًكا يعمل".
    """
    if role == "super_admin":
        return True
    perms = effective_permissions(role, assigned)
    return decision_permission(category) in perms or "approve_request" in perms
