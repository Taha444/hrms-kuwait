# -*- coding: utf-8 -*-
"""محرّك الطلبات والموافقات (configurable Requests & Approvals).

كل نوع طلب يُعرَّف بسلسلة مراحل مرتّبة (approval_chain_json). كل مرحلة:
  { "order": 0, "label": "...", "role": "branch_supervisor", "kind": "approval",
    "produces_document": false }

أنواع المراحل (kind):
- approval     : يحتاج قرار اعتماد/رفض من صاحب الدور.
- hr_review    : يعتمد HR ثم يولّد المستند ويحدد موعد توقيع (awaiting_signature)،
                 وبعد رفع الموقّع يتقدّم الطلب.
- delegate_exit: مهمة للمندوب لإجراءات إذن المغادرة (awaiting_delegate)،
                 وبعد رفع إذن المغادرة يكتمل الطلب.
- pickup       : إشعار HR والعامل بأن المستند جاهز للاستلام (ready_for_pickup).

المدير العام / صاحب الشركة / الإدارة العليا يحق لهم الرفض/الإلغاء في أي مرحلة.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy import or_ as sa_or
from sqlalchemy.orm import Session

from . import models
from .task_kinds import is_notification
from .config import settings
from .notifications import create_task, notify_employee_self, notify_from_template, users_by_role
from .permissions import ROLE_LABEL_AR
from .storage import key_exists, save_at_key

# إلغاء الطلب إجراء تشغيلي → المالك (اطلاع فقط) مستبعَد
CANCEL_ROLES = {"super_admin", "company_manager"}

# نص «الصيغة الرسمية» الحرفي لكل نوع طلب من حزمة V1.3 (منقول من ملف المراجعة) — يُستخدم
# كإقرار/تعهد الموظف في المستند المعتمد النهائي (HTML/PDF)، بدل تفريغ عام لحقول payload.
REQUEST_OFFICIAL_TEXT: dict[str, str] = {
    "REQLV": "أتقدم بطلب إجازة خلال الفترة المحددة بغرض السفر خارج الكويت، وأتعهد بالعودة إلى العمل في التاريخ المحدد، وبإبلاغ الشركة فور حدوث أي ظرف يمنع العودة في الموعد. وأقر بأن الطلب لا يكون نافًذا إلا بعد استكمال مراجعة المسؤول المباشر، والإفادة المالية عند اللزوم، ومراجعة شؤون الموظفين / الشؤون القانونية، وصدور القرار النهائي. الإفادة المالية معلوماتية فقط وليست موافقة أو رفًضا نهائًيا. المندوب لا يتدخل إلا بعد اعتماد الإجازة وللسفر فقط.",
    "REQPER": "أتقدم بطلب إذن أثناء الدوام للفترة المحددة، وأتعهد بالعودة إلى مقر العمل فور انتهاء مدة الإذن. وأعلم أن أي تمديد أو غياب بعد المدة المحددة يحتاج إلى موافقة جديدة. ولا يعد هذا الإذن إجازة سفر ولا يترتب عليه أي إجراء من المندوب. لا يمر على المندوب، ويتم تسجيله كإذن داخلي فقط.",
    "REQEXIT": "أتقدم بطلب مغادرة مبكرة من مقر العمل في التاريخ والوقت المحددين، وأقر بأن الموافقة إن صدرت تقتصر على مدة المغادرة الموضحة ولا تعتبر إجازة أو إذن سفر أو خروج خارج الكويت. لا يستخدم هذا النموذج لإذن خروج السفر ولا يمر على المندوب.",
    "REQLATE": "أقر بحدوث التأخير الموضح في هذا النموذج، وأتقدم بتبريري للإدارة المختصة للنظر فيه. وأعلم أن قبول التبرير أو رفضه يخضع لتقدير المسؤول المختص وسياسات الحضور المعتمدة. الإقرار بالتأخير لا يعني قبول التبرير تلقائًيا.",
    "REQATT": "أتقدم بطلب تصحيح سجل الحضور أو الانصراف للتاريخ المحدد، وأقر بأن البيانات المقدمة صحيحة، وأن التصحيح لا يتم إلا بعد مراجعة السجل والمرفقات واعتماد المسؤول المختص. يفضل إرفاق ما يثبت سبب التصحيح.",
    "REQSHIFT": "أتقدم بطلب تغيير الوردية أو جدول العمل للفترة المحددة، وأقر بأن تنفيذ التغيير لا يتم إلا بعد موافقة المسؤول المختص والتأكد من عدم الإضرار بسير العمل. قرار تشغيلي، وقد يحتاج بديًلا أو تغطية.",
    "REQOT": "يرجى اعتماد العمل الإضافي الموضح بهذا النموذج، وذلك لحاجة العمل وخلال المدة المحددة. وأقر بأن صرف أي مقابل عن العمل الإضافي لا يتم إلا بعد اعتماد الساعات فعلًيا وفق سياسة الشركة. لا يصرف مقابل مالي دون اعتماد الساعات والميزانية.",
    "REQWLOC": "تقرر تكليف الموظف مؤقًتا بالعمل في الموقع أو الفرع الموضح خلال المدة المحددة، دون أن يعد ذلك نقًلا دائًما أو تعديًلا في مقر العمل الرسمي إلا بقرار مستقل. يفصل النظام بين موقع العمل الرسمي والفعلي.",
    "REQMIS": "يرجى اعتماد مهمة العمل الخارجية الموضحة بهذا النموذج، مع التزام الموظف بتنفيذ المهمة في حدود التكليف وتسليم ما يثبت الإنجاز أو المصروفات إن وجدت. إذا ترتب مصروفات، تمر على المالية كإفادة مراجعة.",
    "REQRESE": "أتقدم بطلب تجديد الإقامة قبل موعد التجديد العادي للسبب الموضح، وأرفق المستندات اللازمة للنظر في الطلب. وأعلم أن بدء المعاملة الحكومية لا يتم إلا بعد قبول المبرر واستكمال المراجعات واعتماد الطلب. – نافذة 31-90 يومًا غالًبا، ويحتاج سبًبا ومرفقات.",
    "REQRESN": "يرجى اتخاذ إجراءات تجديد إقامة الموظف الموضح قبل تاريخ الانتهاء، مع مراجعة اكتمال المستندات وحالة الجواز والبطاقة المدنية. ولا يبدأ التنفيذ إلا بعد إسناد المهمة للمندوب المختص. – نافذة 0-30 يومًا، ويعامل كأولوية أعلى.",
    "REQPASS": "أتقدم بطلب تحديث بيانات جواز السفر أو متابعة تجديده وفق البيانات والمستندات المرفقة، وأقر بصحة صورة الجواز والبيانات المسجلة. يؤثر على الإقامة والسفر ويحتاج تحقق مستندي.",
    "REQCID": "يرجى مراجعة وتحديث بيانات البطاقة المدنية أو اتخاذ إجراءات التجديد وفق المستندات المرفقة، مع التزام الموظف بتوفير أي مستندات إضافية مطلوبة. يرتبط بملف الموظف والمعاملات الحكومية.",
    "REQWP": "يرجى اتخاذ إجراءات تجديد إذن العمل للموظف الموضح، بعد مراجعة المستندات والبيانات الحكومية اللازمة، ولا يبدأ التنفيذ الخارجي إلا بعد اعتماد الجهة المختصة. معاملة حكومية تنفذ بواسطة المندوب عند الإسناد.",
    "REQGOV": "يرجى فتح ومتابعة المعاملة الحكومية الموضحة، مع بيان نوع المعاملة والمستندات والجهة الخارجية. ويقتصر دور المندوب على التنفيذ ورفع إثبات الإنجاز. المندوب لا يملك اعتمادًا نهائًيا.",
    "REQTRFLIC": "يرجى دراسة نقل الموظف بين الفرع أو الترخيص الموضح، مع مراعاة أثر النقل على التشغيل والبيانات الحكومية وسجلات الموظف. ولا يتم التعديل إلا بعد الاعتماد. يؤثر على المكان الرسمي / الفعلي وربما التراخيص.",
    "REQDOC": "أقر بأن المستند المرفق صحيح وواضح ومطابق للأصل في حدود علمي، وأطلب تحديث ملفي الوظيفي وفًقا له. يحتاج تحقق مستندي قبل اعتماده في الملف.",
    "REQDATA": "أتقدم بطلب تعديل البيانات الموضحة، وأقر بصحة البيانات الجديدة وبمسؤوليتي عن أي خطأ فيها، وأرفق المستند الداعم عند تعديل بيانات رسمية. البيانات الرسمية تحتاج مستن ًدا.",
    "REQBANK": "أتقدم بطلب تغيير الحساب البنكي المعتمد لتحويل مستحقاتي، وأقر بأن البيانات البنكية صحيحة ومملوكة لي أو مصرح باستخدامها حسب سياسة الشركة. بيانات مالية حساسة، تعرض مقنعة لمن لا يملك صالحية.",
    "REQCONTACT": "أطلب تحديث بيانات الاتصال والطوارئ الموضحة، وأقر بمسؤوليتي عن صحة البيانات وتحديثها عند أي تغيير. بيانات تشغيلية لا تحتاج مسار طويل.",
    "REQCERTSAL": "أتقدم بطلب إصدار شهادة راتب للجهة الموضحة، وأقر بأن الشهادة تصدر بالبيانات المصرح بإظهارها فقط ولا تتضمن أي ملاحظات داخلية غير مصرح بها. صيغة محايدة؛ بيانات الراتب حسب الصلاحية.",
    "REQCERTEMP": "أتقدم بطلب إصدار شهادة لمن يهمه الأمر تثبت بيانات عملي لدى الشركة حتى تاريخ الإصدار، وذلك للاستخدام في الغرض الموضح فقط. لا تتضمن تفاصيل حساسة إلا بتصريح.",
    "REQCERTEXP": "أتقدم بطلب إصدار شهادة خبرة توضح مدة عملي والمسمى الوظيفي والمهام العامة المصرح بإظهارها، دون تضمين أسباب إنهاء أو جزاءات أو ملاحظات داخلية غير مصرح بها. صيغة قانونية محايدة.",
    "REQFILE": "أتقدم بطلب الحصول على نسخة من المستند الموضح، وأقر باستخدام النسخة للغرض المحدد، مع مراعاة سياسة الشركة في تسليم المستندات وحماية البيانات. حسب ملكية المستند وسرية البيانات.",
    "REQADV": "أتقدم بطلب سلفة أو قرض موظف بالقيمة الموضحة، وأتعهد في حال الموافقة بالالتزام بخطة السداد المعتمدة. وأعلم أن أي استقطاع لا يتم إلا وفق الضوابط والاعتمادات المقررة. يحتاج مراجعة مالية وخطة سداد.",
    "REQEXP": "أتقدم بطلب استرداد المصروفات الموضحة، وأقر بأنها صرفت لغرض متعلق بالعمل وبناًء على تكليف أو موافقة، وأرفق الفواتير أو الإثباتات اللازمة. لا يعتمد دون إثباتات.",
    "REQALLOW": "أتقدم بطلب بدل أو ميزة وفق البيانات الموضحة، وأعلم أن الموافقة تخضع لسياسة الشركة والميزانية وصلاحيات الاعتماد. قد يؤثر على الراتب ويحتاج اعتمادًا.",
    "REQPAY": "أتقدم باعتراض أو استفسار عن الراتب للفترة الموضحة، وأطلب مراجعة البنود محل الاعتراض مع المحافظة على سرية البيانات المالية. سري ويقتصر على المخولين.",
    "REQDED": "أتقدم باعتراض على الخصم الموضح، وأطلب مراجعة سببه ومستنده وتاريخ تطبيقه، مع احتفاظي بحقي في تقديم المستندات أو الردود الداعمة. حق الرد والقرار المسبب.",
    "REQGRV": "أتقدم بهذه الشكوى أو التظلم وفق الوقائع الموضحة، وأقر بأن ما ورد بها صحيح في حدود علمي، وأطلب التعامل معها بسرية وبما يمنع تضارب المصالح. إذا كان المسؤول المباشر طرًفا لا يطلع عليها تلقائًيا.",
    "REQVIO": "أتقدم باعتراض على المخالفة الموضحة، وأطلب مراجعة الواقعة والمستندات، وأرفق ما لدي من ردود أو أدلة مؤيدة. لا يسقط حق الرد.",
    "REQWARN": "أقر باستلام الإنذار الموضح، ويحق لي تقديم رد أو اعتراض خلال المدة المحددة. ولا يعد استلامي للإنذار إقراًرا بصحة كل ما ورد فيه ما لم أصرح بذلك كتابة. فصل بين الاستلام والإقرار بالمضمون.",
    "REQGEN": "أتقدم بهذا الطلب أو الاقتراح للإدارة المختصة للنظر فيه، وأعلم أن قبوله أو تنفيذه يخضع لتقدير الشركة وإمكاناتها. مسار بسيط.",
    "REQTRN": "أتقدم بطلب حضور التدريب الموضح، لما له من علاقة بتطوير أدائي الوظيفي، وأتعهد بالالتزام بالحضور وتقديم ما يثبت إتمام التدريب عند الطلب. قد يحتاج ميزانية.",
    "REQTRF": "أتقدم بطلب نقل داخلي إلى الجهة الموضحة، وأعلم أن النقل لا يتم إلا بعد موافقة الجهة الحالية والجهة المستقبلة وصاحب الصلاحية. يحتاج أثر تشغيلي.",
    "REQPROMO": "يرجى دراسة ترقية أو تعديل راتب الموظف الموضح بناًء على الأداء أو تغير المهام أو الهيكل، مع مراعاة الميزانية وصلاحيات الاعتماد. حساس مالًيا.",
    "REQCON": "يرجى اتخاذ قرار بشأن تجديد أو عدم تجديد عقد الموظف قبل تاريخ الانتهاء، مع مراجعة احتياج العمل والالتزامات النظامية والمالية. قرار حساس يحتاج صياغة قانونية.",
    "REQRESIGN": "أتقدم بطلب الاستقالة من عملي لدى الشركة، وأقترح أن يكون آخر يوم عمل كما هو موضح. وأعلم أن قبول الاستقالة وتحديد آخر يوم عمل وإجراءات إخلاء الطرف تخضع لاعتماد الشركة. لا يغلق الملف قبل إخلاء الطرف.",
    "REQEOS": "يرجى احتساب وتسوية نهاية خدمة الموظف وفق بيانات الخدمة والراتب والمستحقات والالتزامات المسجلة، على أن يعد الاحتساب مبدئًيا حتى اعتماده قانونًيا ومالًيا. مبدئي ثم نهائي بعد الاعتماد.",
    "REQCLR": "يرجى استكمال إجراءات إخلاء الطرف والتأكد من تسليم العهد والمستندات وتسوية الالتزامات المالية قبل إصدار المخالصة أو إغلاق ملف الموظف. + + عهد مالية مستندات.",
    "ADMEMP": "تقرر فتح ملف موظف جديد وفق البيانات والمستندات المعتمدة، ولا يتم تفعيل الحساب أو الراتب أو الصلاحيات إلا بعد اكتمال الحد الأدنى من المستندات والاعتمادات. بداية ملف رسمي.",
    "ADMACTUAL": "يرجى اعتماد تعديل الراتب الفعلي أو مكان العمل الفعلي للموظف الموضح، مع بيان سبب التعديل وتاريخه، وتسجيل الأثر في سجل التدقيق. صالحية حقلية وسرية.",
    "ADMDED": "بناًء على الواقعة أو الالتزام الموضح، تقرر الإدارة دراسة إصدار خصم على الموظف وفق الضوابط المعتمدة، ولا يطبق الخصم إلا بعد بيان السبب والمستند وحق الرد والاعتماد المالي. لا خصم بلا سبب ومصدر إثبات.",
    "ADMVIO": "تقرر تسجيل مخالفة وظيفية على الموظف وفق الواقعة الموثقة والمستندات المؤيدة، مع تمكين الموظف من الرد أو الاعتراض وفق الإجراءات المعتمدة. قرار تأديبي حساس.",
    "ADMWARN": "تقرر إصدار إنذار وظيفي للموظف بشأن الواقعة الموضحة، مع بيان مستوى الإنذار وتاريخ سريانه وحق الموظف في الرد أو الاعتراض خلال المدة المحددة. استلام الإنذار لا يعني الإقرار بصحته.",
    "ADMTASK": "يكلف المندوب أو الموظف المختص بتنفيذ المهمة الموضحة خلال المدة المحددة، ويقتصر دوره على التنفيذ ورفع الإثبات، دون صلاحية اعتماد أصل الطلب أو تغييره. دور تنفيذ فقط.",
    "ADMMISS": "نحيطكم علًما بوجود نقص في المستندات الموضحة، ويرجى استكمالها خلال المهلة المحددة حتى لا تتأثر المعاملة أو ملف الموظف. إخطار رسمي.",
    "ADMLIC": "يرجى اتخاذ إجراءات تجديد مستند الشركة أو الترخيص الموضح قبل تاريخ الانتهاء، مع تحديد المستندات المطلوبة والجهة المنفذة والمسؤول عن المتابعة. قد يكلف للمندوب.",
    "ADMSIGN": "يستخدم هذا السجل لإثبات الاعتماد أو التوقيع الإلكتروني على المستند المحدد، مع بيان هوية الموّقع وتاريخ ووقت التوقيع ومعرف العملية. سجل تدقيق.",
}

# ----------------------- ربط الحالات الداخلية بحالات V1.3 و V1.5 الرسمية -----------------------
# كل حالة داخلية (Request.status) تُعرَض عبر هذا الربط بدل الاسم التقني الخام.
# - `code`: اسم V1.3 التاريخي (FIX-009) للتوافق العكسي مع الواجهة القديمة.
# - `v15`: اسم V1.5 canonical (DRAFT/SUBMITTED/IN_REVIEW/NEEDS_INFO/APPROVED/IN_EXECUTION/
#   COMPLETED/REJECTED/CANCELLED) للعرض في الواجهة الحديثة.
# - `label`: النص العربي المعروض للمستخدم.
STATUS_MAP: dict[str, dict[str, str]] = {
    "pending": {"code": "PENDING_APPROVAL", "v15": "IN_REVIEW", "label": "قيد الاعتماد"},
    "awaiting_signature": {"code": "AWAITING_SIGNATURE", "v15": "IN_EXECUTION", "label": "بانتظار التوقيع"},
    "awaiting_delegate": {"code": "AWAITING_DELEGATE", "v15": "IN_EXECUTION", "label": "بانتظار إجراءات المندوب"},
    "ready_for_pickup": {"code": "READY_FOR_PICKUP", "v15": "IN_EXECUTION", "label": "جاهز للاستلام"},
    "completed": {"code": "COMPLETED", "v15": "COMPLETED", "label": "مكتمل"},
    "rejected": {"code": "REJECTED", "v15": "REJECTED", "label": "مرفوض"},
    "cancelled": {"code": "CANCELLED", "v15": "CANCELLED", "label": "ملغى"},
    "returned": {"code": "NEEDS_INFO", "v15": "NEEDS_INFO", "label": "بحاجة معلومات إضافية"},
    # P0-#6 — Effect Failure: distinct terminal-ish status. الطلب معتمَد من الجميع لكن
    # التطبيق الآلي فشل (مثلاً: تصحيح حضور ما لقيش السجل). ليست returned (اللي بيرجع للـsubmitter)
    # ولا rejected (اللي بيقفل الطلب) — الحالة دي بتفتح مسار "action required" للإدارة.
    "apply_failed": {"code": "APPLY_FAILED", "v15": "FAILED", "label": "فشل التطبيق — يحتاج إجراء"},
}


def status_info(status: str) -> dict[str, str]:
    return STATUS_MAP.get(status, {"code": status.upper(), "v15": status.upper(), "label": status})


# ----------------------- أنواع الطلبات الافتراضية (للـ seed) -----------------------

# تصنيفات أنواع الطلبات (حزمة V1.3 — 49 نموذجًا رسميًا)
CAT_ATTENDANCE = "الحضور والإجازات"
CAT_RESIDENCY = "الإقامة والمعاملات الحكومية"
CAT_EMP_DATA = "بيانات الموظف والمستندات"
CAT_CERTIFICATES = "الشهادات والخطابات"
CAT_FINANCIAL = "الطلبات المالية"
CAT_GRIEVANCE = "الشكاوى والتظلمات"
CAT_GENERAL = "طلبات عامة"
CAT_CAREER = "التطوير الوظيفي"
CAT_CONTRACTS = "العقود وإنهاء الخدمة"
CAT_ADMIN = "نماذج إدارية"


def _simple(code: str, name: str, category: str, roles: list[str],
           produces_document: bool = False, requires_physical_signature: bool = True,
           is_confidential: bool = False, visible_to_employee: bool = False,
           default_template_code: str | None = None,
           validation_roles: tuple[str, ...] = ()) -> dict:
    """يبني نوع طلب بسلسلة موافقات خطّية بسيطة (مرحلة اعتماد لكل دور بالترتيب).

    تُستخدم لتغطية أنواع V1.3 الـ44 المتبقية (المسار الرئيسي المذكور في كل نموذج)
    دون تكرار منطق خاص — النوع الأول (leave) و(salary_certificate) وما شابه تبقى
    بمسارها المخصص (hr_review/delegate_exit/pickup) لأنها مطبَّقة ومختبرة فعلًا.

    visible_to_employee افتراضيًا False (P0-06): معظم الـ44 نوعًا إجراءات داخلية
    تبدأ من HR/الإدارة/المندوب/PRO لا من الموظف نفسه (خاصة كل ما يبدأ بـADM)، فتُستبعد
    من قائمة "طلب جديد" كخدمة ذاتية إلا ما صُرِّح صراحًة أنه يبدأ من الموظف.
    default_template_code (P0-02): ربط اختياري بأحد قوالب HRMS-PR-001..042 للتتبّع.
    """
    # V1.5 Phase 2: كل خطوة تحمل step_type canonical (DECISION للـ approval العادية،
    # AUTOMATION للخطوة النهائية إن كانت produces_document عبر النظام). الحقل اختياري
    # للتوافق مع الخطوات القديمة (kind="approval"/"hr_review"/"delegate_exit"/"pickup").
    chain = [
        # V2.2 §13.3 (AC-03) — خطوة التحقق ليست قراًرا: من يتحقّق من صحة
        # البيانات لا يحتاج صلاحية من يقرّر صرف المال، ومنحها له لأجل خطوته
        # يمنحه القرار في كل الطلبات المالية.
        {"order": i,
         "label": (f"تحقّق {ROLE_LABEL_AR.get(r, r)}" if r in validation_roles
                   else f"اعتماد {ROLE_LABEL_AR.get(r, r)}"),
         "role": r, "kind": "approval",
         "step_type": "VALIDATION" if r in validation_roles else "DECISION",
         "produces_document": produces_document and i == len(roles) - 1}
        for i, r in enumerate(roles)
    ]
    return {
        "code": code, "name": name, "category": category,
        "requires_physical_signature": requires_physical_signature,
        "produces_document": produces_document,
        "approval_chain_json": chain, "template_html": None,
        "is_confidential": is_confidential, "visible_to_employee": visible_to_employee,
        "default_template_code": default_template_code,
    }


DEFAULT_REQUEST_TYPES = [
    {
        "code": "leave",
        "name": "طلب إجازة",
        "category": CAT_ATTENDANCE,
        "requires_physical_signature": True,
        "produces_document": True,
        "approval_chain_json": [
            # V2.2 §14 (RW-04) — إجازة داخل الرصيد والمدة: مدير واحد ثم تحديث
            # الرصيد والحضور. كانت تمرّ بأربعة معتمِدين — مسؤول الفرع والمدير
            # العام وHR والمندوب — على يومين إجازة. المدير العام لا يضيف قراًرا
            # فوق قرار المسؤول المباشر: كلاهما يجيب السؤال نفسه، والثاني يؤخّر
            # إجازة أُقرّت فعًلا. ومراجعة HR تحقّق من الرصيد لا قرار عليه.
            {"order": 0, "label": "اعتماد مسؤول الفرع", "role": "branch_supervisor",
             "kind": "approval", "step_type": "DECISION"},
            {"order": 1, "label": "تحديث الرصيد والحضور (شؤون الموظفين)", "role": "hr",
             "kind": "hr_review", "step_type": "VALIDATION", "produces_document": True},
            # QA-10 — تظهر فقط مع سفر خارج البلاد؛ إجازة داخل الكويت لا تمر
            # بالمندوب أصًلا
            {"order": 2, "label": "إجراءات إذن مغادرة البلاد (المندوب)", "role": "delegate",
             "kind": "delegate_exit",
             "when": {"field": "travel_required", "truthy": True}},
        ],
        "template_html": None,
        "visible_to_employee": True, "default_template_code": "HRMS-PR-015",
    },
    {
        "code": "salary_certificate",
        "name": "طلب شهادة راتب",
        "category": CAT_CERTIFICATES,
        "requires_physical_signature": False,
        "produces_document": True,
        "approval_chain_json": [
            {"order": 0, "label": "اعتماد وتوقيع المدير العام", "role": "company_manager",
             "kind": "approval", "produces_document": True},
            {"order": 1, "label": "جاهزة للاستلام من شؤون الموظفين", "role": "hr", "kind": "pickup"},
        ],
        "template_html": None,
        "visible_to_employee": True, "default_template_code": "HRMS-PR-001",
    },
    {
        "code": "exit_permission",
        "name": "طلب إذن خروج/استئذان",
        "category": CAT_ATTENDANCE,
        "requires_physical_signature": False,
        "produces_document": False,
        "approval_chain_json": [
            {"order": 0, "label": "اعتماد مسؤول الفرع", "role": "branch_supervisor", "kind": "approval"},
            {"order": 1, "label": "اعتماد المدير العام", "role": "company_manager", "kind": "approval"},
        ],
        "template_html": None,
        "visible_to_employee": True, "default_template_code": "HRMS-PR-018",
    },
    {
        "code": "advance",
        "name": "طلب سلفة",
        "category": CAT_FINANCIAL,
        "requires_physical_signature": False,
        "produces_document": False,
        "approval_chain_json": [
            {"order": 0, "label": "اعتماد المدير العام", "role": "company_manager", "kind": "approval"},
            {"order": 1, "label": "التنفيذ من المحاسب", "role": "accountant", "kind": "pickup"},
        ],
        "template_html": None,
        "visible_to_employee": True,
    },
    {
        "code": "loan",
        "name": "طلب قرض",
        "category": CAT_FINANCIAL,
        "requires_physical_signature": False,
        "produces_document": False,
        "approval_chain_json": [
            {"order": 0, "label": "اعتماد المدير العام", "role": "company_manager", "kind": "approval"},
            {"order": 1, "label": "التنفيذ من المحاسب", "role": "accountant", "kind": "pickup"},
        ],
        "template_html": None,
        "visible_to_employee": True,
    },

    # ----------------- الـ 44 نوعًا الرسمية المتبقية من حزمة V1.3 (FIX-002) -----------------
    # الحضور والإجازات
    _simple("REQPER", "طلب إذن أثناء الدوام", CAT_ATTENDANCE,
           ["branch_supervisor", "hr"], requires_physical_signature=False, visible_to_employee=True),
    _simple("REQEXIT", "طلب مغادرة مبكرة", CAT_ATTENDANCE,
           ["branch_supervisor", "hr"], requires_physical_signature=False, visible_to_employee=True),
    _simple("REQLATE", "تبرير تأخير", CAT_ATTENDANCE,
           ["branch_supervisor", "hr"], requires_physical_signature=False, visible_to_employee=True,
           default_template_code="HRMS-PR-031"),
    _simple("REQATT", "طلب تصحيح سجل حضور", CAT_ATTENDANCE,
           ["branch_supervisor", "hr"], requires_physical_signature=False, visible_to_employee=True,
           default_template_code="HRMS-PR-030"),
    _simple("REQSHIFT", "طلب تغيير وردية", CAT_ATTENDANCE,
           ["branch_supervisor", "company_manager"], requires_physical_signature=False,
           default_template_code="HRMS-PR-037"),
    _simple("REQOT", "طلب عمل إضافي", CAT_ATTENDANCE,
           ["branch_supervisor", "company_manager", "accountant"], requires_physical_signature=False,
           default_template_code="HRMS-PR-038"),
    _simple("REQWLOC", "تكليف مؤقت بموقع أو فرع", CAT_ATTENDANCE,
           ["branch_supervisor", "company_manager", "hr"], produces_document=True),
    _simple("REQMIS", "طلب مهمة عمل خارجية", CAT_ATTENDANCE,
           ["branch_supervisor", "company_manager"], produces_document=True,
           default_template_code="HRMS-PR-036"),

    # الإقامة والمعاملات الحكومية
    _simple("REQRESE", "طلب تجديد إقامة مبكر", CAT_RESIDENCY,
           ["hr", "company_manager", "delegate"], produces_document=True, visible_to_employee=True,
           default_template_code="HRMS-PR-021"),
    _simple("REQRESN", "طلب تجديد إقامة عادي", CAT_RESIDENCY,
           ["delegate", "hr"], produces_document=True,
           default_template_code="HRMS-PR-021"),
    _simple("REQPASS", "طلب تحديث أو تجديد جواز السفر", CAT_RESIDENCY,
           ["hr"], requires_physical_signature=False,
           default_template_code="HRMS-PR-024"),
    _simple("REQCID", "طلب تحديث أو تجديد البطاقة المدنية", CAT_RESIDENCY,
           ["hr", "delegate"], requires_physical_signature=False,
           default_template_code="HRMS-PR-023"),
    # DOC-11 — تجديد إذن العمل لا يُنتج مستنًدا من النظام: الإذن تُصدره الهيئة
    # العامة للقوى العاملة، وأي ورقة يولّدها النظام بشكله ليست إذًنا بل انتحال
    # صفة جهة حكومية. المندوب يرفع المستند الرسمي بعد استخراجه.
    _simple("REQWP", "طلب تجديد إذن عمل", CAT_RESIDENCY,
           ["hr", "company_manager", "delegate"], produces_document=False,
           default_template_code="HRMS-PR-022"),
    _simple("REQGOV", "طلب معاملة حكومية", CAT_RESIDENCY,
           ["hr", "delegate"], requires_physical_signature=False, visible_to_employee=True),
    _simple("REQTRFLIC", "طلب نقل عامل بين فرع أو ترخيص", CAT_RESIDENCY,
           ["branch_supervisor", "hr", "company_manager"], produces_document=True,
           default_template_code="HRMS-PR-007"),

    # بيانات الموظف والمستندات
    _simple("REQDOC", "رفع أو تحديث مستند موظف", CAT_EMP_DATA,
           ["hr"], requires_physical_signature=False, visible_to_employee=True),
    _simple("REQDATA", "طلب تعديل البيانات الشخصية", CAT_EMP_DATA,
           ["hr"], requires_physical_signature=False, visible_to_employee=True,
           default_template_code="HRMS-PR-039"),
    # RW-11 — تغيير الحساب البنكي: تحقّق HR من الهوية والمستند أوًلا، ثم مراجع
    # مالي مستقل. كان يبدأ بالمحاسب مباشرة بلا تحقّق من أن طالب التغيير هو
    # صاحب الحساب فعًلا — وهذا أشيع مسار احتيال داخلي في أنظمة الرواتب:
    # رسالة "غيّروا حسابي" تمرّ بلا تثبّت من هوية مرسلها.
    _simple("REQBANK", "طلب تغيير الحساب البنكي", CAT_EMP_DATA,
           ["hr", "accountant", "company_manager"], validation_roles=("hr",),
           requires_physical_signature=False, visible_to_employee=True,
           default_template_code="HRMS-PR-004"),
    _simple("REQCONTACT", "تحديث بيانات الاتصال والطوارئ", CAT_EMP_DATA,
           ["hr"], requires_physical_signature=False, visible_to_employee=True,
           default_template_code="HRMS-PR-039"),

    # الشهادات والخطابات
    # AC-11 + RW-03 + DOC-01 — شهادة الراتب تُولَّد من بيانات معتمَدة أصًلا
    # (الراتب في ملف الموظف)، فلا معنى لسلسلة موافقات عليها. مرحلة المدير
    # العام كانت شكلية: لا يقرّر شيًئا — الراتب مقرَّر سلًفا — بل يؤخّر شهادة
    # يحتاجها الموظف اليوم لبنك أو سفارة. ختم HR وحده يكفي ويُثبت المصدر.
    _simple("REQCERTSAL", "طلب شهادة راتب", CAT_CERTIFICATES,
           ["hr"], produces_document=True, requires_physical_signature=False,
           visible_to_employee=True, default_template_code="HRMS-PR-001"),
    _simple("REQCERTEMP", "طلب شهادة لمن يهمه الأمر", CAT_CERTIFICATES,
           ["hr"], produces_document=True, requires_physical_signature=False, visible_to_employee=True,
           default_template_code="HRMS-PR-002"),
    _simple("REQCERTEXP", "طلب شهادة خبرة", CAT_CERTIFICATES,
           ["hr", "company_manager"], produces_document=True, requires_physical_signature=False, visible_to_employee=True,
           default_template_code="HRMS-PR-003"),
    _simple("REQFILE", "طلب نسخة من ملف أو مستند", CAT_CERTIFICATES,
           ["hr"], requires_physical_signature=False),

    # الطلبات المالية
    _simple("REQADV", "طلب سلفة أو قرض", CAT_FINANCIAL,
           ["company_manager", "accountant"], requires_physical_signature=False, visible_to_employee=True),
    _simple("REQEXP", "طلب استرداد مصروفات", CAT_FINANCIAL,
           ["branch_supervisor", "accountant"], requires_physical_signature=False, visible_to_employee=True),
    _simple("REQALLOW", "طلب بدل أو ميزة", CAT_FINANCIAL,
           ["branch_supervisor", "company_manager"], requires_physical_signature=False),
    _simple("REQPAY", "اعتراض على الراتب", CAT_FINANCIAL,
           ["accountant", "company_manager"], requires_physical_signature=False, visible_to_employee=True,
           default_template_code="HRMS-PR-032"),
    # AC-03 — خطوة HR هنا تحقّق تعاقدي لا قرار مالي: القرار للمحاسب والمدير
    _simple("REQDED", "اعتراض على خصم", CAT_FINANCIAL,
           ["accountant", "hr", "company_manager"], validation_roles=("hr",),
           requires_physical_signature=False, visible_to_employee=True,
           default_template_code="HRMS-PR-033"),

    # الشكاوى والتظلمات
    _simple("REQGRV", "شكوى أو تظلم", CAT_GRIEVANCE,
           ["hr"], requires_physical_signature=False, is_confidential=True, visible_to_employee=True,
           default_template_code="HRMS-PR-041"),
    _simple("REQVIO", "اعتراض على مخالفة", CAT_GRIEVANCE,
           ["hr", "company_manager"], requires_physical_signature=False,
           default_template_code="HRMS-PR-013"),
    _simple("REQWARN", "إقرار أو رد على إنذار", CAT_GRIEVANCE,
           ["hr"], requires_physical_signature=False,
           default_template_code="HRMS-PR-014"),

    # طلبات عامة
    _simple("REQGEN", "طلب عام أو اقتراح", CAT_GENERAL,
           ["branch_supervisor"], requires_physical_signature=False),

    # التطوير الوظيفي
    _simple("REQTRN", "طلب تدريب", CAT_CAREER,
           ["branch_supervisor", "company_manager"], requires_physical_signature=False, visible_to_employee=True),
    _simple("REQTRF", "طلب نقل داخلي", CAT_CAREER,
           ["branch_supervisor", "company_manager"], produces_document=True,
           default_template_code="HRMS-PR-007"),
    _simple("REQPROMO", "طلب ترقية أو تعديل راتب", CAT_CAREER,
           ["branch_supervisor", "company_manager"], produces_document=True, visible_to_employee=True,
           default_template_code="HRMS-PR-008"),

    # العقود وإنهاء الخدمة
    _simple("REQCON", "تجديد عقد أو عدم تجديد", CAT_CONTRACTS,
           ["hr", "company_manager"], produces_document=True,
           default_template_code="HRMS-PR-006"),
    _simple("REQRESIGN", "طلب استقالة", CAT_CONTRACTS,
           ["company_manager", "hr"], produces_document=True, visible_to_employee=True,
           default_template_code="HRMS-PR-025"),
    _simple("REQEOS", "طلب احتساب وتسوية نهاية خدمة", CAT_CONTRACTS,
           ["hr", "accountant", "company_manager"], produces_document=True,
           default_template_code="HRMS-PR-028"),
    # V2.2 §13.10 (AC-10) + RW-14 — إخلاء الطرف بمهام متوازية لا سلسلة.
    # الجهات مستقلة بطبعها: كل واحدة تعرف عهدتها ولا تعرف عهدة غيرها، وترتيبها
    # بينها اصطناعي كان يجعل المالية تنتظر دور غيرها بلا سبب. والمندوب لا
    # تُنشأ له مهمة إلا إن كان للموظف وثائق حكومية فعلًا.
    {
        "code": "REQCLR", "name": "إخلاء طرف وتسليم عهدة", "category": CAT_CONTRACTS,
        "produces_document": True, "requires_physical_signature": True,
        "is_confidential": False, "visible_to_employee": False,
        "default_template_code": "HRMS-PR-026",
        "approval_chain_json": [
            {"order": 0, "kind": "parallel", "label": "إقرارات الجهات",
             "step_type": "VALIDATION", "produces_document": False,
             "parties": [
                 {"role": "accountant", "label": "المالية — العهد والالتزامات"},
                 {"role": "branch_supervisor", "label": "الفرع — عهدة الموقع"},
                 {"role": "delegate", "label": "المندوب — الوثائق الحكومية",
                  "when": {"field": "has_gov_documents", "truthy": True}},
             ]},
            {"order": 1, "label": "اعتماد شؤون الموظفين/القانونية", "role": "hr",
             "kind": "approval", "step_type": "DECISION", "produces_document": True},
        ],
    },

    # نماذج إدارية
    _simple("ADMEMP", "إضافة موظف جديد", CAT_ADMIN,
           ["hr", "company_manager"], requires_physical_signature=False),
    _simple("ADMACTUAL", "تعديل الراتب الفعلي أو مكان العمل الفعلي", CAT_ADMIN,
           ["company_manager", "accountant"], requires_physical_signature=False,
           default_template_code="HRMS-PR-009"),
    _simple("ADMDED", "إصدار خصم", CAT_ADMIN,
           ["hr", "accountant", "company_manager"], requires_physical_signature=False,
           default_template_code="HRMS-PR-012"),
    _simple("ADMVIO", "تسجيل مخالفة وظيفية", CAT_ADMIN,
           ["branch_supervisor", "hr", "company_manager"], requires_physical_signature=False,
           default_template_code="HRMS-PR-013"),
    _simple("ADMWARN", "إصدار إنذار", CAT_ADMIN,
           ["hr", "company_manager"], produces_document=True,
           default_template_code="HRMS-PR-010"),
    _simple("ADMTASK", "تكليف مندوب أو مهمة إدارية", CAT_ADMIN,
           ["company_manager", "delegate", "hr"], requires_physical_signature=False,
           default_template_code="HRMS-PR-019"),
    _simple("ADMMISS", "إشعار نقص مستندات", CAT_ADMIN,
           ["hr"], requires_physical_signature=False,
           default_template_code="HRMS-PR-020"),
    _simple("ADMLIC", "تجديد مستند شركة أو ترخيص", CAT_ADMIN,
           ["hr", "company_manager", "delegate"], produces_document=True,
           default_template_code="HRMS-PR-022"),
    _simple("ADMSIGN", "اعتماد وتوقيع إلكتروني", CAT_ADMIN,
           ["company_manager", "hr"], requires_physical_signature=False,
           default_template_code="HRMS-PR-040"),
    # طلب تغيير التوقيع: الموظف يرفع أول توقيع مباشرة من ملفه، أما تغييره بعد ذلك
    # فيمر من هنا. التوقيع دليل يُحتجّ به على كل مستند وُقِّع سابقًا، فتغييره
    # قرار يوثَّق بسبب ويعتمده HR لا إجراء ذاتي صامت.
    # QA-07 — visible_to_employee=True: النوع خدمة ذاتية بنص تعليقه أعلاه، لكنه
    # وُرِث الافتراضي False المخصّص لإجراءات ADM* الداخلية، فاختفى من "طلب جديد"
    # عند الموظف — وهو صاحبه الوحيد.
    _simple("REQSIG", "طلب تغيير التوقيع", CAT_ADMIN,
           ["hr"], requires_physical_signature=False, visible_to_employee=True),
]


def get_request_type(db: Session, company_id: int, code: str) -> models.RequestType | None:
    """يبحث عن نوع الطلب الخاص بالشركة أولًا ثم العام (company_id=None).

    توافقًا مع V1.5 Migration Registry: إن كان الكود المُمرَّر canonical جديد (WF-XXX أو
    OD-XXX) ولم يوجد في القاعدة (لأن seed لسه على الأكواد القديمة)، نبحث عن أي كود legacy
    مربوط بالـ canonical عبر LEGACY_REQUEST_ALIASES. هذا يسمح للعميل الحديث أن يمرر
    الكود الجديد فورًا دون كسر البيانات المخزنة."""
    def _lookup(c: str) -> models.RequestType | None:
        rt = db.scalar(
            select(models.RequestType).where(
                models.RequestType.code == c,
                models.RequestType.company_id == company_id,
                models.RequestType.is_active == True,  # noqa: E712
            )
        )
        if rt:
            return rt
        return db.scalar(
            select(models.RequestType).where(
                models.RequestType.code == c,
                models.RequestType.company_id.is_(None),
                models.RequestType.is_active == True,  # noqa: E712
            )
        )

    rt = _lookup(code)
    if rt:
        return rt
    # V1.5 forward-compat: canonical → legacy fallback
    from .v15_registry import LEGACY_REQUEST_ALIASES, CANONICAL_WORKFLOWS
    if code in CANONICAL_WORKFLOWS:
        for legacy_code, info in LEGACY_REQUEST_ALIASES.items():
            if info.get("canonical") == code:
                rt = _lookup(legacy_code)
                if rt:
                    return rt

    # STR-07 — كود معروف في السجل بلا صف نوع: يُحَل عبر مساره الـcanonical.
    #
    # ROOT CAUSE: أكواد مثل REQLV لها نموذج (form_schema) ولا صف RequestType.
    # فطلب أُنشئ بها يُقبل ثم **يعجز النظام عن حلّ نوعه**: يظهر بلا اسم ولا
    # سلسلة، ولا يستطيع أحد إغلاقه لأن مراحله غير معروفة. "قُبل ثم يتيم" أسوأ
    # من "رُفض عند الإنشاء" — الأول يترك أثًرا معطًلا في القاعدة.
    own = LEGACY_REQUEST_ALIASES.get(code, {}).get("canonical")
    if own:
        for legacy_code, info in LEGACY_REQUEST_ALIASES.items():
            if legacy_code != code and info.get("canonical") == own:
                rt = _lookup(legacy_code)
                if rt:
                    return rt
    return None


def _stage_applies(stage: dict, payload: dict | None,
                   policy: dict | None = None) -> bool:
    """هل تنطبق هذه المرحلة على هذا الطلب؟ (QA-10 + V2.2 §7/§13.8)

    المرحلة قد تحمل شرًطا:
      {"when": {"field": "travel_required", "truthy": true}}
      {"when": {"field": "leave_type", "equals": "annual"}}
      {"when": {"field": "amount", "policy_gt": "finance.extra_approval_threshold",
                "policy_field": "amount"}}   ← V2.2: الحد من السياسة لا من الكود

    بلا شرط ⇒ تنطبق دائًما، وهو سلوك كل المراحل القائمة.

    ``policy`` هو لقطة القواعد المحفوظة مع الطلب لا القراءة الحالية: تعديل حدٍّ
    بعد الإرسال لا يُضيف مرحلة لطلب قائم ولا يحذف منه (RW-18).
    """
    cond = stage.get("when")
    if not cond:
        return True
    if payload is None:
        # وصف النوع مجرًدا (بلا طلب): نعرض المراحل المشروطة لأنها جزء من التعريف
        return True
    value = (payload or {}).get(cond.get("field"))
    if "policy_gt" in cond:
        # حدّ من السياسة: المرحلة تُضاف فقط عند تجاوزه فعلًا (RW-06 مقابل RW-07)
        key = cond["policy_gt"]
        entry = (policy or {}).get(key) or {}
        limit = (entry.get("value") or {}).get(cond.get("policy_field", "amount"))
        if limit is None or float(limit) <= 0:
            # لا حدّ معتمَد ⇒ لا مرحلة إضافية. هذا هو السلوك القائم بالضبط،
            # فإدخال الآلية وحدها لا يغيّر شيًئا قبل اعتماد قيمة.
            return False
        try:
            return float(value or 0) > float(limit)
        except (TypeError, ValueError):
            return False
    if "equals" in cond:
        return value == cond["equals"]
    if "in" in cond:
        return value in (cond["in"] or [])
    if cond.get("truthy"):
        # "لا"/"false"/"0" تصل نًصا من نماذج الواجهة، فلا نعتمد صدق بايثون وحده
        return bool(value) and str(value).strip().lower() not in ("false", "0", "no", "لا")
    return True


def _chain(rt: models.RequestType, req: models.Request | None = None) -> list[dict]:
    """مراحل الطلب — مُرشَّحة بمحتواه لا قالًبا ثابًتا (QA-10).

    ROOT CAUSE: كانت تُعيد approval_chain_json كما هو، فمرحلة "إذن مغادرة
    البلاد (المندوب)" تظهر في كل طلب إجازة ولو كانت إجازة داخل الكويت — يقف
    الطلب عند المندوب بلا سبب.
    """
    stages = sorted(rt.approval_chain_json or [], key=lambda s: s.get("order", 0))
    payload = (req.payload_json if req is not None else None)
    # لقطة السياسة المحفوظة مع الطلب لا القراءة الحالية (RW-18)
    policy = (getattr(req, "policy_snapshot_json", None) or {}) if req is not None else {}
    return [s for s in stages if _stage_applies(s, payload, policy)]


def _warn_unassigned_stage(db: Session, req: models.Request,
                           emp: models.Employee | None) -> None:
    """QA-02 — مرحلة بلا معتمِد مؤهَّل: نُنبّه الإدارة بدل تمريرها للمدير بصمت.

    السبب دائًما بيانات لا منطق: الموظف بلا فرع، أو الفرع بلا مسؤول مربوط في
    BranchSupervisor. المهمة تحمل ما يكفي لإصلاحه.
    """
    why = ("الموظف غير مرتبط بفرع" if not (emp and emp.branch_id)
           else "لا يوجد مسؤول مرتبط بفرع الموظف")
    for u in users_by_role(db, req.company_id, ["hr", "company_manager"]):
        create_task(
            db, company_id=req.company_id, type="config_gap",
            assignee_user_id=u.id,
            title="طلب متوقف: لا مسؤول فرع لهذه المرحلة",
            detail=(f"طلب #{req.id} — {why}. اربط مسؤول الفرع بفرع الموظف "
                    f"ليصله الطلب."),
            related_entity_type="request", related_entity_id=req.id,
            dedup_key=f"stage_unassigned:{req.id}", severity="critical",
        )


def resolve_stage_approvers(db: Session, req: models.Request, stage: dict) -> list[models.User]:
    """يحدد المستخدمين المعنيين بمرحلة معيّنة حسب الدور (وفرع العامل).

    V2.2 §8 — المسؤول المباشر الفعلي:
    إن كان role="direct_manager"، نستخدم Employee.direct_manager_id (الشخص الفعلي)
    بدلًا من الافتراض بأنه "company_manager". هذا يتيح:
      - محاسب مسؤول عن محاسبين آخرين
      - موظف يمكن أن يكون مسؤولًا عن آخرين
      - عند غيابه نسقط إلى Branch Supervisor ثم Company Manager
    """
    role = stage.get("role")
    if role == "direct_manager":
        emp = db.get(models.Employee, req.employee_id)
        if emp and emp.direct_manager_id:
            mgr_emp = db.get(models.Employee, emp.direct_manager_id)
            if mgr_emp:
                mgr_user = db.scalar(select(models.User).where(
                    models.User.employee_id == mgr_emp.id, models.User.is_active.is_(True)))
                if mgr_user:
                    from .delegation import expand_approvers_with_delegates
                    return expand_approvers_with_delegates(db, [mgr_user], req.company_id)
        # لا مسؤول مباشر → سقوط إلى branch_supervisor أو company_manager
        stage_sup = {**stage, "role": "branch_supervisor"}
        return resolve_stage_approvers(db, req, stage_sup)
    if role == "branch_supervisor":
        emp = db.get(models.Employee, req.employee_id)
        if emp and emp.branch_id:
            sup_ids = [
                bs.user_id for bs in db.scalars(
                    select(models.BranchSupervisor).where(
                        models.BranchSupervisor.branch_id == emp.branch_id
                    )
                ).all()
            ]
            users = [db.get(models.User, uid) for uid in sup_ids]
            users = [u for u in users if u and u.is_active]
            if users:
                # V1.5 Phase 3: يوسّع القائمة لتشمل أي مفوَّض إليهم نشطين
                from .delegation import expand_approvers_with_delegates
                return expand_approvers_with_delegates(db, users, req.company_id)
        # QA-01/QA-02 — لا سقوط صامت للمدير.
        #
        # ROOT CAUSE الحقيقي للبندين: كان غياب صف BranchSupervisor للفرع (أو
        # غياب branch_id عن الموظف) يجعل مرحلة "مسؤول الفرع" مرحلةَ المدير
        # **شرًعا**. فالمدير يعتمدها لأنه صار معتمِدها فعًلا، ومسؤول الفرع لا
        # يراها لأنه غير مربوط. إزالة التجاوز الصريح من can_decide لم تمسّ هذا
        # المسار، ولم تكشفه الاختبارات لأن بيانات البذر فيها صفوف الربط
        # والإنتاج بلا صفوف.
        #
        # القاعدة الآن: مرحلة بلا معتمِد مؤهَّل تبقى بلا معتمِد، وتُنبَّه الإدارة
        # لإصلاح الربط. طلب عالق ظاهر أفضل من طلب يعتمده من ليس صاحبه.
        emp = db.get(models.Employee, req.employee_id)
        _warn_unassigned_stage(db, req, emp)
        return []
    if not role:
        return []
    base = users_by_role(db, req.company_id, [role])
    from .delegation import expand_approvers_with_delegates
    return expand_approvers_with_delegates(db, base, req.company_id)


def is_stage_approver(db: Session, req: models.Request, user: models.User,
                      stage: dict) -> bool:
    """هل هذا المستخدم من معتمِدي هذه المرحلة فعلًا؟ — بلا أي تجاوز إداري.

    المصدر الوحيد لهذا السؤال: يستدعيه مسار القرار و can_decide وصندوق
    "بانتظار موافقتي" معًا. وضع القاعدة في أحدها دون البقية هو بالضبط نمط
    "موضعان يصفان قاعدة واحدة" الذي أنتج نصف أعطال هذا النظام.
    """
    if user.company_id != req.company_id:
        return False
    if stage.get("kind") == "parallel":
        # V2.2 §13.10 — الجهة معتمِدة نصيبها وحده، ومرة واحدة
        parties = {p["role"] for p in applicable_parties(stage, req.payload_json)}
        if user.role not in parties:
            return False
        return user.role not in _party_decisions(db, req, req.current_stage)
    return any(u.id == user.id for u in resolve_stage_approvers(db, req, stage))


def may_override(db: Session, user: models.User,
                 rt: models.RequestType | None = None) -> bool:
    """هل يملك صلاحية التجاوز الإداري؟ — الطلبات السرّية لا تُتجاوَز إطلاقًا.

    V2.2 §13.5 (AC-05): super_admin استثناء معكوس. has_permission تعيد له True
    مطلًقا، فكان يملك التجاوز في كل لحظة ويعتمد أي مرحلة عمل بلا أن يطلبها أحد
    ولا أن ينتبه إليها أحد — حساب تقني صار معتمًِدا تجارًيا بحكم الأمر الواقع.
    يحتاج الآن نافذة Break-glass سارية: بسبب مكتوب ومدة تنتهي وحدها وسجل.

    المنع الكامل ليس حًلا: حين يتعطّل الإسناد (موظف بلا فرع، معتمِد غادر) يقف
    العمل ولا مخرج. فالتجاوز يبقى ممكًنا لكنه يصير حدًثا لا حالة دائمة.
    """
    if rt is not None and rt.is_confidential:
        return False
    if user.role == "super_admin":
        from .break_glass import active_session
        return active_session(db, user.id) is not None
    from .deps import get_user_perms
    from .permissions import has_permission
    return has_permission(user.role, get_user_perms(user, db), "override_approval")


def can_decide(db: Session, req: models.Request, user: models.User, stage: dict,
              rt: models.RequestType | None = None) -> bool:
    """QA-01/QA-02 — من يعتمد هذه المرحلة.

    ROOT CAUSE: كان هنا تجاوز ضمني يعيد True لكل company_manager وcompany_owner
    في أي مرحلة (وسطر مماثل لـsuper_admin). النتيجة وجهان لعملة واحدة:
      - QA-01: المدير يعتمد مراحل ليست له، ويعتمد متسلسًلا بحسابه وحده.
      - QA-02: صندوق "بانتظار موافقتي" مبني على هذه الدالة نفسها، فامتلأ صندوق
        المدير بكل الطلبات بينما لا يُختبر مسار مسؤول الفرع أصلًا.

    القاعدة الآن: معتمِد المرحلة الفعلي فقط. والتجاوز الإداري — إن لزم — صلاحية
    مسمّاة (override_approval) لا تُمنح افتراضًا لأي دور، ويسجّلها مسار القرار
    في التدقيق. الطلبات السرّية لا تقبل تجاوًزا بحال.
    """
    # V2.2 §13.6 (AC-06) — لا اعتماد ذاتي لأي دور.
    #
    # الحالة الواضحة: طلب يخصّ الشخص نفسه. أن يكون HR معتمِد مرحلة لا يعني أن
    # يعتمد إجازته هو؛ ولا المحاسب سلفته. القاعدة تسبق كل شيء آخر — حتى
    # override_approval — لأن التجاوز الإداري صُمّم لحلّ عُطل في الإسناد، لا
    # ليمنح صاحب الطلب سلطة على طلبه.
    if user.employee_id and req.employee_id == user.employee_id:
        return False

    if is_stage_approver(db, req, user, stage):
        return True
    if user.company_id != req.company_id:
        return False
    return may_override(db, user, rt)


def _employee_name(db: Session, req: models.Request) -> str:
    emp = db.get(models.Employee, req.employee_id)
    return emp.name if emp else f"#{req.employee_id}"


def create_request(db: Session, employee: models.Employee, requester: models.User,
                   rt: models.RequestType, payload: dict) -> models.Request:
    # V2.2 §13.8 (AC-08) + RW-18 — لقطة القواعد الفاعلة لحظة الإرسال.
    # المراحل المشروطة بحدّ تُحسب من هذه اللقطة لا من القراءة الحالية، فتعديل
    # حدٍّ بعد الإرسال لا يُضيف مرحلة لطلب قائم ولا يحذف منه.
    from . import policy as policy_service
    snapshot = policy_service.snapshot(
        db, employee.company_id,
        [s.get("when", {}).get("policy_gt") for s in (rt.approval_chain_json or [])
         if isinstance(s.get("when"), dict) and s["when"].get("policy_gt")],
    )
    req = models.Request(
        company_id=employee.company_id, employee_id=employee.id,
        requester_user_id=requester.id, request_type_code=rt.code,
        payload_json=payload, status="pending", current_stage=0,
        policy_snapshot_json=snapshot or None,
    )
    db.add(req)
    db.flush()
    enter_stage(db, req, rt)
    db.commit()
    db.refresh(req)
    return req


def applicable_parties(stage: dict, payload: dict | None) -> list[dict]:
    """V2.2 §13.10 (AC-10) — الجهات المنطبقة على هذا الطلب وحدها.

    ROOT CAUSE لإخلاء الطرف: كان سلسلة متتابعة، فتنتظر المالية دور تقنية
    المعلومات وإن كان الموظف لا يحمل أي عهدة تقنية. الجهات مستقلة بطبعها: كل
    واحدة تعرف عهدتها ولا تعرف عهدة غيرها، وترتيبها بينها اصطناعي.

    ``when`` لكل جهة يُقيَّم بنفس مُقيِّم شروط المراحل، فجهة لا تنطبق لا تُنشأ
    لها مهمة أصلًا — لا تُنشأ ثم تُغلق تلقائًيا (ذلك يُربك السجل ويوهم بإجراء
    لم يقع).
    """
    out = []
    for party in stage.get("parties") or []:
        cond = party.get("when")
        if cond and not _stage_applies({"when": cond}, payload):
            continue
        out.append(party)
    return out


def _party_decisions(db: Session, req: models.Request, stage_order: int) -> set[str]:
    """أدوار الجهات التي حسمت هذه المرحلة المتوازية."""
    rows = db.scalars(select(models.RequestApproval).where(
        models.RequestApproval.request_id == req.id,
        models.RequestApproval.stage_order == stage_order,
        models.RequestApproval.decision == "approved",
    )).all()
    return {r.approver_role for r in rows if r.approver_role}


def parallel_stage_complete(db: Session, req: models.Request, stage: dict) -> bool:
    """هل حسمت كل الجهات المنطبقة؟ (All-of لا Any-of).

    الإغلاق قبل اكتمالها يعني مخالصة نهائية بينما جهة لم تُقرّ بعد — وهو ما
    يمنعه DOC-12 صراحًة.
    """
    needed = {p["role"] for p in applicable_parties(stage, req.payload_json)}
    return needed and needed <= _party_decisions(db, req, req.current_stage)


def enter_stage(db: Session, req: models.Request, rt: models.RequestType) -> None:
    """يهيّئ المرحلة الحالية: ضبط الحالة وإنشاء المهام للمستلِمين."""
    chain = _chain(rt, req)
    if req.current_stage >= len(chain):
        return _finalize(db, req)
    stage = chain[req.current_stage]
    kind = stage.get("kind", "approval")
    name = _employee_name(db, req)
    label = stage.get("label", "")

    if kind == "parallel":
        # مهمة لكل جهة منطبقة — كل جهة ترى مهمتها وحدها ولا تنتظر غيرها
        req.status = "pending"
        for party in applicable_parties(stage, req.payload_json):
            for u in users_by_role(db, req.company_id, [party["role"]]):
                notify_from_template(
                    db, code="NTF-033", assignee_user_id=u.id, company_id=req.company_id,
                    context={"request_type": rt.name, "employee_name": name,
                             "stage_label": party.get("label") or label},
                    related_entity_type="request", related_entity_id=req.id,
                    severity="info",
                    dedup_key=f"req_par:{req.id}:{req.current_stage}:{party['role']}:u{u.id}",
                )
    elif kind in ("approval", "hr_review"):
        req.status = "pending"
        for u in resolve_stage_approvers(db, req, stage):
            notify_from_template(
                db, code="NTF-033", assignee_user_id=u.id, company_id=req.company_id,
                context={"request_type": rt.name, "employee_name": name, "stage_label": label},
                related_entity_type="request", related_entity_id=req.id,
                severity="info", dedup_key=f"req_stage:{req.id}:{req.current_stage}:u{u.id}",
            )
    elif kind == "delegate_exit":
        req.status = "awaiting_delegate"
        p = req.payload_json or {}
        for u in users_by_role(db, req.company_id, ["delegate"]):
            notify_from_template(
                db, code="NTF-065", assignee_user_id=u.id, company_id=req.company_id,
                context={"task": f"إجراءات إذن مغادرة البلاد لـ{name} "
                                 f"({p.get('start_date','')} إلى {p.get('end_date','')})",
                        "request_no": req.id},
                related_entity_type="request", related_entity_id=req.id,
                severity="warning", dedup_key=f"req_exit:{req.id}",
            )
    elif kind == "pickup":
        req.status = "ready_for_pickup"
        # يُنفّذ الطلب الدور المحدَّد في المرحلة (hr افتراضيًا، أو accountant للسلف/القروض)
        executor = stage.get("role") or "hr"
        for u in users_by_role(db, req.company_id, [executor]):
            notify_from_template(
                db, code="NTF-039", assignee_user_id=u.id, company_id=req.company_id,
                context={"request_type": f"{rt.name} — {name}"},
                related_entity_type="request", related_entity_id=req.id,
                dedup_key=f"req_pickup:{req.id}",
            )
        _notify_employee_from_template(
            db, req, code="NTF-039", context={"request_type": rt.name},
            dedup_key=f"req_pickup_emp:{req.id}",
        )

    # إشعار العامل بالتقدّم
    _notify_employee_from_template(
        db, req, code="NTF-034", context={"request_type": rt.name, "stage_label": label},
        dedup_key=f"req_progress:{req.id}:{req.current_stage}",
    )


def _notify_employee_from_template(db: Session, req: models.Request, code: str,
                                   context: dict | None = None, **kwargs) -> None:
    """يُشعر العامل نفسه (خدمة ذاتية) عبر قالب مسمّى من الكتالوج — إن كان له حساب."""
    user = db.scalar(select(models.User).where(models.User.employee_id == req.employee_id))
    if user:
        notify_from_template(
            db, code=code, assignee_user_id=user.id, company_id=req.company_id,
            context=context, related_entity_type="request", related_entity_id=req.id, **kwargs,
        )


def _close_open_tasks(db: Session, req: models.Request) -> None:
    """يغلق تلقائيًا أي مهام مفتوحة/قيد التنفيذ مرتبطة بطلب وصل لحالة نهائية
    (رُفض/أُلغي/اكتمل) — كانت تبقى «مفتوحة» في صندوق المهام رغم انتهاء الطلب
    المرتبطة به (QA-P1-TASK-01). P1-#18 — يشمل in_progress كمان."""
    open_tasks = db.scalars(select(models.Task).where(
        models.Task.related_entity_type == "request",
        models.Task.related_entity_id == req.id,
        models.Task.status.in_(("open", "in_progress")),
    )).all()
    for t in open_tasks:
        # TSK-03 — الإشعار خبر لا إجراء: إغلاقه مع المهام يمحو إخطار
        # النتيجة نفسه، فيبقى الموظف لا يعرف ماذا جرى بطلبه.
        if is_notification(t.type):
            continue
        t.status = "dismissed"
        t.completed_at = datetime.now(timezone.utc)


