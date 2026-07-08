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
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .notifications import create_task, notify_employee_self, users_by_role

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

# ----------------------- ربط الحالات الداخلية بحالات V1.3 الرسمية (FIX-009) -----------------------
# كل حالة داخلية (Request.status) تُعرَض دومًا عبر هذا الربط بدل الاسم التقني الخام،
# حتى تكون واجهة/API الطلب متطابقة مع مسمّيات النسخة المعتمدة V1.3.
STATUS_MAP: dict[str, dict[str, str]] = {
    "pending": {"code": "PENDING_APPROVAL", "label": "قيد الاعتماد"},
    "awaiting_signature": {"code": "AWAITING_SIGNATURE", "label": "بانتظار التوقيع"},
    "awaiting_delegate": {"code": "AWAITING_DELEGATE", "label": "بانتظار إجراءات المندوب"},
    "ready_for_pickup": {"code": "READY_FOR_PICKUP", "label": "جاهز للاستلام"},
    "completed": {"code": "COMPLETED", "label": "مكتمل"},
    "rejected": {"code": "REJECTED", "label": "مرفوض"},
    "cancelled": {"code": "CANCELLED", "label": "ملغى"},
}


def status_info(status: str) -> dict[str, str]:
    return STATUS_MAP.get(status, {"code": status.upper(), "label": status})


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
           is_confidential: bool = False) -> dict:
    """يبني نوع طلب بسلسلة موافقات خطّية بسيطة (مرحلة اعتماد لكل دور بالترتيب).

    تُستخدم لتغطية أنواع V1.3 الـ44 المتبقية (المسار الرئيسي المذكور في كل نموذج)
    دون تكرار منطق خاص — النوع الأول (leave) و(salary_certificate) وما شابه تبقى
    بمسارها المخصص (hr_review/delegate_exit/pickup) لأنها مطبَّقة ومختبرة فعلًا.
    """
    chain = [
        {"order": i, "label": f"اعتماد {ROLE_LABEL_AR.get(r, r)}", "role": r, "kind": "approval",
         "produces_document": produces_document and i == len(roles) - 1}
        for i, r in enumerate(roles)
    ]
    return {
        "code": code, "name": name, "category": category,
        "requires_physical_signature": requires_physical_signature,
        "produces_document": produces_document,
        "approval_chain_json": chain, "template_html": None,
        "is_confidential": is_confidential,
    }


ROLE_LABEL_AR = {
    "branch_supervisor": "المسؤول المباشر", "company_manager": "المدير العام",
    "hr": "شؤون الموظفين/القانونية", "delegate": "المندوب", "accountant": "المحاسب",
}


