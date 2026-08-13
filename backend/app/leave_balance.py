# -*- coding: utf-8 -*-
"""مصدر واحد لأرصدة الإجازة (QA-05).

ROOT CAUSE: كان الرقم يُحسب في مكانين بمعنيين مختلفين ويُعرض باسم واحد
«رصيد الإجازات»:

  - ملف الموظف يعرض `Employee.annual_leave_balance` — المتبقّي القابل
    للاستخدام الآن، يُخصم منه مع كل إجازة معتمَدة.
  - نهاية الخدمة تحسب `annual_leave_days * decimal_years` — المستحق التراكمي
    عن كامل مدة الخدمة، أساس بدل الإجازات.

فظهر 30 في شاشة و92.16 في أخرى، وكلاهما صحيح في بابه. الخطأ لم يكن في
الحساب بل في تسميتهما بالاسم نفسه.

القاعدة هنا: دالة واحدة تُعيد الرقمين بأسماء صريحة، وكل شاشة تستدعيها وتعرض
ما يخصّها. لا يُجمعان في رقم واحد — ذلك يخلط استحقاقًا ماليًا بحق تشغيلي.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models

DEFAULT_ANNUAL_LEAVE_DAYS = 30.0


def service_years(emp: models.Employee, as_of: date | None = None) -> float:
    """سنوات الخدمة العشرية حتى تاريخ (أو حتى انتهاء الخدمة إن كان أقرب).

    تستدعي `eos.service_breakdown` لا تحسب بنفسها: القسمة المباشرة على 365
    تعطي رقًما يقارب حساب EOS ولا يطابقه (فرق ~0.07 سنة)، فيعود التناقض الذي
    أُصلح — بصورة أدق يصعب ملاحظتها.
    """
    if not emp.hire_date:
        return 0.0
    end = as_of or date.today()
    if emp.termination_date:
        end = min(end, emp.termination_date)
    from .eos import service_breakdown
    return float(service_breakdown(emp.hire_date, end)[4])  # decimal_years


def accrued_from_service(annual_days: float, years: float) -> float:
    """المستحق التراكمي عن مدة الخدمة — الصيغة الوحيدة في النظام.

    تستدعيها `eos.py` ودالة `leave_balance` أدناه، فلا تُكتب مرتين ولا تتفرّقان.
    """
    return float(annual_days or DEFAULT_ANNUAL_LEAVE_DAYS) * float(years or 0)


def used_days(db: Session, emp: models.Employee) -> float:
    """الأيام المستهلكة فعلًا — من سجلات الإجازة السنوية المعتمَدة.

    نقرأها من `Leave` لا من فرق الأرقام: الفرق يفترض أن الرصيد الابتدائي لم
    يُعدَّل يدويًا يومًا، وهو افتراض لا يصمد.
    """
    rows = db.scalars(select(models.Leave).where(
        models.Leave.employee_id == emp.id,
        models.Leave.status == "approved",
        models.Leave.leave_type == "annual",
    )).all()
    return float(sum(r.days or 0 for r in rows))


def leave_balance(db: Session, emp: models.Employee,
                  company: models.Company | None = None,
                  as_of: date | None = None) -> dict:
    """كل أرقام رصيد الإجازة لموظف — بأسماء لا تلتبس.

    - `usable_days`  : المتاح للاستخدام الآن (ما يراه الموظف ويطلب منه إجازة).
    - `accrued_days` : المستحق التراكمي عن مدة الخدمة (أساس بدل الإجازات).
    - `used_days`    : المستهلك من الإجازات السنوية المعتمَدة.
    - `payable_days` : القابل للصرف عند نهاية الخدمة = المستحق − المستهلك،
                       ولا يقلّ عن صفر (الاستهلاك الزائد لا يُخصم من المكافأة).
    """
    annual = float(
        (company.annual_leave_days if company and company.annual_leave_days
         else None) or DEFAULT_ANNUAL_LEAVE_DAYS
    )
    yrs = service_years(emp, as_of)
    accrued = accrued_from_service(annual, yrs)
    used = used_days(db, emp)
    return {
        "usable_days": round(float(emp.annual_leave_balance or 0), 2),
        "accrued_days": round(accrued, 2),
        "used_days": round(used, 2),
        "payable_days": round(max(accrued - used, 0.0), 2),
        "service_years": round(yrs, 3),
        "annual_entitlement": annual,
    }