def decide(db: Session, req: models.Request, user: models.User, decision: str,
           note: str | None, rt: models.RequestType) -> models.Request:
    chain = _chain(rt, req)
    stage = chain[req.current_stage]
    approval = models.RequestApproval(
        request_id=req.id, stage_order=req.current_stage,
        stage_label=stage.get("label", ""), approver_role=user.role,
        approver_user_id=user.id, decision=decision, note=note,
    )
    db.add(approval)
    # autoflush=False على مستوى الجلسة (database.py) — بدون flush صريح هنا لا يرى استعلام
    # generate_document() اعتماد هذه المرحلة نفسها، فتخرج آخر مرحلة (المكتمِلة للمستند)
    # غائبة عن سلسلة الاعتماد داخل مستندها نفسه (P0-05).
    db.flush()

    if decision == "rejected":
        req.status = "rejected"
        req.closed_at = datetime.now(timezone.utc)
        _notify_terminated(db, req, rt, "rejected", user, note)
        _close_open_tasks(db, req)
        db.commit()
        db.refresh(req)
        return req

    if decision == "returned":
        # إرجاع للمقدّم للتصحيح — بديل عن الرفض النهائي في المرحلتين الأولى والثانية
        # (QA-P2-WF-03): يوثّق سبب الإرجاع بوضوح ويترك للموظف تقديم طلب مصحَّح.
        req.status = "returned"
        req.closed_at = datetime.now(timezone.utc)
        _notify_terminated(db, req, rt, "returned", user, note)
        _close_open_tasks(db, req)
        db.commit()
        db.refresh(req)
        return req

    # اعتماد
    kind = stage.get("kind", "approval")
    if kind == "hr_review":
        # يولّد المستند وينتقل لحالة انتظار التوقيع (لا يتقدّم حتى رفع الموقّع)
        generate_document(db, req, rt, kind="generated_pdf", actor=user)
        req.status = "awaiting_signature"
        _notify_employee_from_template(
            db, req, code="NTF-038", context={"scheduled_at": "أقرب وقت ممكن"},
            dedup_key=f"req_sign:{req.id}",
        )
        db.commit()
        db.refresh(req)
        return req

    # V2.2 §13.10 (AC-10) — مرحلة متوازية: الجهة تحسم نصيبها ولا تتقدّم
    # المرحلة إلا باكتمال كل الجهات المنطبقة (All-of). الإغلاق قبل ذلك يعني
    # مخالصة نهائية وجهة لم تُقرّ بعد — وهو ما يمنعه DOC-12 صراحًة.
    if stage.get("kind") == "parallel" and not parallel_stage_complete(db, req, stage):
        db.commit()
        db.refresh(req)
        return req

    if stage.get("produces_document"):
        generate_document(db, req, rt, kind="generated_pdf", actor=user)

    _advance(db, req, rt)
    db.commit()
    db.refresh(req)
    return req


