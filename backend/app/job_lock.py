# -*- coding: utf-8 -*-
"""AWS-02 — المهمة المجدولة تعمل مرة واحدة مهما تعدّدت النسخ.

المجدول يعمل داخل التطبيق، فمع أكثر من instance يعمل على كل واحدة. النتيجة
ليست بطًئا بل بيانات خاطئة: الفحص اليومي يُنشئ تنبيهات ومهامّ مكرّرة،
والإشعارات تصل مرتين، وفي الأسوأ تتكرّر قيود مالية. وهذا يفاقم بلاًغا
قائًما عن مهامّ مكرّرة وSLA/digest مضاعف.

**القفل في القاعدة لا في الذاكرة.** قفل داخل العملية لا يرى العملية
الأخرى — وهي المشكلة نفسها. والقاعدة هي الشيء الوحيد الذي تتشاركه كل
النسخ، فهي موضع القفل الطبيعي.

**والقفل هو السجلّ.** الإدراج على مفتاح أساسيّ مركّب ``(job, run_key)``
عملية ذرّية في Postgres وSQLite معًا: من نجح إدراجه ملك القفل، ومن اصطدم
بالتكرار يعرف أن غيره يعمل. فلا حاجة لآلية ثانية، والصفّ الباقي هو دليل
أن هذه الجولة نُفِّذت — أي أن القفل والـidempotency شيء واحد لا شيئان
يفترقان.

**والمفتاح هو الجولة.** ``daily_scan`` مفتاحه اليوم، و``sla_scan`` مفتاحه
اليوم والساعة. فإعادة تشغيل الخادم مرتين في الدقيقة نفسها لا تُعيد التنفيذ،
وهذا هو الفرق بين قفل يمنع التزامن وضمانٍ يمنع التكرار.

**والقفل العالق يُستردّ.** نسخة تسقط أثناء التنفيذ تترك صًفا «يعمل» إلى
الأبد، فتتوقّف المهمة بصمت — وهو أسوأ من تكرارها: تنتهي إقامات بلا تنبيه
لأن المُنبِّه نفسه متعطّل. فأي صفّ تجاوز مهلته يُؤخذ ويُسجَّل استرداده.
"""
from __future__ import annotations

import logging
import os
import socket
from contextlib import contextmanager
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .clock import now as kuwait_now

logger = logging.getLogger(__name__)

#: مهلة تُعتبر بعدها الجولة عالقة. أطول من أطول مهمة بكثير: الاسترداد
#: المبكّر يعني تشغيًلا متزامًنا حقيقيًّا، وهو ما جئنا نمنعه.
STALE_AFTER = timedelta(hours=2)

#: كم يوًما تبقى سجلّات الجولات. هي دليل التنفيذ لا أرشيف دائم.
KEEP_DAYS = 30


def _holder() -> str:
    """من يملك القفل — يظهر في السجلّ عند التحقيق في جولة عالقة."""
    return f"{socket.gethostname()}:{os.getpid()}"[:80]


@contextmanager
def run_once(db: Session, job: str, run_key: str):
    """ينفّذ الكتلة مرة واحدة لهذه الجولة عبر كل النسخ.

    يُسلّم ``True`` إن مُنح القفل و``False`` إن كانت الجولة مأخوذة أو
    منفَّذة — والمنادي يقرّر، فلا تُبتلع الحالة بصمت.
    """
    granted = False
    now = kuwait_now().replace(tzinfo=None)
    try:
        db.add(models.JobRun(job=job, run_key=run_key, status="running",
                             started_at=now, holder=_holder()))
        db.commit()
        granted = True
    except IntegrityError:
        db.rollback()
        row = db.get(models.JobRun, (job, run_key))
        if row and row.status == "running" and row.started_at and \
                now - row.started_at > STALE_AFTER:
            # نسخة سقطت أثناء التنفيذ. الاسترداد يُسجَّل: جولة عالقة تتكرّر
            # مرتين علامة على عطل لا على تزامن.
            logger.warning("استرداد جولة عالقة %s/%s من %s (بدأت %s)",
                           job, run_key, row.holder, row.started_at)
            row.status = "running"
            row.started_at = now
            row.holder = _holder()
            row.recovered = (row.recovered or 0) + 1
            db.commit()
            granted = True
        else:
            logger.info("تُخُطّيت %s/%s — نسخة أخرى نفّذتها أو تنفّذها", job, run_key)

    try:
        yield granted
    except Exception:
        if granted:
            row = db.get(models.JobRun, (job, run_key))
            if row:
                # يُترك الصفّ بحالة failed لا يُحذف: الحذف يعني إعادة تنفيذ
                # صامتة في الجولة التالية، والفشل يجب أن يُرى.
                row.status = "failed"
                row.finished_at = kuwait_now().replace(tzinfo=None)
                db.commit()
        raise
    else:
        if granted:
            row = db.get(models.JobRun, (job, run_key))
            if row:
                row.status = "done"
                row.finished_at = kuwait_now().replace(tzinfo=None)
                db.commit()


def daily_key(job: str, at: datetime | None = None) -> str:
    d = (at or kuwait_now()).date()
    return f"{d.isoformat()}"


def hourly_key(job: str, at: datetime | None = None) -> str:
    t = at or kuwait_now()
    return f"{t.date().isoformat()}T{t.hour:02d}"


def purge_old(db: Session) -> int:
    """يحذف سجلّات الجولات القديمة — دليل تنفيذ لا أرشيف دائم."""
    cutoff = (kuwait_now() - timedelta(days=KEEP_DAYS)).replace(tzinfo=None)
    res = db.execute(delete(models.JobRun).where(models.JobRun.started_at < cutoff))
    db.commit()
    return res.rowcount or 0


def recent_runs(db: Session, limit: int = 50) -> list[models.JobRun]:
    return list(db.scalars(
        select(models.JobRun).order_by(models.JobRun.started_at.desc()).limit(limit)))
