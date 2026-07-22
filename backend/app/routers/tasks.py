# -*- coding: utf-8 -*-
"""صندوق المهام لكل مستخدم (Task Inbox) + تشغيل المسح اليومي يدويًا."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, require_perm
from ..notifications import daily_scan

router = APIRouter(prefix="/tasks", tags=["tasks"])

# تصنيف الإشعارات (Rule / 3.10)
_CATEGORY = {
    "renew_residency": "government", "renew_work_permit": "government", "license_expiring": "government",
    "doc_expiring": "government", "transfer_info": "government", "exit_permit": "government",
    "capacity_exceeded": "government", "request_stage": "approvals", "request_update": "approvals",
    "pickup_ready": "hr", "appointment": "hr",
}


def _category(task_type: str) -> str:
    return _CATEGORY.get(task_type, "system")


@router.get("/my")
def my_tasks(status: str | None = "open", category: str | None = None,
             user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(models.Task).where(models.Task.assignee_user_id == user.id)
    if status:
        q = q.where(models.Task.status == status)
    rows = db.scalars(q.order_by(models.Task.created_at.desc())).all()
    out = [{"id": t.id, "type": t.type, "category": _category(t.type), "title": t.title,
            "detail": t.detail, "status": t.status, "severity": t.severity,
            "due_date": t.due_date, "related_entity_type": t.related_entity_type,
            "related_entity_id": t.related_entity_id, "created_at": t.created_at,
            "template_code": t.template_code, "channel": t.channel} for t in rows]
    if category:
        out = [x for x in out if x["category"] == category]
    return out


@router.get("/count")
def my_open_count(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = len(db.scalars(select(models.Task.id).where(
        models.Task.assignee_user_id == user.id, models.Task.status == "open")).all())
    return {"open": n}


@router.post("/{task_id}/status")
def update_status(task_id: int, status: str,
                  user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if status not in ("open", "in_progress", "done", "dismissed"):
        raise HTTPException(status_code=400, detail="حالة غير صالحة")
    task = db.get(models.Task, task_id)
    if not task or task.assignee_user_id != user.id:
        raise HTTPException(status_code=404, detail="المهمة غير موجودة")
    task.status = status
    if status in ("done", "dismissed"):
        task.completed_at = datetime.now()
    db.commit()
    return {"ok": True, "status": status}


@router.post("/run-scan")
def run_scan(user: models.User = Depends(require_perm("manage_tasks")), db: Session = Depends(get_db)):
    """تشغيل المسح اليومي يدويًا لتوليد المهام (يستخدمه HR/المدير عند الحاجة)."""
    return daily_scan(db)


@router.post("/{task_id}/claim")
def claim_task(task_id: int, user: models.User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """V1.5 Phase 3 — التقاط مهمة موزعة على مجموعة أدوار قبل التنفيذ لمنع التكرار.

    يفشل بـ409 إن كانت المهمة مُلتقَطة من مستخدم آخر ولم تُطلَق بعد.
    """
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="المهمة غير موجودة")
    if task.status not in ("open", "in_progress"):
        raise HTTPException(status_code=400, detail="لا يمكن التقاط مهمة غير مفتوحة")
    if task.claimed_by_user_id and task.claimed_by_user_id != user.id:
        raise HTTPException(status_code=409,
                            detail="المهمة ملتقطة من مستخدم آخر — انتظر إطلاقها أو تنفيذها")
    task.claimed_by_user_id = user.id
    task.claimed_at = datetime.now()
    task.status = "in_progress"
    db.commit()
    return {"ok": True, "claimed_by_user_id": user.id,
            "claimed_at": task.claimed_at.isoformat()}


@router.post("/{task_id}/release")
def release_task(task_id: int, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """يُطلق التقاط المهمة ليتمكن مستخدم آخر من التقاطها. متاح للمالك أو HR."""
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="المهمة غير موجودة")
    if task.claimed_by_user_id and task.claimed_by_user_id != user.id and user.role not in ("hr", "super_admin"):
        raise HTTPException(status_code=403, detail="لا يمكنك إطلاق مهمة ملتقطة من مستخدم آخر")
    task.claimed_by_user_id = None
    task.claimed_at = None
    task.status = "open"
    db.commit()
    return {"ok": True}


@router.post("/bulk")
def bulk_task_action(task_ids: list[int], action: str,
                     user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    """V2.2 §19 — Bulk Complete/Dismiss لمهام المستخدم.

    - action ∈ {done, dismissed}
    - المستخدم لا يعمل bulk على مهام غيره (assignee_user_id == user.id)
    - يعيد {count} = عدد المهام التي تأثرت فعلًا
    """
    if action not in ("done", "dismissed"):
        raise HTTPException(status_code=400, detail="عملية غير صالحة")
    if not task_ids:
        return {"ok": True, "count": 0}
    q = select(models.Task).where(
        models.Task.id.in_(task_ids),
        models.Task.assignee_user_id == user.id,
        models.Task.status.in_(("open", "in_progress")),
    )
    updated = 0
    now = datetime.now()
    for t in db.scalars(q).all():
        t.status = action
        t.completed_at = now
        updated += 1
    db.commit()
    return {"ok": True, "count": updated}


@router.post("/cleanup-orphans")
def cleanup_orphan_tasks(user: models.User = Depends(require_perm("manage_tasks")),
                         db: Session = Depends(get_db)):
    """V2.2 §19 — تنظيف مهام يتيمة: المهام المفتوحة المرتبطة بطلب مغلق (نهائية).
    يستخدمها HR لتصحيح حالات نادرة تسبق تفعيل _close_open_tasks."""
    closed_statuses = {"completed", "rejected", "cancelled"}
    q = select(models.Task).where(
        models.Task.status.in_(("open", "in_progress")),
        models.Task.related_entity_type == "request",
    )
    fixed = 0
    now = datetime.now()
    for t in db.scalars(q).all():
        req = db.get(models.Request, t.related_entity_id)
        if req and req.status in closed_statuses:
            t.status = "dismissed"
            t.completed_at = now
            fixed += 1
    db.commit()
    return {"ok": True, "cleaned": fixed}


@router.post("/run-sla-scan")
def run_sla_scan(user: models.User = Depends(require_perm("manage_tasks")),
                 db: Session = Depends(get_db)):
    """تشغيل مسح SLA يدويًا لتصعيد المهام المتأخرة (اختياري — يعمل تلقائيًا كل ساعة)."""
    from ..notifications import sla_scan
    return sla_scan(db)
