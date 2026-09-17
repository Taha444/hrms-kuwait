# -*- coding: utf-8 -*-
"""حقولُ العقد الحكومي من مصدر السلطة — مصدرٌ واحد للتعيين والتجديد معًا.

كانت هذه القواعد مكتوبةً في راوتر التجديد وحده، ومسارُ التعيين يبني سياقَه
بنفسه من قالب HTML. فقاعدةُ «الأجر من المسيّر المعتمد» و«إدارة العمل من
محافظة مقرّ العمل» كانتا تحكمان ورقًة واحدة في أحد المسارين فقط — وهما
ورقةٌ واحدة تُقدَّم للهيئة. فنُقلتا هنا ويقرؤهما الاثنان.

قرار المالك (2026-09-17): الأجرُ في العقد هو **الراتب الأساسي**.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models

#: حالات المسيّر التي يُعتدّ بأجرها. «prepared» ليست منها: مسيّر محضَّر لم
#: يعتمده أحد بعد، والعقد يذكر الأجر بوصفه التزاًما لا اقتراًحا.
APPROVED_PAYROLL_STATUSES = ("approved", "finalized", "locked")

#: أسماءُ أيام الأسبوع بالعربية — النموذج يكتب اليوم في الخانة العربية.
DAY_AR = {0: "الإثنين", 1: "الثلاثاء", 2: "الأربعاء", 3: "الخميس",
          4: "الجمعة", 5: "السبت", 6: "الأحد"}


def approved_wage(db: Session, emp: models.Employee) -> tuple[str, str]:
    """GC-05 — الأجر الأساسي من آخر مسيّر معتمد. يعيد (القيمة، مصدرها).

    الفرق ليس شكليًّا: راتب الموظف في ملفه قيمة قابلة للتعديل في أي لحظة،
    وأجر المسيّر المعتمد مرّ بمراجعة واعتماد وصار التزاًما محاسبيًّا. وعقد
    يذكر رقًما لم يعتمده أحد يُوقَّع ويُقدَّم لجهة رسمية.

    وحين لا يوجد مسيّر معتمد بعد — موظف جديد مثًلا — يُؤخذ من ملفه، وهو
    مصدر سلطة أيًضا. الممنوع هو payload الطلب: من يستطيع تحرير أجره في
    نموذج يستطيع تزويره.
    """
    runs = db.scalars(select(models.PayrollRun).where(
        models.PayrollRun.company_id == emp.company_id,
        models.PayrollRun.status.in_(APPROVED_PAYROLL_STATUSES),
    ).order_by(models.PayrollRun.period.desc())).all()
    for run in runs:
        for slip in ((run.totals_json or {}).get("payslips") or []):
            if slip.get("employee_id") == emp.id and slip.get("basic_salary") is not None:
                return str(slip["basic_salary"]), f"payroll:{run.period}"
    return ("" if emp.basic_salary is None else str(emp.basic_salary)), "employee_master"


def contract_context(db: Session, emp: models.Employee,
                     company: models.Company | None,
                     start_date: date | None = None) -> dict:
    """حقولُ النموذج الرسمي التي لا يوفّرها سياق القوالب العام.

    كلها من مصدر السلطة في القاعدة، ولا شيء منها من payload الطلب: العقد
    يُقدَّم لجهة رسمية، ومن يستطيع تحرير أجره في نموذج يستطيع تزويره.
    """
    from .clock import today as kuwait_today

    # GC-06 — رقم الإقامة الفعلي لا كود المستند الداخلي.
    residence = db.scalar(select(models.Permit).where(
        models.Permit.employee_id == emp.id,
        models.Permit.kind == "residency",
    ).order_by(models.Permit.expiry_date.desc()))

    # إدارة العمل المختصّة تتبع محافظة مقرّ العمل. وموظف بلا فرع محدَّد
    # يتبع مقرّ الشركة — فيُؤخذ من أول فرع لها يحمل محافظة. اشتقاق من
    # بيانات الشركة لا قيمة مخترعة: العقد يُقدَّم للإدارة المسمّاة فيه.
    branch = db.get(models.Branch, emp.branch_id) if emp.branch_id else None
    if branch is None or not branch.governorate:
        branch = db.scalar(select(models.Branch).where(
            models.Branch.company_id == emp.company_id,
            models.Branch.governorate.isnot(None),
        ).order_by(models.Branch.id)) or branch

    today = kuwait_today()
    start = start_date or emp.hire_date or today
    wage, wage_source = approved_wage(db, emp)
    return {
        "residence_no": (residence.number if residence else "") or "",
        "company_rep_name": (company.representative_name if company else "") or "",
        "company_rep_name_en": (company.representative_name_en if company else "") or "",
        "company_civil_id": (company.representative_civil_id if company else "") or "",
        "labour_dept": (branch.governorate if branch else "") or "",
        "labour_dept_en": (branch.governorate_en if branch else "") or "",
        "wage": wage,
        # يُدوَّن مصدر الأجر في سجلّ التوليد: من يراجع عقًدا بعد سنة يحتاج
        # أن يعرف من أين جاء الرقم، لا أن يستنتجه.
        "wage_source": wage_source,
        "nationality_en": (emp.nationality_en or "") or "",
        "contract_date": today.strftime("%d/%m/%Y"),
        "contract_start_date": start.strftime("%d/%m/%Y"),
        "day_name_en": today.strftime("%A"),
        "day_name": DAY_AR[today.weekday()],
        "contract_term_ar": "سنة",
        "contract_term_en": "ONE YEAR",
        # GC-07 — النوع الخام كما هو مسجَّل، لا الصيغة المعروضة: الصيغة
        # نصّ للقراءة وقد تُترجم، والقرار يُبنى على القيمة لا على عرضها.
        "contract_type_raw": (emp.contract_type or ""),
    }