def upload_signed_scan_done(db: Session, req: models.Request, rt: models.RequestType) -> None:
    """يُستدعى بعد رفع نسخة موقّعة في مرحلة hr_review → يتقدّم الطلب."""
    _advance(db, req, rt)
    db.commit()


def upload_exit_permit_done(db: Session, req: models.Request, rt: models.RequestType) -> None:
    """يُستدعى بعد رفع إذن المغادرة في مرحلة delegate_exit → يكتمل الطلب."""
    name = _employee_name(db, req)
    _notify_employee_from_template(
        db, req, code="NTF-018", context={"employee_name": name},
        dedup_key=f"req_exit_ready:{req.id}",
    )
    _advance(db, req, rt)
    db.commit()


def mark_pickup_received(db: Session, req: models.Request, rt: models.RequestType) -> None:
    _advance(db, req, rt)
    db.commit()


def _decided_by(db: Session, req: models.Request, stage_order: int) -> int | None:
    """من اتخذ قرار هذه المرحلة فعلًا (آخر قرار مسجَّل عليها)."""
    row = db.scalar(select(models.RequestApproval).where(
        models.RequestApproval.request_id == req.id,
        models.RequestApproval.stage_order == stage_order,
    ).order_by(models.RequestApproval.id.desc()))
    return getattr(row, "approver_user_id", None) if row else None