DEFAULT_REQUEST_TYPES = [
    {
        "code": "leave",
        "name": "طلب إجازة",
        "category": CAT_ATTENDANCE,
        "requires_physical_signature": True,
        "produces_document": True,
        "approval_chain_json": [
            {"order": 0, "label": "اعتماد مسؤول الفرع", "role": "branch_supervisor", "kind": "approval"},
            {"order": 1, "label": "اعتماد المدير العام", "role": "company_manager", "kind": "approval"},
            {"order": 2, "label": "مراجعة شؤون الموظفين وتحديد موعد التوقيع", "role": "hr",
             "kind": "hr_review", "produces_document": True},
            {"order": 3, "label": "إجراءات إذن مغادرة البلاد (المندوب)", "role": "delegate",
             "kind": "delegate_exit"},
        ],
        "template_html": None,
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
    },

    # ----------------- الـ 44 نوعًا الرسمية المتبقية من حزمة V1.3 (FIX-002) -----------------
    # الحضور والإجازات
    _simple("REQPER", "طلب إذن أثناء الدوام", CAT_ATTENDANCE,
           ["branch_supervisor", "hr"], requires_physical_signature=False),
    _simple("REQEXIT", "طلب مغادرة مبكرة", CAT_ATTENDANCE,
           ["branch_supervisor", "hr"], requires_physical_signature=False),
    _simple("REQLATE", "تبرير تأخير", CAT_ATTENDANCE,
           ["branch_supervisor", "hr"], requires_physical_signature=False),
    _simple("REQATT", "طلب تصحيح سجل حضور", CAT_ATTENDANCE,
           ["branch_supervisor", "hr"], requires_physical_signature=False),
    _simple("REQSHIFT", "طلب تغيير وردية", CAT_ATTENDANCE,
           ["branch_supervisor", "company_manager"], requires_physical_signature=False),
    _simple("REQOT", "طلب عمل إضافي", CAT_ATTENDANCE,
           ["branch_supervisor", "company_manager", "accountant"], requires_physical_signature=False),
    _simple("REQWLOC", "تكليف مؤقت بموقع أو فرع", CAT_ATTENDANCE,
           ["branch_supervisor", "company_manager", "hr"], produces_document=True),
    _simple("REQMIS", "طلب مهمة عمل خارجية", CAT_ATTENDANCE,
           ["branch_supervisor", "company_manager"], produces_document=True),

    # الإقامة والمعاملات الحكومية
    _simple("REQRESE", "طلب تجديد إقامة مبكر", CAT_RESIDENCY,
           ["hr", "company_manager", "delegate"], produces_document=True),
    _simple("REQRESN", "طلب تجديد إقامة عادي", CAT_RESIDENCY,
           ["delegate", "hr"], produces_document=True),
    _simple("REQPASS", "طلب تحديث أو تجديد جواز السفر", CAT_RESIDENCY,
           ["hr"], requires_physical_signature=False),
    _simple("REQCID", "طلب تحديث أو تجديد البطاقة المدنية", CAT_RESIDENCY,
           ["hr", "delegate"], requires_physical_signature=False),
    _simple("REQWP", "طلب تجديد إذن عمل", CAT_RESIDENCY,
           ["hr", "company_manager", "delegate"], produces_document=True),
    _simple("REQGOV", "طلب معاملة حكومية", CAT_RESIDENCY,
           ["hr", "delegate"], requires_physical_signature=False),
    _simple("REQTRFLIC", "طلب نقل عامل بين فرع أو ترخيص", CAT_RESIDENCY,
           ["branch_supervisor", "hr", "company_manager"], produces_document=True),

    # بيانات الموظف والمستندات
    _simple("REQDOC", "رفع أو تحديث مستند موظف", CAT_EMP_DATA,
           ["hr"], requires_physical_signature=False),
    _simple("REQDATA", "طلب تعديل البيانات الشخصية", CAT_EMP_DATA,
           ["hr"], requires_physical_signature=False),
    _simple("REQBANK", "طلب تغيير الحساب البنكي", CAT_EMP_DATA,
           ["accountant", "company_manager"], requires_physical_signature=False),
    _simple("REQCONTACT", "تحديث بيانات الاتصال والطوارئ", CAT_EMP_DATA,
           ["hr"], requires_physical_signature=False),

    # الشهادات والخطابات
    _simple("REQCERTSAL", "طلب شهادة راتب (V1.3)", CAT_CERTIFICATES,
           ["company_manager", "hr"], produces_document=True, requires_physical_signature=False),
    _simple("REQCERTEMP", "طلب شهادة لمن يهمه الأمر", CAT_CERTIFICATES,
           ["hr"], produces_document=True, requires_physical_signature=False),
    _simple("REQCERTEXP", "طلب شهادة خبرة", CAT_CERTIFICATES,
           ["hr", "company_manager"], produces_document=True, requires_physical_signature=False),
    _simple("REQFILE", "طلب نسخة من ملف أو مستند", CAT_CERTIFICATES,
           ["hr"], requires_physical_signature=False),

    # الطلبات المالية
    _simple("REQADV", "طلب سلفة أو قرض", CAT_FINANCIAL,
           ["company_manager", "accountant"], requires_physical_signature=False),
    _simple("REQEXP", "طلب استرداد مصروفات", CAT_FINANCIAL,
           ["branch_supervisor", "accountant"], requires_physical_signature=False),
    _simple("REQALLOW", "طلب بدل أو ميزة", CAT_FINANCIAL,
           ["branch_supervisor", "company_manager"], requires_physical_signature=False),
    _simple("REQPAY", "اعتراض على الراتب", CAT_FINANCIAL,
           ["accountant", "company_manager"], requires_physical_signature=False),
    _simple("REQDED", "اعتراض على خصم", CAT_FINANCIAL,
           ["accountant", "hr", "company_manager"], requires_physical_signature=False),

    # الشكاوى والتظلمات
    _simple("REQGRV", "شكوى أو تظلم", CAT_GRIEVANCE,
           ["hr"], requires_physical_signature=False, is_confidential=True),
    _simple("REQVIO", "اعتراض على مخالفة", CAT_GRIEVANCE,
           ["hr", "company_manager"], requires_physical_signature=False),
    _simple("REQWARN", "إقرار أو رد على إنذار", CAT_GRIEVANCE,
           ["hr"], requires_physical_signature=False),

    # طلبات عامة
    _simple("REQGEN", "طلب عام أو اقتراح", CAT_GENERAL,
           ["branch_supervisor"], requires_physical_signature=False),

    # التطوير الوظيفي
    _simple("REQTRN", "طلب تدريب", CAT_CAREER,
           ["branch_supervisor", "company_manager"], requires_physical_signature=False),
    _simple("REQTRF", "طلب نقل داخلي", CAT_CAREER,
           ["branch_supervisor", "company_manager"], produces_document=True),
    _simple("REQPROMO", "طلب ترقية أو تعديل راتب", CAT_CAREER,
           ["branch_supervisor", "company_manager"], produces_document=True),

    # العقود وإنهاء الخدمة
    _simple("REQCON", "تجديد عقد أو عدم تجديد", CAT_CONTRACTS,
           ["hr", "company_manager"], produces_document=True),
    _simple("REQRESIGN", "طلب استقالة", CAT_CONTRACTS,
           ["company_manager", "hr"], produces_document=True),
    _simple("REQEOS", "طلب احتساب وتسوية نهاية خدمة", CAT_CONTRACTS,
           ["hr", "accountant", "company_manager"], produces_document=True),
    _simple("REQCLR", "إخلاء طرف وتسليم عهدة", CAT_CONTRACTS,
           ["accountant", "hr"], produces_document=True),

    # نماذج إدارية
    _simple("ADMEMP", "إضافة موظف جديد", CAT_ADMIN,
           ["hr", "company_manager"], requires_physical_signature=False),
    _simple("ADMACTUAL", "تعديل الراتب الفعلي أو مكان العمل الفعلي", CAT_ADMIN,
           ["company_manager", "accountant"], requires_physical_signature=False),
    _simple("ADMDED", "إصدار خصم", CAT_ADMIN,
           ["hr", "accountant", "company_manager"], requires_physical_signature=False),
    _simple("ADMVIO", "تسجيل مخالفة وظيفية", CAT_ADMIN,
           ["branch_supervisor", "hr", "company_manager"], requires_physical_signature=False),
    _simple("ADMWARN", "إصدار إنذار", CAT_ADMIN,
           ["hr", "company_manager"], produces_document=True),
    _simple("ADMTASK", "تكليف مندوب أو مهمة إدارية", CAT_ADMIN,
           ["company_manager", "delegate", "hr"], requires_physical_signature=False),
    _simple("ADMMISS", "إشعار نقص مستندات", CAT_ADMIN,
           ["hr"], requires_physical_signature=False),
    _simple("ADMLIC", "تجديد مستند شركة أو ترخيص", CAT_ADMIN,
           ["hr", "company_manager", "delegate"], produces_document=True),
    _simple("ADMSIGN", "اعتماد وتوقيع إلكتروني", CAT_ADMIN,
           ["company_manager", "hr"], requires_physical_signature=False),
]


