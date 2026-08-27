# -*- coding: utf-8 -*-
"""QA-20 / BKL-06 — مصدر واحد لتعريف «المهمة الحكومية» ولنطاقها معًا.

ROOT CAUSE الأصلي: الرقم نفسه كان له تعريفان — لوحة المندوب تعدّ مهامه
كلها أًيا كان نوعها، ومركز العمليات يعدّ أنواًعا حكومية على مستوى الشركة.
فيرى المستخدم «2» ثم صفحة تقول «لا توجد بيانات».

**وبقي نصف العطل بعد ذلك**: التعريف وُحِّد والنطاق لم يُوحَّد. العدّاد يعدّ
مهام الشركة كلها بصرف النظر عن المُسنَد إليه، والقائمة التي يفتحها المندوب
تعرض مهامه هو. والقياس على بيانات حقيقية: **العدّاد 29 والقائمة 12** —
لأن المهام موزّعة على أربعة مستخدمين.

ولا أحد الرقمين خاطئ في ذاته؛ الخطأ أنهما يحملان الاسم نفسه ويُعرضان
كأنهما جواب سؤال واحد.

**القاعدة هنا**: بانٍ واحد للاستعلام يأخذ النطاق وسيًطا، والعدّ يُشتقّ منه
لا يُكتب بجانبه. فيستحيل أن يعدّ رقمٌ شيًئا وتعرض قائمتُه شيًئا آخر ما دام
كلاهما ينادي هذه الدالة بالوسائط نفسها.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models

#: أنواع المهام التي تُعدّ «حكومية». هذه القائمة هي التعريف الوحيد —
#: يشتقّ منها تصنيف المهام في ``routers/tasks.py`` أيًضا، فلا توجد قائمة
#: ثانية تنحرف عنها بنوع يُضاف هنا ويُنسى هناك.
GOV_TASK_TYPES = [
    "renew_residency", "renew_work_permit", "license_expiring",
    "doc_expiring", "transfer_info", "exit_permit", "capacity_exceeded",
]


def gov_tasks_query(company_id: int | None = None,
                    assignee_user_id: int | None = None,
                    status: str | None = "open"):
    """استعلام صفوف المهام الحكومية. **العدّاد والقائمة يستعملانه معًا.**

    كل وسيط يضيّق النطاق، وغيابه يعني «كل شيء». وتمرير الوسائط نفسها من
    موضعَين هو ما يضمن أن الرقم والقائمة يصفان الشيء ذاته.
    """
    q = select(models.Task).where(models.Task.type.in_(GOV_TASK_TYPES))
    if status:
        q = q.where(models.Task.status == status)
    if company_id is not None:
        q = q.where(models.Task.company_id == company_id)
    if assignee_user_id is not None:
        q = q.where(models.Task.assignee_user_id == assignee_user_id)
    return q


def list_gov_tasks(db: Session, company_id: int | None = None,
                   assignee_user_id: int | None = None,
                   status: str | None = "open") -> list[models.Task]:
    q = gov_tasks_query(company_id, assignee_user_id, status)
    return list(db.scalars(q.order_by(models.Task.created_at.desc())))


def count_gov_tasks(db: Session, company_id: int | None = None,
                    assignee_user_id: int | None = None,
                    status: str | None = "open") -> int:
    """العدّ مشتقّ من استعلام القائمة نفسه لا مكتوب بجانبه."""
    inner = gov_tasks_query(company_id, assignee_user_id, status)
    return db.scalar(select(func.count()).select_from(inner.subquery())) or 0


# ---- أسماء قديمة تنادي الجديدة، فلا يبقى تعريف ثانٍ ----
def open_gov_tasks_query(company_id: int | None):
    return gov_tasks_query(company_id=company_id)


def count_open_gov_tasks(db: Session, company_id: int | None) -> int:
    return count_gov_tasks(db, company_id=company_id)