def _skip_duplicate_approver(db: Session, req: models.Request,
                             rt: models.RequestType) -> bool:
    """V2.2 §13.9 (AC-09) + RW-09 — تتخطّى المرحلة إن كان معتمِدها هو نفسه من
    اعتمد السابقة، وكان وحده معتمِدها.

    ROOT CAUSE: في شركة صغيرة يجمع شخص واحد دورين متتاليين في السلسلة، فيصله
    الطلب مرتين ليضغط "اعتماد" على قراره هو. ذلك ليس مراجعة مستقلة بل إيهام
    بها: خطوتان في السجل وقرار واحد في الواقع.

    الشرط "وحده": لو كان للمرحلة معتمِدون آخرون فالمراجعة المستقلة ما زالت
    ممكنة، فلا نتخطّاها — نتركها لهم. والتخطّي يُسجَّل بسببه حتى لا يبدو
    القرار وقد قفز مرحلة بلا تفسير.
    """
    chain = _chain(rt, req)
    if req.current_stage <= 0 or req.current_stage >= len(chain):
        return False
    previous = _decided_by(db, req, req.current_stage - 1)
    if not previous:
        return False
    approvers = resolve_stage_approvers(db, req, chain[req.current_stage])
    ids = {u.id for u in approvers}
    if ids != {previous}:
        return False

    stage = chain[req.current_stage]
    db.add(models.RequestApproval(
        request_id=req.id, stage_order=req.current_stage,
        stage_label=stage.get("label") or stage.get("role") or "",
        approver_role=stage.get("role"), approver_user_id=previous,
        decision="skipped",
        note="تخطٍّ آلي: معتمِد هذه المرحلة هو نفسه معتمِد السابقة ولا معتمِد غيره "
             "(V2.2 §13.9) — مراجعة الشخص لقراره ليست مراجعة مستقلة.",
    ))
    # الجلسة autoflush=False: بلا غسل صريح لا يرى _decided_by هذا الصف في
    # الدورة التالية، فتنكسر التخطّيات المتتالية (شخص يجمع ثلاثة أدوار).
    db.flush()
    return True