def get_request_type(db: Session, company_id: int, code: str) -> models.RequestType | None:
    """يبحث عن نوع الطلب الخاص بالشركة أولًا ثم العام (company_id=None)."""
    rt = db.scalar(
        select(models.RequestType).where(
            models.RequestType.code == code,
            models.RequestType.company_id == company_id,
            models.RequestType.is_active == True,  # noqa: E712
        )
    )
    if rt:
        return rt
    return db.scalar(
        select(models.RequestType).where(
            models.RequestType.code == code,
            models.RequestType.company_id.is_(None),
            models.RequestType.is_active == True,  # noqa: E712
        )
    )


def _chain(rt: models.RequestType) -> list[dict]:
    return sorted(rt.approval_chain_json or [], key=lambda s: s.get("order", 0))


def resolve_stage_approvers(db: Session, req: models.Request, stage: dict) -> list[models.User]:
    """يحدد المستخدمين المعنيين بمرحلة معيّنة حسب الدور (وفرع العامل)."""
    role = stage.get("role")
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
                return users
        # لا يوجد مسؤول فرع → يتجاوز للمدير العام
        return users_by_role(db, req.company_id, ["company_manager"])
    return users_by_role(db, req.company_id, [role]) if role else []


def can_decide(db: Session, req: models.Request, user: models.User, stage: dict,
              rt: models.RequestType | None = None) -> bool:
    if user.role == "super_admin":
        return True
    if user.company_id != req.company_id:
        return False
    # المدير العام يستطيع التدخّل في أي مرحلة — إلا في الطلبات السرّية (شكاوى/تظلمات، FIX-014):
    # يقتصر القرار فيها على معتمدي المرحلة الفعليين دون تجاوز إداري، حفاظًا على السرّية.
    if not (rt and rt.is_confidential) and user.role in ("company_manager", "company_owner"):
        return True
    approvers = resolve_stage_approvers(db, req, stage)
    return any(u.id == user.id for u in approvers)


