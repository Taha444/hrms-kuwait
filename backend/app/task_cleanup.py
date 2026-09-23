# -*- coding: utf-8 -*-
"""تنظيف ما خلّفه تكرار المهام — بعد إغلاق جذره لا قبله.

**لماذا أمٌر منفصل**: منع التكرار الجديد لا يزيل ما تراكم. وصندوق فيه
أربعون بلاًغا عن ثمانية أشياء يُعلّم قارئه ألّا يقرأه — فيضيع البلاغ
الحقيقي بين نسخه.

**ولا يحذف صًفا واحًدا**: يُغلق بحالة ``dismissed`` وسبب مكتوب. السجل
يبقى للتفتيش، والصندوق يعود صادًقا.

**وجافٌّ افتراضًيا**: يُبلّغ عمّا سيفعله، ولا يكتب إلا مع ``--apply``.
فمن يشغّله على الإنتاج يرى الأثر قبل وقوعه.

الاستعمال::

    python -m app.task_cleanup                # تقرير فقط
    python -m app.task_cleanup --apply        # ينفّذ
    python -m app.task_cleanup --company 1    # شركة بعينها
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .clock import today as kuwait_today
from .database import SessionLocal

OPEN = ("open", "in_progress")

#: سبب الإغلاق يُكتَب في المهمة نفسها — «أُغلقت» بلا سبب سؤال بلا جواب.
REASON_DUPLICATE = "أُغلقت آلًيا: نسخة مكرَّرة من مهمة قائمة لنفس الموضوع."
REASON_CLOSED_REQUEST = "أُغلقت آلًيا: الطلب المرتبط بلغ حالة نهائية."
REASON_RENEWED = "أُغلقت آلًيا: التصريح جُدِّد وتاريخ انتهائه لم يعد قريًبا."
REASON_ORPHAN = "أُغلقت آلًيا: الكيان المرتبط لم يعد موجوًدا."
REASON_STALE_DIGEST = "أُغلقت آلًيا: خلاصة يومية انقضى وقتها."
REASON_ESCALATION_SOURCE_CLOSED = "أُغلقت آلًيا: المهمة التي صُعِّد بشأنها لم تعد مفتوحة."

#: ما يُنفَّذ **آليًّا كل يوم**: ما لا رجعةَ فيه ولا يُعاد توليده — كيانٌ محذوف، تصعيدٌ لمهمةٍ أُغلقت،
#: علّةُ فرعٍ زالت.
#: **ولا تدخل هنا** ``renewed_permits`` (نافذته 60 يومًا وتنبيه المسح 90: فيُغلق ما ولّده المسح
#: ثم يُعاد توليده كل يوم) ولا ``closed_requests`` و``stale_digests`` (يعالجها مساراتها).
AUTOMATIC_BUCKETS = ("orphans", "orphan_escalations", "resolved_branch_gaps")
REASON_BRANCH_GAP_RESOLVED = "أُغلقت آلًيا: الفرع زالت عنه العلّة (أُدخلت إحداثياته أو أُرشف أو حُذف)."

#: الأنواع المعلوماتية **الدورية**: قيمتها في يومها.
#:
#: ولا تشمل كل إشعار: خبر نتيجة طلب يُقرأ متى فُتح الملف، أما خلاصة
#: يوم مضى فلا معنى لبقائها مفتوحة — وعشرة منها تُغرق الصندوق وتُعلّم
#: قارئه ألّا يقرأه.
PERIODIC_TYPES = ("digest",)

#: بعد كم يوم تُعدّ الخلاصة منقضية. أسبوع: ما بعده لا يُقرأ.
STALE_AFTER_DAYS = 7


def _dismiss(task: models.Task, reason: str) -> None:
    task.status = "dismissed"
    task.completed_at = datetime.now(timezone.utc)
    # يُلحَق بالتفصيل ولا يُستبدَل: نصّ المهمة الأصلي جزء من السجل.
    task.detail = f"{(task.detail or '').strip()}\n— {reason}".strip()


def _duplicates(db: Session, company_id: int | None) -> list[models.Task]:
    """النسخ الزائدة من مهمة واحدة: نفس النوع والكيان والمكلَّف.

    **ويُبقى الأحدث**: تفصيله أقرب إلى الواقع (ساعات التأخّر مثًلا)،
    والأقدم نسخة من حدث واحد لا حدث ثانٍ.
    """
    q = select(models.Task).where(models.Task.status.in_(OPEN))
    if company_id is not None:
        q = q.where(models.Task.company_id == company_id)
    rows = db.scalars(q.order_by(models.Task.id)).all()

    groups: dict[tuple, list[models.Task]] = {}
    for t in rows:
        key = (t.type, t.related_entity_type, t.related_entity_id,
               t.assignee_user_id)
        groups.setdefault(key, []).append(t)
    extra = []
    for items in groups.values():
        if len(items) > 1:
            extra.extend(items[:-1])   # الأحدث يبقى
    return extra


def _on_closed_requests(db: Session, company_id: int | None) -> list[models.Task]:
    """مهام مفتوحة على طلبات بلغت حالة نهائية.

    ولا تشمل الإشعارات: الإشعار خبر يُقرأ، وإغلاقه يمحو إخطار النتيجة.
    """
    from .task_kinds import is_notification

    q = select(models.Task).where(
        models.Task.status.in_(OPEN),
        models.Task.related_entity_type == "request")
    if company_id is not None:
        q = q.where(models.Task.company_id == company_id)
    out = []
    for t in db.scalars(q).all():
        if is_notification(t.type):
            continue
        req = db.get(models.Request, t.related_entity_id)
        if req is not None and req.closed_at is not None:
            out.append(t)
    return out


def _stale_permit_tasks(db: Session, company_id: int | None) -> list[models.Task]:
    """بلاغات انتهاء على تصريح **جُدِّد بالفعل**.

    وهذا عين ما وصفه التقرير: تصريح ممتدّ إلى 2027 وعليه بلاغات قديمة
    ما زالت مفتوحة. والمعيار تاريخ الانتهاء نفسه لا عمر البلاغ.
    """
    q = select(models.Task).where(
        models.Task.status.in_(OPEN),
        models.Task.related_entity_type == "permit")
    if company_id is not None:
        q = q.where(models.Task.company_id == company_id)
    today = kuwait_today()
    out = []
    for t in db.scalars(q).all():
        permit = db.get(models.Permit, t.related_entity_id)
        if permit is None:
            continue
        exp = getattr(permit, "expiry_date", None)
        # 60 يوًما: نافذة التنبيه المعتادة. ما تجاوزها لم يعد قريًبا.
        if exp and (exp - today).days > 60:
            out.append(t)
    return out


def _stale_periodic(db: Session, company_id: int | None) -> list[models.Task]:
    """خلاصات دورية انقضى وقتها.

    **ولا تُحذف**: تُغلَق بسببها ويبقى نصّها في السجل. والقياس على
    تاريخها لا على عددها — فخلاصة اليوم تبقى مفتوحة.
    """
    from datetime import timedelta

    q = select(models.Task).where(
        models.Task.status.in_(OPEN),
        models.Task.type.in_(PERIODIC_TYPES))
    if company_id is not None:
        q = q.where(models.Task.company_id == company_id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_AFTER_DAYS)
    out = []
    for t in db.scalars(q).all():
        made = t.created_at
        if made is None:
            continue
        if made.tzinfo is None:
            made = made.replace(tzinfo=timezone.utc)
        if made < cutoff:
            out.append(t)
    return out


def _orphans(db: Session, company_id: int | None) -> list[models.Task]:
    """مهام تشير إلى كيان لم يعد موجوًدا — لا سبيل إلى إنجازها."""
    kinds = {"request": models.Request, "permit": models.Permit,
             "employee": models.Employee, "renewal": models.ResidencyRenewal,
             "document": models.Document, "license": models.License}
    q = select(models.Task).where(
        models.Task.status.in_(OPEN),
        models.Task.related_entity_type.in_(list(kinds)),
        models.Task.related_entity_id.is_not(None))
    if company_id is not None:
        q = q.where(models.Task.company_id == company_id)
    out = []
    for t in db.scalars(q).all():
        model = kinds.get(t.related_entity_type)
        if model is not None and db.get(model, t.related_entity_id) is None:
            out.append(t)
    return out


def _orphan_escalations(db: Session, company_id: int | None) -> list[models.Task]:
    """تصعيدات SLA لمهمةٍ **لم تعد مفتوحة** (أُغلقت أو زالت).

    قيس على الإنتاج (2026-09-23): 69 تصعيدًا «حرجًا» مفتوحًا على حساب HR لطلباتٍ غير
    موجودة. والتصعيد مفتاحه ``sla_escalation:<task_id>:u<user>`` — فمصدره يُعرف من
    مفتاحه، وإذا أُغلق المصدر لم يبقَ ما يُصعَّد بشأنه.
    """
    q = select(models.Task).where(
        models.Task.status.in_(OPEN),
        models.Task.type == "sla_escalation",
        models.Task.dedup_key.like("sla_escalation:%"))
    if company_id is not None:
        q = q.where(models.Task.company_id == company_id)
    out = []
    for t in db.scalars(q).all():
        parts = (t.dedup_key or "").split(":")
        if len(parts) < 2 or not parts[1].isdigit():
            continue
        src = db.get(models.Task, int(parts[1]))
        if src is None or src.status not in OPEN:
            out.append(t)
    return out


def _resolved_branch_gaps(db: Session, company_id: int | None) -> list[models.Task]:
    """«فرعٌ بلا إحداثيات» بعد أن زالت علّته.

    المسح اليوميّ يُنشئ التنبيه (``branch_no_coords:<id>``) ولا شيء كان يُغلقه: بعد أن
    أُدخلت إحداثيات الفروع الأربعة والأربعين وحُذفت المكرَّرات ظلّت سبعُ مهامّ «فرعٌ
    بلا إحداثيات» مفتوحةً على حساب HR (2026-09-23) توحي بأن الموقع ناقص وهو مكتمل.
    """
    q = select(models.Task).where(
        models.Task.status.in_(OPEN),
        models.Task.type == "config_gap",
        models.Task.dedup_key.like("branch_no_coords:%"))
    if company_id is not None:
        q = q.where(models.Task.company_id == company_id)
    out = []
    for t in db.scalars(q).all():
        # المفتاح الفعليّ «branch_no_coords:<id>:u<user>» — ``notify_roles`` تُلحق المستلِم.
        parts = (t.dedup_key or "").split(":")
        tail = parts[1] if len(parts) > 1 else ""
        if not tail.isdigit():
            continue
        b = db.get(models.Branch, int(tail))
        if b is None or b.latitude is not None or b.status == "archived":
            out.append(t)
    return out


def run(db: Session, *, company_id: int | None = None,
        apply: bool = False, only: tuple[str, ...] | None = None) -> dict:
    """يجمع ما يجب إغلاقه ويُغلقه عند ``apply``. قابل لإعادة التشغيل.

    ``only`` يحصر الدفعات المنفَّذة (المسح اليومي يمرّر ``AUTOMATIC_BUCKETS``).
    """
    buckets = [
        ("duplicates", _duplicates(db, company_id), REASON_DUPLICATE),
        ("closed_requests", _on_closed_requests(db, company_id),
         REASON_CLOSED_REQUEST),
        ("renewed_permits", _stale_permit_tasks(db, company_id), REASON_RENEWED),
        ("orphans", _orphans(db, company_id), REASON_ORPHAN),
        ("stale_digests", _stale_periodic(db, company_id), REASON_STALE_DIGEST),
        ("orphan_escalations", _orphan_escalations(db, company_id),
         REASON_ESCALATION_SOURCE_CLOSED),
        ("resolved_branch_gaps", _resolved_branch_gaps(db, company_id),
         REASON_BRANCH_GAP_RESOLVED),
    ]
    if only is not None:
        buckets = [b for b in buckets if b[0] in only]
    report: dict[str, object] = {"apply": apply}
    seen: set[int] = set()
    total = 0
    for name, rows, reason in buckets:
        fresh = [t for t in rows if t.id not in seen]
        seen.update(t.id for t in fresh)
        report[name] = {"count": len(fresh), "ids": [t.id for t in fresh][:50]}
        total += len(fresh)
        if apply:
            for t in fresh:
                _dismiss(t, reason)
    report["total"] = total
    if apply:
        db.commit()
    return report


def main() -> None:
    p = argparse.ArgumentParser(description="تنظيف المهام المكرَّرة والمتقادمة")
    p.add_argument("--apply", action="store_true",
                   help="ينفّذ الإغلاق (بدونه تقرير فقط)")
    p.add_argument("--company", type=int, default=None, help="حصر بشركة")
    args = p.parse_args()

    db = SessionLocal()
    try:
        rep = run(db, company_id=args.company, apply=args.apply)
    finally:
        db.close()

    print("تنظيف المهام —", "تنفيذ" if args.apply else "تقرير فقط (بلا كتابة)")
    for key in ("duplicates", "closed_requests", "renewed_permits", "orphans",
                "stale_digests", "orphan_escalations", "resolved_branch_gaps"):
        info = rep[key]
        print(f"  {key:<18} {info['count']}")
    print(f"  {'المجموع':<18} {rep['total']}")
    if not args.apply and rep["total"]:
        print("\nأعد التشغيل مع --apply للتنفيذ. لا يُحذف صفٌّ واحد — تُغلَق "
              "بحالة dismissed وسبب مكتوب.")


if __name__ == "__main__":
    main()