def _advance(db: Session, req: models.Request, rt: models.RequestType) -> None:
    req.current_stage += 1
    # قد تتوالى مراحل لنفس الشخص، فنتخطّى ما دام الشرط قائًما
    while _skip_duplicate_approver(db, req, rt):
        req.current_stage += 1
    if req.current_stage >= len(_chain(rt, req)):
        _finalize(db, req)
    else:
        enter_stage(db, req, rt)


# الإجازة السنوية وحدها تُخصم من الرصيد؛ المرضية والطارئة وبدون راتب لها
# أحكامها الخاصة ولا تنقص الرصيد السنوي.
LEAVE_TYPES_DEDUCTING_BALANCE = {"annual"}


def _as_date(v):
    """حمولة الطلب تحمل التواريخ نصًّا (JSON)، وأعمدة Leave من نوع Date."""
    if not v or isinstance(v, date):
        return v or None
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def _apply_leave(db: Session, req: models.Request) -> tuple[bool, str]:
    """يسجّل الإجازة المعتمَدة ويخصم رصيدها.

    طلب الإجازة كان يمرّ بكل مراحل الاعتماد ثم يُغلق بلا أثر: لا صف Leave
    يُنشأ، ولا annual_leave_balance ينقص. فكان الموظف يستهلك إجازاته والرصيد
    ثابت على 30 إلى الأبد.

    الخصم يُقيَّد في leave_ledger بالرصيد قبله وبعده، فالرقم قابل للتفسير
    وإعادة البناء. ورصيد غير كافٍ يُفشل التطبيق (apply_failed) بدل أن يُنشئ
    رصيدًا سالبًا بصمت — تمامًا كما يفعل تصحيح الحضور عند تعذّر التطبيق.
    """
    p = req.payload_json or {}
    emp = db.get(models.Employee, req.employee_id)
    if not emp:
        return False, "الموظف غير موجود"

    leave_type = (p.get("leave_type") or "annual").strip()
    try:
        days = float(p.get("days") or 0)
    except (TypeError, ValueError):
        return False, f"عدد أيام غير صالح: {p.get('days')!r}"
    if days <= 0:
        return False, "عدد أيام الإجازة يجب أن يكون أكبر من صفر"

    # حارس التكرار: إعادة التطبيق على نفس الطلب تخصم مرتين
    already = db.scalar(select(models.Leave).where(models.Leave.request_id == req.id))
    if already:
        return True, f"الإجازة مسجَّلة مسبًقا لهذا الطلب (#{already.id}) — لم يُخصم مرتين"

    deducts = leave_type in LEAVE_TYPES_DEDUCTING_BALANCE
    before = float(emp.annual_leave_balance or 0)
    if deducts and days > before:
        return False, (f"الرصيد لا يكفي: المطلوب {days:g} يوم والمتاح {before:g} يوم")

    leave = models.Leave(
        company_id=req.company_id, employee_id=emp.id, request_id=req.id,
        leave_type=leave_type, start_date=_as_date(p.get("start_date")),
        end_date=_as_date(p.get("end_date")), days=days, status="approved",
    )
    db.add(leave)
    db.flush()  # نحتاج leave.id للقيد

    after = before - days if deducts else before
    if deducts:
        emp.annual_leave_balance = after
    db.add(models.LeaveLedger(
        company_id=req.company_id, employee_id=emp.id,
        kind="deduction" if deducts else "record",
        days=days, balance_before=before, balance_after=after,
        leave_type=leave_type, request_id=req.id, leave_id=leave.id,
        note=(f"إجازة معتمَدة من {p.get('start_date') or '—'} "
              f"إلى {p.get('end_date') or '—'}"),
    ))

    if deducts:
        return True, f"خُصم {days:g} يوم — الرصيد {before:g} ← {after:g}"
    return True, f"سُجّلت إجازة {leave_type} ({days:g} يوم) بلا خصم من الرصيد السنوي"