def _employee_name(db: Session, req: models.Request) -> str:
    emp = db.get(models.Employee, req.employee_id)
    return emp.name if emp else f"#{req.employee_id}"


def create_request(db: Session, employee: models.Employee, requester: models.User,
                   rt: models.RequestType, payload: dict) -> models.Request:
    req = models.Request(
        company_id=employee.company_id, employee_id=employee.id,
        requester_user_id=requester.id, request_type_code=rt.code,
        payload_json=payload, status="pending", current_stage=0,
    )
    db.add(req)
    db.flush()
    enter_stage(db, req, rt)
    db.commit()
    db.refresh(req)
    return req


def enter_stage(db: Session, req: models.Request, rt: models.RequestType) -> None:
    """يهيّئ المرحلة الحالية: ضبط الحالة وإنشاء المهام للمستلِمين."""
    chain = _chain(rt)
    if req.current_stage >= len(chain):
        return _finalize(db, req)
    stage = chain[req.current_stage]
    kind = stage.get("kind", "approval")
    name = _employee_name(db, req)
    label = stage.get("label", "")

    if kind in ("approval", "hr_review"):
        req.status = "pending"
        for u in resolve_stage_approvers(db, req, stage):
            create_task(
                db, company_id=req.company_id, assignee_user_id=u.id, type="request_stage",
                title=f"بانتظار موافقتك: {rt.name} — {name}",
                detail=f"المرحلة: {label}. اطّلع على الطلب لاعتماده أو رفضه.",
                related_entity_type="request", related_entity_id=req.id,
                severity="info", dedup_key=f"req_stage:{req.id}:{req.current_stage}:u{u.id}",
            )
    elif kind == "delegate_exit":
        req.status = "awaiting_delegate"
        p = req.payload_json or {}
        for u in users_by_role(db, req.company_id, ["delegate"]):
            create_task(
                db, company_id=req.company_id, assignee_user_id=u.id, type="exit_permit",
                title=f"إجراءات إذن مغادرة البلاد: {name}",
                detail=(f"تم منح {name} إجازة من {p.get('start_date','')} إلى {p.get('end_date','')}، "
                        "برجاء البدء في إجراءات إذن مغادرة البلاد ورفعه على النظام."),
                related_entity_type="request", related_entity_id=req.id,
                severity="warning", dedup_key=f"req_exit:{req.id}",
            )
    elif kind == "pickup":
        req.status = "ready_for_pickup"
        # يُنفّذ الطلب الدور المحدَّد في المرحلة (hr افتراضيًا، أو accountant للسلف/القروض)
        executor = stage.get("role") or "hr"
        for u in users_by_role(db, req.company_id, [executor]):
            create_task(
                db, company_id=req.company_id, assignee_user_id=u.id, type="pickup_ready",
                title=f"طلب معتمَد بانتظار التنفيذ: {rt.name} — {name}",
                detail="تم اعتماد الطلب. استكمل التنفيذ/التسليم.",
                related_entity_type="request", related_entity_id=req.id,
                dedup_key=f"req_pickup:{req.id}",
            )
        notify_employee_self(
            db, req.employee_id, type="pickup_ready",
            title=f"{rt.name} جاهزة للاستلام",
            detail="يرجى استلام المستند من مكتب شؤون الموظفين.",
            related_entity_type="request", related_entity_id=req.id,
            dedup_key=f"req_pickup_emp:{req.id}",
        )

    # إشعار العامل بالتقدّم
    notify_employee_self(
        db, req.employee_id, type="request_update",
        title=f"تحديث على طلبك: {rt.name}",
        detail=f"وصل طلبك إلى مرحلة: {label}.",
        related_entity_type="request", related_entity_id=req.id,
        dedup_key=f"req_progress:{req.id}:{req.current_stage}",
    )


