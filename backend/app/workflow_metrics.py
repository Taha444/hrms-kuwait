# -*- coding: utf-8 -*-
"""V2.2 §13.15 (AC-15) — قياس تشغيل المسارات.

ROOT CAUSE: النظام يسجّل كل قرار بوقته منذ البداية، لكن لا أحد يستطيع أن
يجيب: أين يقف الطلب طويلًا؟ من يُرجِع أكثر مما يعتمد؟ كم مرة خرقنا مهلتنا؟
البيانات موجودة والسؤال بلا جواب — وهذا أسوأ من غيابها، لأنه يُخفي المشكلة
تحت انطباع بأن "الأمور بخير".

المقاييس هنا مشتقّة من الجداول القائمة لا من عدّادات جديدة: عدّاد يُكتب عند
الحدث ينحرف عن الواقع مع أول عطل، والاشتقاق لا ينحرف.

- زمن الانتظار لكل خطوة = من دخول المرحلة إلى قرارها. ودخول المرحلة هو قرار
  سابقتها (أو إنشاء الطلب للمرحلة الأولى) — لا عمود مستقل لذلك، فيُشتقّ.
- خرق SLA يُقاس على المهام التي تحمل sla_due_at فعلًا؛ ما لا مهلة له لا
  يُحتسب نجاًحا ولا فشًلا، ويُعلَن عدده حتى لا تبدو النسبة أفضل مما هي.
- نسبة الأتمتة = الخطوات التي أنهاها النظام (AUTOMATION/skipped) من مجموع
  الخطوات المنفَّذة.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models


def _hours(a: datetime | None, b: datetime | None) -> float | None:
    if not a or not b:
        return None
    return round((b - a).total_seconds() / 3600.0, 2)


def _avg(values: list[float]) -> float | None:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 2) if vals else None


def workflow_operations(db: Session, company_id: int | None,
                        since: date | None = None, until: date | None = None) -> dict:
    """تقرير تشغيلي: أزمنة الخطوات، الإرجاع، الرفض، خرق SLA، نسبة الأتمتة."""
    since = since or (date.today() - timedelta(days=90))
    until = until or date.today()
    start = datetime.combine(since, datetime.min.time())
    end = datetime.combine(until, datetime.max.time())

    rq = select(models.Request).where(models.Request.created_at >= start,
                                      models.Request.created_at <= end)
    if company_id is not None:
        rq = rq.where(models.Request.company_id == company_id)
    requests = db.scalars(rq).all()
    ids = [r.id for r in requests]

    approvals = []
    if ids:
        approvals = db.scalars(select(models.RequestApproval).where(
            models.RequestApproval.request_id.in_(ids)
        ).order_by(models.RequestApproval.request_id,
                   models.RequestApproval.stage_order,
                   models.RequestApproval.id)).all()

    by_request: dict[int, list] = {}
    for a in approvals:
        by_request.setdefault(a.request_id, []).append(a)

    created_at = {r.id: r.created_at for r in requests}
    per_step: dict[str, dict] = {}
    decisions = {"approved": 0, "rejected": 0, "returned": 0, "skipped": 0}

    for rid, rows in by_request.items():
        entered = created_at.get(rid)
        for a in rows:
            decisions[a.decision] = decisions.get(a.decision, 0) + 1
            label = a.stage_label or a.approver_role or f"مرحلة {a.stage_order}"
            slot = per_step.setdefault(label, {"waits": [], "count": 0,
                                               "returned": 0, "rejected": 0,
                                               "skipped": 0})
            slot["count"] += 1
            if a.decision in ("returned", "rejected", "skipped"):
                slot[a.decision] += 1
            slot["waits"].append(_hours(entered, a.decided_at))
            # المرحلة التالية تبدأ من قرار هذه
            entered = a.decided_at

    steps = [{
        "stage": label,
        "decisions": s["count"],
        "avg_wait_hours": _avg(s["waits"]),
        "returned": s["returned"],
        "rejected": s["rejected"],
        "skipped_automatically": s["skipped"],
    } for label, s in sorted(per_step.items(), key=lambda kv: -(kv[1]["count"]))]

    # زمن التنفيذ الكامل: من الإنشاء إلى الإغلاق
    cycle = [_hours(r.created_at, r.closed_at) for r in requests if r.closed_at]

    # خرق SLA — على ما له مهلة فعلًا
    tq = select(models.Task).where(models.Task.sla_due_at.isnot(None),
                                   models.Task.created_at >= start,
                                   models.Task.created_at <= end)
    if company_id is not None:
        tq = tq.where(models.Task.company_id == company_id)
    with_sla = db.scalars(tq).all()
    now = datetime.now()
    breached = sum(1 for t in with_sla
                   if (t.completed_at or now) > t.sla_due_at)

    total_tasks_q = select(func.count()).select_from(models.Task).where(
        models.Task.created_at >= start, models.Task.created_at <= end)
    if company_id is not None:
        total_tasks_q = total_tasks_q.where(models.Task.company_id == company_id)
    total_tasks = db.scalar(total_tasks_q) or 0

    executed = sum(decisions.values())
    automated = decisions.get("skipped", 0)

    return {
        "period": {"since": since.isoformat(), "until": until.isoformat()},
        "requests": {
            "total": len(requests),
            "closed": sum(1 for r in requests if r.closed_at),
            "avg_cycle_hours": _avg(cycle),
        },
        "steps": steps,
        "decisions": decisions,
        "return_rate": round(decisions.get("returned", 0) / executed, 3) if executed else None,
        "rejection_rate": round(decisions.get("rejected", 0) / executed, 3) if executed else None,
        "sla": {
            "tasks_with_sla": len(with_sla),
            "breached": breached,
            "breach_rate": round(breached / len(with_sla), 3) if with_sla else None,
            # يُعلَن صراحًة: نسبة محسوبة على جزء من المهام ليست نسبة على كلها
            "tasks_without_sla": max(total_tasks - len(with_sla), 0),
        },
        "automation": {
            "executed_steps": executed,
            "automated_steps": automated,
            "ratio": round(automated / executed, 3) if executed else None,
        },
    }