def _apply_attendance_correction(db: Session, req: models.Request) -> tuple[bool, str]:
    """PILOT-P0-4 — يطبّق تعديل الحضور المعتمَد فعليًا على AttendanceRecord.

    الحمولة المتوقعة (اختياريًا: الحمولة المرنة تُقبل، والحقول اللي تنقص لا تطبّق):
        date          : تاريخ اليوم المطلوب تصحيحه (YYYY-MM-DD)
        check_in      : وقت الحضور الجديد (HH:MM)
        check_out     : وقت الانصراف الجديد (HH:MM)
        reason        : سبب التصحيح (للـaudit)

    يعيد (applied, note). لو applied=False، الطلب يبقى في IN_EXECUTION مع علامة
    الفشل ولا يُعتبَر Completed — يمنع التقفيل الوهمي.
    """
    from datetime import datetime as _dt, date as _date

    payload = req.payload_json or {}
    day_str = payload.get("date") or payload.get("attendance_date")
    if not day_str:
        return False, "الحمولة تفتقد حقل التاريخ (date)"
    try:
        day = _date.fromisoformat(str(day_str))
    except ValueError:
        return False, f"صيغة التاريخ غير صحيحة: {day_str}"

    # نجد سجل الحضور: نفس الموظف ونفس اليوم
    from sqlalchemy import and_
    day_start = _dt.combine(day, _dt.min.time())
    day_end = _dt.combine(day, _dt.max.time())
    rec = db.scalar(
        select(models.AttendanceRecord).where(and_(
            models.AttendanceRecord.employee_id == req.employee_id,
            models.AttendanceRecord.check_in_at >= day_start,
            models.AttendanceRecord.check_in_at <= day_end,
        ))
    )

    new_ci = payload.get("check_in") or payload.get("new_check_in")
    new_co = payload.get("check_out") or payload.get("new_check_out")

    def _combine(hhmm: str) -> _dt | None:
        try:
            h, m = str(hhmm).split(":")[:2]
            return _dt.combine(day, _dt.min.time().replace(hour=int(h), minute=int(m)))
        except (ValueError, AttributeError):
            return None

    changes: list[str] = []
    if rec is None:
        # لا سجل — ننشئه لو فيه على الأقل check_in
        ci = _combine(new_ci) if new_ci else None
        if not ci:
            return False, "لا يوجد سجل حضور لليوم المحدد ولم يُقدَّم check_in لإنشائه"
        rec = models.AttendanceRecord(
            company_id=req.company_id, employee_id=req.employee_id,
            check_in_at=ci, check_out_at=_combine(new_co) if new_co else None,
        )
        db.add(rec)
        changes.append(f"إنشاء سجل: in={ci}")
    else:
        if new_ci:
            new_ci_dt = _combine(new_ci)
            if new_ci_dt and new_ci_dt != rec.check_in_at:
                changes.append(f"check_in: {rec.check_in_at} → {new_ci_dt}")
                rec.check_in_at = new_ci_dt
        if new_co:
            new_co_dt = _combine(new_co)
            if new_co_dt and new_co_dt != rec.check_out_at:
                changes.append(f"check_out: {rec.check_out_at} → {new_co_dt}")
                rec.check_out_at = new_co_dt

    if not changes:
        return False, "لم يُطلَب أي تعديل فعلي (نفس القيم القديمة)"

    return True, "; ".join(changes)