def decide(db: Session, req: models.Request, user: models.User, decision: str,
           note: str | None, rt: models.RequestType) -> models.Request:
    chain = _chain(rt)
    stage = chain[req.current_stage]
    approval = models.RequestApproval(
        request_id=req.id, stage_order=req.current_stage,
        stage_label=stage.get("label", ""), approver_role=user.role,
        approver_user_id=user.id, decision=decision, note=note,
    )
    db.add(approval)

    if decision == "rejected":
        req.status = "rejected"
        req.closed_at = datetime.now(timezone.utc)
        _notify_terminated(db, req, rt, "rejected", user, note)
        db.commit()
        db.refresh(req)
        return req

    # اعتماد
    kind = stage.get("kind", "approval")
    if kind == "hr_review":
        # يولّد المستند وينتقل لحالة انتظار التوقيع (لا يتقدّم حتى رفع الموقّع)
        generate_document(db, req, rt, kind="generated_pdf", actor=user)
        req.status = "awaiting_signature"
        notify_employee_self(
            db, req.employee_id, type="appointment",
            title="مطلوب حضورك للتوقيع",
            detail="برجاء مراجعة مسؤول شؤون الموظفين في مقر الشركة لإتمام طلبك بالتوقيع.",
            related_entity_type="request", related_entity_id=req.id,
            dedup_key=f"req_sign:{req.id}",
        )
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
    notify_employee_self(
        db, req.employee_id, type="exit_permit",
        title="إذن مغادرة البلاد جاهز",
        detail=f"تم إنهاء إجراءات إذن المغادرة الخاص بـ {name}. يمكنك طباعته والسفر.",
        related_entity_type="request", related_entity_id=req.id,
        dedup_key=f"req_exit_ready:{req.id}",
    )
    _advance(db, req, rt)
    db.commit()


def mark_pickup_received(db: Session, req: models.Request, rt: models.RequestType) -> None:
    _advance(db, req, rt)
    db.commit()


def _advance(db: Session, req: models.Request, rt: models.RequestType) -> None:
    req.current_stage += 1
    if req.current_stage >= len(_chain(rt)):
        _finalize(db, req)
    else:
        enter_stage(db, req, rt)


def _finalize(db: Session, req: models.Request) -> None:
    req.status = "completed"
    req.closed_at = datetime.now(timezone.utc)
    notify_employee_self(
        db, req.employee_id, type="request_update",
        title="اكتمل طلبك",
        detail="تم إنهاء جميع مراحل طلبك بنجاح.",
        related_entity_type="request", related_entity_id=req.id,
        dedup_key=f"req_done:{req.id}",
    )


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
    db.commit()
    db.refresh(req)
    return req


