# -*- coding: utf-8 -*-
"""QA-20 — مصدر واحد لتعريف "المهمة الحكومية".

ROOT CAUSE: الرقم نفسه كان له تعريفان:
- لوحة المندوب: كل مهامي المفتوحة أًيا كان نوعها (``assignee_user_id == me``)
- مركز العمليات: أنواع حكومية محددة على مستوى الشركة، بصرف النظر عن المُسنَد إليه

والبطاقة في اللوحة تنقل إلى مركز العمليات — فيرى المستخدم "2" ثم صفحة تقول
"لا توجد بيانات". لا أحد الرقمين خاطئ في ذاته؛ الخطأ أنهما يحملان الاسم نفسه.

التعريف المعتمد هنا هو تعريف الوجهة (مركز العمليات)، لأنه ما يراه المستخدم
بعد النقر.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models

GOV_TASK_TYPES = [
    "renew_residency", "renew_work_permit", "license_expiring",
    "doc_expiring", "transfer_info", "exit_permit", "capacity_exceeded",
]


def open_gov_tasks_query(company_id: int | None):
    """استعلام عدّ المهام الحكومية المفتوحة — يستخدمه العدّاد والقائمة مًعا."""
    q = select(func.count()).select_from(models.Task).where(
        models.Task.status == "open",
        models.Task.type.in_(GOV_TASK_TYPES),
    )
    if company_id is not None:
        q = q.where(models.Task.company_id == company_id)
    return q


def count_open_gov_tasks(db: Session, company_id: int | None) -> int:
    return db.scalar(open_gov_tasks_query(company_id)) or 0