def _finalize(db: Session, req: models.Request) -> None:
    rt = get_request_type(db, req.company_id, req.request_type_code)

    # P0-#6 — Apply Effect atomicity:
    # - Success → status="completed", current_stage stays at len(chain) (past-end).
    # - Failure → status="apply_failed" (distinct status), current_stage rolled back to
    #   len(chain)-1 (last approved stage) لتجنب حالة تناقضية:
    #   "current_stage=2/2 + status=returned + all approvals done".
    #   الحالة الجديدة "apply_failed" واضحة للـUI والـaudit — مش returned (اللي بيرجع
    #   للـsubmitter لتعديل بيانات) ولا rejected (اللي بيقفل الطلب).
    chain_len = len(_chain(rt, req)) if rt else 0

    # PILOT-P0-4 — تصحيح الحضور: نطبّق الأثر الفعلي قبل ما نعتبر الطلب Completed
    # وطلب الإجازة مثله: كان يكتمل بلا أثر — لا سجل إجازة ولا خصم رصيد.
    # WF-09 — بقية الأنواع التي تغيّر بيانات الموظف (جواز، بطاقة، اتصال،
    # ترقية، وردية، نقل) كانت تُغلق "مكتملة" بلا أثر. سجلّها التصريحي في
    # request_effects.FIELD_EFFECTS وتدخل من نفس الباب: نفس الذرّية ونفس
    # مسار apply_failed، فلا يوجد طريقان لتطبيق أثر.
    from .request_effects import FIELD_EFFECTS, apply_field_effect

    _effect = {"REQATT": _apply_attendance_correction,
               "REQLV": _apply_leave, "leave": _apply_leave}.get(req.request_type_code)
    if _effect is None and req.request_type_code in FIELD_EFFECTS:
        _effect = apply_field_effect
    if _effect:
        applied, note = _effect(db, req)
        if not applied:
            # roll back current_stage — نجعله يشير للمرحلة الأخيرة اللي اعتُمدت فعلاً
            # (بدل من len(chain) = past-end الحالة التناقضية)
            if chain_len > 0:
                req.current_stage = chain_len - 1
            req.status = "apply_failed"
            req.closed_at = None  # ما نغلقه — يحتاج إجراء
            db.add(models.RequestApproval(
                request_id=req.id, stage_order=req.current_stage,
                stage_label="فشل تطبيق التصحيح", approver_role="system",
                decision="apply_failed", note=note,
            ))
            # P0-#7 — audit apply failure كسطر واضح مربوط بالـrequest
            db.add(models.AuditLog(
                company_id=req.company_id, user_id=None,
                action="request_apply_failed", entity_type="request",
                entity_id=req.id, detail=f"reason: {note}",
                correlation_id=f"req:{req.id}",
                after_json={"status": req.status, "current_stage": req.current_stage,
                          "reason": note},
            ))
            _notify_employee_from_template(
                db, req, code="NTF-035",
                context={"request_type": rt.name if rt else req.request_type_code,
                         "reason": note},
                dedup_key=f"req_att_fail:{req.id}",
            )
            # الإدارة (HR) تحتاج task ثانية لمعرفة إن فيه إجراء يدوي مطلوب
            for u in users_by_role(db, req.company_id, ["hr", "company_manager"]):
                create_task(
                    db, company_id=req.company_id, type="apply_failed",
                    assignee_user_id=u.id,
                    title=f"فشل التطبيق بعد الاعتماد: {rt.name if rt else req.request_type_code}",
                    detail=f"طلب #{req.id} — السبب: {note}",
                    related_entity_type="request", related_entity_id=req.id,
                    dedup_key=f"req_apply_failed:{req.id}", severity="critical",
                )
            _close_open_tasks(db, req)
            return
        # نجح التطبيق — نسجّل ملاحظة قبل/بعد كـ approval trail
        db.add(models.RequestApproval(
            request_id=req.id, stage_order=req.current_stage,
            stage_label=("تطبيق تصحيح الحضور" if req.request_type_code == "REQATT"
                         else FIELD_EFFECTS[req.request_type_code][0]
                         if req.request_type_code in FIELD_EFFECTS
                         else "تسجيل الإجازة وخصم الرصيد"),
            approver_role="system", decision="approved", note=note,
        ))
        # P0-#7 — audit apply success
        db.add(models.AuditLog(
            company_id=req.company_id, user_id=None,
            action="request_apply_success", entity_type="request",
            entity_id=req.id, detail=note,
            correlation_id=f"req:{req.id}",
        ))

    req.status = "completed"
    req.closed_at = datetime.now(timezone.utc)
    # P0-#7 — audit completion (transition to terminal state)
    db.add(models.AuditLog(
        company_id=req.company_id, user_id=None,
        action="request_completed", entity_type="request",
        entity_id=req.id,
        detail=f"{rt.code if rt else req.request_type_code}",
        correlation_id=f"req:{req.id}",
        after_json={"status": "completed", "closed_at": req.closed_at.isoformat()},
    ))
    _notify_employee_from_template(
        db, req, code="NTF-037", context={"request_type": rt.name if rt else req.request_type_code},
        dedup_key=f"req_done:{req.id}",
    )
    # V2.2 §20 — إشعار "جاهز للطباعة" للمسؤول عن طباعة المستندات (HR/الأرشيف)
    # عند وجود مستند رسمي مُوَلَّد ينتظر الطباعة والحفظ في الملف الورقي.
    if rt and getattr(rt, "produces_document", False):
        for u in users_by_role(db, req.company_id, ["hr"]):
            create_task(
                db, company_id=req.company_id, type="ready_to_print",
                assignee_user_id=u.id,
                title=f"جاهز للطباعة والحفظ: {rt.name}",
                detail=f"طلب #{req.id} — الموظف: {_employee_name(db, req)}",
                related_entity_type="request", related_entity_id=req.id,
                dedup_key=f"req_ready_print:{req.id}", severity="info",
                template_code="NTF-040",
            )
    _close_open_tasks(db, req)


def cancel(db: Session, req: models.Request, user: models.User, note: str | None,
           rt: models.RequestType) -> models.Request:
    """إلغاء/رفض من المدير العام في أي مرحلة → إشعار كل الأطراف."""
    if user.role not in CANCEL_ROLES:
        raise PermissionError("الإلغاء من صلاحية المدير العام / الإدارة العليا فقط")
    req.status = "cancelled"
    req.closed_at = datetime.now(timezone.utc)
    db.add(models.RequestApproval(
        request_id=req.id, stage_order=req.current_stage, stage_label="إلغاء المدير العام",
        approver_role=user.role, approver_user_id=user.id, decision="rejected", note=note,
    ))
    _notify_terminated(db, req, rt, "cancelled", user, note)
    _close_open_tasks(db, req)
    db.commit()
    db.refresh(req)
    return req


def resubmit(db: Session, req: models.Request, user: models.User, updated_payload: dict | None,
             rt: models.RequestType) -> models.Request:
    """إعادة تقديم طلب أُعيد للتصحيح (V1.4 NEEDS_INFO/returned): يعدّل المقدّم الأصلي حقول
    الحمولة ثم يعيد الطلب من المرحلة صفر بلا إنشاء طلب جديد — يحافظ على سلسلة التاريخ
    (approval history + timeline) كما يشترط الـ spec."""
    if req.status != "returned":
        raise ValueError("هذا الطلب ليس في حالة إعادة للتصحيح")
    if req.requester_user_id != user.id and user.role not in ("hr", "super_admin"):
        raise PermissionError("إعادة التقديم مقتصرة على مقدّم الطلب أو الموارد البشرية")
    if updated_payload:
        req.payload_json = {**(req.payload_json or {}), **updated_payload}
    req.status = "pending"
    req.current_stage = 0
    req.closed_at = None
    db.add(models.RequestApproval(
        request_id=req.id, stage_order=-1, stage_label="إعادة تقديم بعد التصحيح",
        approver_role=user.role, approver_user_id=user.id, decision="resubmitted",
    ))
    enter_stage(db, req, rt)
    db.commit()
    db.refresh(req)
    return req


def _notify_terminated(db: Session, req: models.Request, rt: models.RequestType,
                       kind: str, actor: models.User, note: str | None) -> None:
    """يُشعر العامل وكل من اعتمد أو كان سيعتمد بالرفض/الإلغاء/الإرجاع للتصحيح."""
    word = {"rejected": "رفض", "cancelled": "إلغاء", "returned": "إرجاع"}.get(kind, kind)
    reason = f" السبب: {note}" if note else ""
    # العامل
    emp_code = {"rejected": "NTF-035", "cancelled": "NTF-036"}.get(kind, "NTF-035")
    _notify_employee_from_template(
        db, req, code=emp_code, context={"request_type": rt.name, "reason": note or ""},
        dedup_key=f"req_term_emp:{req.id}",
    )
    # كل من اعتمد سابقًا
    approved_uids = {
        a.approver_user_id for a in db.scalars(
            select(models.RequestApproval).where(models.RequestApproval.request_id == req.id)
        ).all() if a.approver_user_id
    }
    # ومن كان سيعتمد في المراحل المتبقية
    chain = _chain(rt, req)
    future_users: set[int] = set()
    for stage in chain[req.current_stage:]:
        for u in resolve_stage_approvers(db, req, stage):
            future_users.add(u.id)
    for uid in (approved_uids | future_users):
        if uid == actor.id:
            continue
        create_task(
            db, company_id=req.company_id, assignee_user_id=uid, type="request_update",
            # QA-11 — rt.name يبدأ بـ"طلب" أصًلا ("طلب إجازة")، فإضافة الكلمة
            # هنا تنتج "تم اعتماد طلب: طلب إجازة".
            title=f"تم {word}: {rt.name} — {_employee_name(db, req)}",
            detail=f"قام {actor.full_name or actor.role} بـ{word} الطلب.{reason}",
            related_entity_type="request", related_entity_id=req.id,
            dedup_key=f"req_term:{req.id}:u{uid}",
        )


def _body_lines(rt, req, emp) -> list[str]:
    """أسطر تفاصيل الطلب (نص صِرف) — تُستخدم في نسخة PDF ونسخة HTML معًا.

    الأولوية لنص «الصيغة الرسمية» الحرفي من حزمة V1.3 (REQUEST_OFFICIAL_TEXT) — وهو
    الإقرار/التعهد الذي وافق عليه الموظف عند التقديم؛ ثم بيانات الطلب (payload) كملحق.
    """
    p = req.payload_json or {}
    lines: list[str] = []
    official = REQUEST_OFFICIAL_TEXT.get(rt.code)
    if official:
        lines.append(official)
    if rt.code == "leave":
        lines += [
            f"نوع الإجازة: {p.get('leave_type','اعتيادية')}",
            f"من تاريخ: {p.get('start_date','')} إلى تاريخ: {p.get('end_date','')} "
            f"(عدد الأيام: {p.get('days','')})",
            f"السبب: {p.get('reason','')}",
        ]
    elif rt.code in ("salary_certificate", "REQCERTSAL"):
        lines += [
            f"الجهة المستفيدة: {p.get('addressed_to','')}",
            f"الغرض: {p.get('purpose','')}",
            f"الراتب الأساسي: {getattr(emp,'basic_salary',0)} د.ك",
        ]
    elif p:
        lines += [f"{PAYLOAD_KEY_LABELS_AR.get(k, _humanize_key(k))}: {v}" for k, v in p.items()]
    legal_note = LEGAL_NOTES.get(rt.code)
    if legal_note:
        lines.append(f"ملاحظة قانونية: {legal_note}")
    return lines


# ملاحظة قانونية صريحة تُطبع كسطر منفصل ومُعنوَن لأحساس أنواع الطلبات التأديبية/المالية
# الحساسة (P1-02) — تعزيز إضافي فوق الصياغة الحذرة الموجودة أصًلا في REQUEST_OFFICIAL_TEXT،
# لا بديل عنها، تؤكد حق الرد وتفصل الاستلام عن الإقرار بالمضمون في كل مستند حسّاس.
LEGAL_NOTES: dict[str, str] = {
    "ADMWARN": "استلام هذا الإنذار لا يعني إقرار الموظف بصحة وقائعه، وله الحق في الرد أو "
              "الاعتراض كتابًة خلال المدة المحددة وفق سياسة الشركة قبل اتخاذ أي إجراء لاحق.",
    "ADMVIO": "هذا تسجيل لمخالفة مبدئي وليس حكًما نهائًيا؛ يحتفظ الموظف بحقه الكامل في الرد "
             "أو تقديم أدلة مضادة قبل اعتماد أي أثر تأديبي أو مالي مترتب عليه.",
    "ADMDED": "لا يُطبَّق أي خصم فعلي على مستحقات الموظف قبل استكمال الاعتماد المالي وإتاحة "
             "فرصة الرد؛ هذا المستند إجراء تمهيدي لا قرار خصم نافذ بذاته.",
    "REQWARN": "تسجيل الرد لا يعني تنازل الموظف عن أي حق آخر في التظلم عبر القنوات "
              "الرسمية المتاحة، ولا يُحتَجّ به وحده كإقرار نهائي بالوقائع.",
    "REQVIO": "تقديم هذا الاعتراض لا يُسقط أي حق آخر للموظف، وتبقى المخالفة الأصلية "
             "قابلة للمراجعة الكاملة لحين صدور القرار النهائي من الجهة المختصة.",
    "REQGRV": "تُعامَل هذه الشكوى بسرية تامة ولا يطّلع عليها إلا المخوّلون؛ تقديمها لا "
             "يعرّض مقدّمها لأي إجراء انتقامي، وهو حق مكفول له وفق سياسة الشركة.",
    "ADMTASK": "تكليف تنفيذي لا يمنح المكلَّف صلاحية اعتماد أو تعديل أصل الطلب أو القرار "
              "محل التنفيذ؛ دوره يقتصر على التنفيذ ورفع إثبات الإنجاز فقط.",
}