def _notify_terminated(db: Session, req: models.Request, rt: models.RequestType,
                       kind: str, actor: models.User, note: str | None) -> None:
    """يُشعر العامل وكل من اعتمد أو كان سيعتمد بالرفض/الإلغاء."""
    word = "رفض" if kind == "rejected" else "إلغاء"
    reason = f" السبب: {note}" if note else ""
    # العامل
    notify_employee_self(
        db, req.employee_id, type="request_update",
        title=f"تم {word} طلبك: {rt.name}",
        detail=f"تم {word} الطلب من قبل {actor.full_name or actor.role}.{reason}",
        related_entity_type="request", related_entity_id=req.id,
        dedup_key=f"req_term_emp:{req.id}",
    )
    # كل من اعتمد سابقًا
    approved_uids = {
        a.approver_user_id for a in db.scalars(
            select(models.RequestApproval).where(models.RequestApproval.request_id == req.id)
        ).all() if a.approver_user_id
    }
    # ومن كان سيعتمد في المراحل المتبقية
    chain = _chain(rt)
    future_users: set[int] = set()
    for stage in chain[req.current_stage:]:
        for u in resolve_stage_approvers(db, req, stage):
            future_users.add(u.id)
    for uid in (approved_uids | future_users):
        if uid == actor.id:
            continue
        create_task(
            db, company_id=req.company_id, assignee_user_id=uid, type="request_update",
            title=f"تم {word} طلب: {rt.name} — {_employee_name(db, req)}",
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
        lines += [f"{k}: {v}" for k, v in p.items()]
    return lines


def generate_document(db: Session, req: models.Request, rt: models.RequestType,
                      kind: str, actor: models.User) -> models.RequestDocument:
    """يولّد مستند الطلب المعتمَد كملف PDF حقيقي (application/pdf) — لا HTML (FIX-007)."""
    from .pdf_export import render_request_pdf

    emp = db.get(models.Employee, req.employee_id)
    company = db.get(models.Company, req.company_id)
    approvals = db.scalars(
        select(models.RequestApproval).where(
            models.RequestApproval.request_id == req.id,
            models.RequestApproval.decision == "approved",
        )
    ).all()
    pdf_bytes = render_request_pdf(rt, req, emp, company, approvals, _body_lines(rt, req, emp))

    os.makedirs(settings.upload_dir, exist_ok=True)
    fname = f"request_{req.id}_{kind}_{int(datetime.now().timestamp())}.pdf"
    fpath = os.path.join(settings.upload_dir, fname)
    with open(fpath, "wb") as f:
        f.write(pdf_bytes)

    existing = db.scalars(
        select(models.RequestDocument).where(
            models.RequestDocument.request_id == req.id,
            models.RequestDocument.kind == kind,
        )
    ).all()
    doc = models.RequestDocument(
        request_id=req.id, kind=kind, file_path=fpath,
        version=len(existing) + 1, uploaded_by=actor.id,
    )
    db.add(doc)
    return doc


def render_document_html(rt, req, emp, company, approvals) -> str:
    """نسخة HTML للمعاينة على الشاشة فقط (المستند الرسمي المعتمد أصبح PDF حقيقيًا — FIX-007)."""
    from html import escape as e  # تهريب القيم لمنع حقن HTML/XSS

    rows = "".join(
        f"<li>اعتمد من قبل: <b>{e(a.stage_label or '')}</b> ({e(a.approver_role or '')}) بتاريخ "
        f"{a.decided_at.strftime('%Y-%m-%d %H:%M')}</li>"
        for a in approvals
    )
    body_extra = "".join(f"<p>{e(line)}</p>" for line in _body_lines(rt, req, emp))
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>{e(rt.name)}</title>
<style>
body{{font-family:'Segoe UI',Tahoma,Arial;margin:40px;color:#111}}
.header{{text-align:center;border-bottom:2px solid #333;padding-bottom:12px;margin-bottom:24px}}
.muted{{color:#666;font-size:13px}} .sign{{margin-top:60px}}
ul{{line-height:1.9}} @media print{{.noprint{{display:none}}}}
</style></head><body>
<div class="header">
  <h2>{e(company.name) if company else ''}</h2>
  <h3>{e(rt.name)}</h3>
  <div class="muted">رقم الطلب: {req.id} — تاريخ: {datetime.now().strftime('%Y-%m-%d')}</div>
</div>
<p>الموظف: <b>{e(emp.name) if emp else ''}</b> — الرقم المدني: {e(getattr(emp,'civil_id','') or '')}</p>
<p>الوظيفة: {e(getattr(emp,'job_title','') or '')}</p>
{body_extra}
<hr><h4>سلسلة الاعتماد</h4><ul>{rows or '<li>—</li>'}</ul>
<div class="sign">
  <p>توقيع الموظف: ............................</p>
  <p>توقيع/ختم الشركة: ............................</p>
</div>
<button class="noprint" onclick="window.print()">طباعة</button>
</body></html>"""
