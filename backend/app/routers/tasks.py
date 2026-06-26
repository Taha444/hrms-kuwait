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


@router.get("/my", response_model=list[schemas.TaskOut])
def my_tasks(status: str | None = "open",
             user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = select(models.Task).where(models.Task.assignee_user_id == user.id)
    if status:
        q = q.where(models.Task.status == status)
    return list(db.scalars(q.order_by(models.Task.created_at.desc())).all())


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