# تسمية عربية لكل مفتاح payload معروف (P0-03) — تمنع ظهور مفاتيح تقنية خام مثل
# amount/months/purpose/destination داخل نص المستند المطبوع؛ أي مفتاح غير مدرَج هنا
# يُحوَّل عبر _humanize_key() (استبدال الشرطة السفلية بمسافة) بدل عرضه كما هو.
PAYLOAD_KEY_LABELS_AR: dict[str, str] = {
    "date": "التاريخ", "amount": "المبلغ (د.ك)", "details": "التفاصيل", "reason": "السبب",
    "start_date": "من تاريخ", "end_date": "إلى تاريخ", "days": "عدد الأيام",
    "leave_type": "نوع الإجازة", "replacement_employee_id": "الموظف البديل",
    "purpose": "الغرض", "addressed_to": "الجهة المستفيدة", "destination": "جهة السفر",
    "months": "عدد الأشهر", "subtype": "نوع الطلب", "installments": "عدد الأقساط",
    "installments_count": "عدد الأقساط", "first_deduction_month": "شهر أول استقطاع",
    "employee_ack": "إقرار الموظف",
    "receipt_ref": "مرجع الفاتورة", "receipt_attachment": "مرفق الفاتورة",
    "category": "الفئة", "description": "الوصف",
    "iban": "رقم الحساب (IBAN)", "bank_name": "اسم البنك",
    "warning_ref": "مرجع الإنذار", "response": "الرد", "attachment": "المرفق",
    "termination_reason": "سبب إنهاء الخدمة", "last_working_day": "آخر يوم عمل",
    "resignation_date": "تاريخ تقديم الاستقالة", "notice_period": "مدة الإشعار",
    "assets": "العهد", "hours": "عدد الساعات", "rate": "المعدل",
    "period": "فترة الراتب", "disputed_amount": "المبلغ محل الاعتراض",
    "evidence": "الإثباتات", "deduction_ref": "مرجع الخصم",
    "employee_response": "رد الموظف", "travel_required": "يتطلب سفرًا",
    "old_title": "المسمى السابق", "requested_title": "المسمى المطلوب",
    "current_title": "المسمى الحالي", "salary": "الراتب", "justification": "المبررات",
    "subject": "الموضوع", "course": "الدورة التدريبية", "provider": "الجهة المقدّمة",
    "cost": "التكلفة", "dates": "المواعيد", "against_person": "الطرف المشتكى منه",
    "target_entity": "الجهة", "language": "اللغة", "effective_month": "شهر السريان",
    "proof": "الإثبات", "old_civil": "الرقم المدني السابق", "new_civil": "الرقم المدني الجديد",
    "old_passport": "الجواز السابق", "new_passport": "الجواز الجديد", "expiry": "تاريخ الانتهاء",
    # REQEOS (تسوية نهاية الخدمة، P0-05)
    "hire_date": "تاريخ التعيين", "last_day": "آخر يوم عمل", "salary_basis": "أساس احتساب الراتب",
    "service_duration": "مدة الخدمة", "entitlements": "المستحقات (د.ك)", "deductions": "الاستقطاعات (د.ك)",
    "net": "صافي المستحقات (د.ك)",
    # REQCLR (إخلاء الطرف، P0-05)
    "finance_status": "الحالة المالية", "department_signoffs": "توقيعات الأقسام",
}


def _humanize_key(key: str) -> str:
    return key.replace("_", " ").strip() or key


def generate_document(db: Session, req: models.Request, rt: models.RequestType,
                      kind: str, actor: models.User) -> models.RequestDocument:
    """يولّد مستند الطلب المعتمَد كملف PDF حقيقي (application/pdf) — لا HTML (FIX-007)."""
    from . import verification
    from .pdf_export import render_request_pdf

    emp = db.get(models.Employee, req.employee_id)
    company = db.get(models.Company, req.company_id)
    approvals = db.scalars(
        select(models.RequestApproval).where(
            models.RequestApproval.request_id == req.id,
            models.RequestApproval.decision == "approved",
        )
    ).all()

    existing = db.scalars(
        select(models.RequestDocument).where(
            models.RequestDocument.request_id == req.id,
            models.RequestDocument.kind == kind,
        )
    ).all()
    # V2.2 §30 (DOC-06) — ضغطتان على "توليد" = مستند واحد.
    #
    # ROOT CAUSE: التوليد كان يُنشئ نسخة جديدة دائًما ويوسم السابقة SUPERSEDED.
    # ذلك صحيح لإعادة إصدار حقيقية، لكن المستخدم يضغط مرتين حين يتأخر الرد —
    # فيحصل على مستندين برقمين مرجعيين مختلفين لنفس القرار، ويقدّم أحدهما
    # لجهة رسمية بينما النظام يعتبره باطًلا.
    #
    # مفتاح التكرار = (الطلب، النوع، آخر قرار). ما دام لم يُتَّخذ قرار جديد
    # بعد توليد النسخة القائمة، فالضغط تكرار لا إعادة إصدار.
    def _naive(d):
        # _now() يُعيد وقًتا واعًيا بالمنطقة بينما الأعمدة naive، فالصف المقروء
        # من القاعدة قد يكون naive والمُنشأ في الذاكرة aware. مقارنتهما مباشرة
        # ترمي TypeError يُسقط توليد المستند كله.
        return d.replace(tzinfo=None) if d and d.tzinfo else d

    # التطبيع قبل max لا بعده: القائمة نفسها تخلط صًفا مقروًءا من القاعدة
    # (naive) بآخر أُنشئ في هذه المعاملة (aware)، فـmax يقارنهما ويرمي.
    _decided = [_naive(a.decided_at) for a in approvals if a.decided_at]
    last_decision = max(_decided) if _decided else None
    for prev in existing:
        if prev.lifecycle_status == "GENERATED" and prev.file_path:
            made = _naive(prev.created_at)
            if last_decision is None or (made and made >= last_decision):
                return prev

    # V2.2 Module 15 — regenerating invalidates prior versions:
    # النسخ السابقة تُوسم SUPERSEDED (signature snapshots القديمة تصبح باطلة)
    # والنسخة الجديدة تحصل على version أعلى.
    for prev in existing:
        if prev.lifecycle_status not in ("SUPERSEDED", "ARCHIVED"):
            prev.lifecycle_status = "SUPERSEDED"
    # يُنشأ السجل أوًلا (بلا file_path) للحصول على doc.id، لازم لتوليد رمز التحقق
    # المُشتق منه (P2-01) قبل رسم الـPDF نفسه.
    # V1.5 Phase 4: نستخرج od_code من default_template_code (HRMS-PR-XXX → OD-YYY)
    from . import v15_registry
    od_code = v15_registry.resolve_template(rt.default_template_code) if rt.default_template_code else None
    doc = models.RequestDocument(
        request_id=req.id, kind=kind, file_path=None,
        version=len(existing) + 1, uploaded_by=actor.id,
        od_code=od_code, lifecycle_status="GENERATING",
    )
    db.add(doc)
    db.flush()

    verification_code = verification.generate_code(doc.id, req.id)
    # SIG-01: صورة توقيع الموظف مقدّم الطلب (المستخدم المرتبط بسجله)
    emp_sig = None
    if emp and emp.id:
        emp_user = db.scalar(select(models.User).where(models.User.employee_id == emp.id))
        if emp_user and emp_user.signature_path and key_exists(emp_user.signature_path):
            emp_sig = emp_user.signature_path
    # SEC2-15: يُفضّل مخوّل من سجل المخوّلين بالتوقيع (Authorized Signatories) عن آخر
    # معتمِد، حتى يكون التوقيع من سلطة موثّقة رسميًا لا من أي معتمِد عابر.
    company_sig = None
    signer_label = None
    try:
        from .routers.signatories import resolve_authorized_signatory
        auth_signer = resolve_authorized_signatory(
            db, req.company_id,
            rt.default_template_code or rt.code,
            category=(getattr(rt, "category", None)),
        )
        if auth_signer:
            signer_user = db.get(models.User, auth_signer.user_id)
            if signer_user and signer_user.signature_path and key_exists(signer_user.signature_path):
                company_sig = signer_user.signature_path
                signer_label = auth_signer.title_ar
    except Exception:
        pass  # فشل السجل لا يمنع الطباعة — نسقط تلقائيًا لآخر معتمِد
    if not company_sig and approvals:
        last = approvals[-1]
        if last.approver_user_id:
            last_user = db.get(models.User, last.approver_user_id)
            if last_user and last_user.signature_path and key_exists(last_user.signature_path):
                company_sig = last_user.signature_path
    # V2.2 §13.12 (AC-12) + RW-15/DOC-18 — دورة المستند مستقلة عن دورة الطلب.
    #
    # ROOT CAUSE: التوليد كان بلا حارس، فاستثناء واحد (خط عربي ناقص، قرص
    # ممتلئ، قالب معطوب) يُسقط المعاملة كلها — بما فيها **قرار الاعتماد
    # نفسه**. المعتمِد يضغط "اعتماد" فيُخبَر بخطأ، ويظنّ أن قراره لم يُسجَّل
    # فيعيده، والطلب عالق بلا سبب ظاهر.
    #
    # القرار قرار والمستند مستند: الاعتماد يبقى، والمستند يُسجَّل FAILED
    # بسببه فيُعاد توليده لاحًقا. ولا يُسجَّل نجاح توليد لم يقع.
    try:
        pdf_bytes = render_request_pdf(rt, req, emp, company, approvals,
                                       _body_lines(rt, req, emp),
                                       verification_code=verification_code,
                                       employee_signature=emp_sig,
                                       company_signature=company_sig,
                                       authorized_signer_label=signer_label)
    except Exception as e:  # noqa: BLE001 — الفشل يُسجَّل ولا يُسقط القرار
        import logging
        doc.lifecycle_status = "FAILED"
        doc.file_path = None
        # لا عمود note على المستند؛ السبب يُحفظ في مرجعه ليظهر في أي قائمة
        doc.reference_no = f"FAILED-{type(e).__name__}"[:80]
        logging.getLogger("hrms.documents").exception(
            "فشل توليد مستند الطلب %s (%s)", req.id, kind)
        for u in users_by_role(db, req.company_id, ["hr"]):
            create_task(
                db, company_id=req.company_id, assignee_user_id=u.id,
                type="document", severity="critical",
                title=f"فشل توليد مستند: {rt.name if rt else req.request_type_code}",
                detail=(f"الطلب #{req.id} معتمَد لكن مستنده لم يُولَّد. "
                        f"السبب: {type(e).__name__}. أعد التوليد بعد معالجته."),
                related_entity_type="request", related_entity_id=req.id,
            )
        return doc

    # AWS-01 — عبر طبقة التخزين. المفتاح محدَّد لأنه يحمل رقم الطلب
    # ونوعه ولحظة التوليد.
    fname = f"request_{req.id}_{kind}_{int(datetime.now().timestamp())}.pdf"
    fpath = save_at_key(pdf_bytes, f"generated/{fname}")
    doc.file_path = fpath
    doc.lifecycle_status = "GENERATED"  # V1.5 Phase 4: انتهى التوليد بنجاح
    # V2.2 §13 — Immutable Artifact: بصمة SHA256 ورقم مرجعي مقروء بشريًا
    import hashlib
    doc.checksum_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    doc.reference_no = f"REQ-{req.id:06d}-{kind.upper()[:6]}-v{doc.version}"
    # DOC-20 — تثبيت نسخة القالب: القالب يتطوّر والمستند الصادر يبقى، وحُجّيته
    # على نصّه لا على نصّ اليوم. بلا هذا يستحيل بعد شهور إثبات بأي نصٍّ صدرت.
    if rt is not None and rt.default_template_code:
        tpl = db.scalar(select(models.DocumentTemplate).where(
            models.DocumentTemplate.code == rt.default_template_code,
            # BKL-05 — نفس عيب ‏IN (NULL, x)‎: القوالب العامة
            # company_id = NULL فلا يطابقها الشرط، ويُقال «لا قالب»
            # بينما القالب موجود.
            sa_or(models.DocumentTemplate.company_id.is_(None),
                  models.DocumentTemplate.company_id == req.company_id),
        ).order_by(models.DocumentTemplate.company_id.isnot(None).desc()))
        if tpl:
            doc.template_code = tpl.code
            doc.template_version = tpl.version
    # V2.2 Module 15 — signature_version: يشير للنسخة الفعلية من signature_path المستخدمة
    #   وقت التوليد. لو الموقّع بدّل توقيعه بعدين، هذا المستند يبقى محتفظًا بالنسخة الأصلية.
    if approvals:
        last_signer_id = approvals[-1].approver_user_id if approvals else None
        if last_signer_id:
            signer = db.get(models.User, last_signer_id)
            if signer and signer.signature_updated_at:
                # نحفظ الطابع الزمني كـinteger unix timestamp للـsignature version
                doc.signature_version = int(signer.signature_updated_at.timestamp())
    return doc


