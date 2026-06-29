# -*- coding: utf-8 -*-
"""محرّك المهام والإشعارات.

ليست مجرد تنبيهات: كل بند = مهمة لها مسؤول وحالة. يدعم:
- إنشاء مهمة مع مفتاح منع تكرار (dedup_key).
- توجيه نفس الإشعار لعدة مستلِمين (مندوب + مدير + العامل) بصياغة مناسبة.
- مسح يومي يولّد مهامًا حسب مهل انتهاء المستندات/الإقامات/التراخيص.

قنوات الإرسال (واتساب/SMS) خلف واجهة قابلة للتوصيل تُضاف لاحقًا؛ المرحلة
الأولى = إشعار داخل التطبيق عبر جدول tasks.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


def create_task(
    db: Session,
    *,
    company_id: int | None,
    type: str,
    title: str,
    assignee_user_id: int | None = None,
    detail: str | None = None,
    related_entity_type: str | None = None,
    related_entity_id: int | None = None,
    severity: str = "info",
    due_date: date | None = None,
    dedup_key: str | None = None,
) -> models.Task | None:
    """ينشئ مهمة. إن وُجد dedup_key لمهمة مفتوحة مطابقة لا يُكرّرها."""
    if dedup_key:
        existing = db.scalar(
            select(models.Task).where(
                models.Task.dedup_key == dedup_key,
                models.Task.status.in_(["open", "in_progress"]),
            )
        )
        if existing:
            return existing
    task = models.Task(
        company_id=company_id, type=type, title=title, detail=detail,
        assignee_user_id=assignee_user_id, related_entity_type=related_entity_type,
        related_entity_id=related_entity_id, severity=severity, due_date=due_date,
        dedup_key=dedup_key,
    )
    db.add(task)
    # إرسال عبر القنوات الخارجية (واتساب/SMS) إن فُعّلت — best-effort
    try:
        from .channels import dispatch
        recipient = None
        if assignee_user_id:
            u = db.get(models.User, assignee_user_id)
            recipient = (u.phone or u.email) if u else None
        dispatch(recipient, title, detail or "")
    except Exception:
        pass
    return task


def users_by_role(db: Session, company_id: int | None, roles: list[str]) -> list[models.User]:
    q = select(models.User).where(models.User.role.in_(roles), models.User.is_active == True)  # noqa: E712
    if company_id is not None:
        q = q.where(models.User.company_id == company_id)
    return list(db.scalars(q).all())


def notify_roles(db: Session, company_id: int | None, roles: list[str], **kwargs) -> None:
    """ينشئ مهمة لكل مستخدم ضمن الأدوار المحددة داخل الشركة."""
    base_dedup = kwargs.pop("dedup_key", None)
    for user in users_by_role(db, company_id, roles):
        dk = f"{base_dedup}:u{user.id}" if base_dedup else None
        create_task(db, company_id=company_id, assignee_user_id=user.id, dedup_key=dk, **kwargs)


def notify_employee_self(db: Session, employee_id: int, **kwargs) -> None:
    """يُشعر العامل نفسه إن كان له حساب خدمة ذاتية."""
    user = db.scalar(select(models.User).where(models.User.employee_id == employee_id))
    if user:
        base_dedup = kwargs.pop("dedup_key", None)
        dk = f"{base_dedup}:u{user.id}" if base_dedup else None
        create_task(db, company_id=user.company_id, assignee_user_id=user.id, dedup_key=dk, **kwargs)


# ----------------------------- المسح اليومي -----------------------------

# مهل التنبيه الذكية (Rule 2): 90/60/30/15/7/يوم الانتهاء
EXPIRY_THRESHOLDS = [0, 7, 15, 30, 60, 90]


def expiry_bucket(days_left: int) -> int | None:
    """يرجع أصغر عتبة تنبيه وقع ضمنها days_left (أو None إن كان أبعد من 90 يومًا)."""
    for t in EXPIRY_THRESHOLDS:
        if days_left <= t:
            return t
    return None


def expiry_severity(days_left: int) -> str:
    if days_left <= 7:
        return "critical"
    if days_left <= 30:
        return "warning"
    return "info"


def daily_scan(db: Session) -> dict:
    """يفحص الإقامات/الجوازات/التراخيص/المستندات ويولّد مهامًا للمستلِمين."""
    today = date.today()
    created = 0

    companies = {c.id: c for c in db.scalars(select(models.Company)).all()}

    # 1) الإقامات وأذونات العمل
    for permit in db.scalars(select(models.Permit).where(models.Permit.status == "active")).all():
        if not permit.expiry_date:
            continue
        days_left = (permit.expiry_date - today).days
        bucket = expiry_bucket(days_left)
        if bucket is None:  # أبعد من 90 يومًا
            continue
        emp = db.get(models.Employee, permit.employee_id)
        kind_ar = "الإقامة" if permit.kind == "residency" else "إذن العمل"
        sev = expiry_severity(days_left)
        name = emp.name if emp else f"#{permit.employee_id}"
        dk = f"permit_expiring:{permit.id}:{bucket}"
        # شأن حكومي → للمندوب (PRO) فقط
        notify_roles(
            db, permit.company_id, ["delegate"],
            type="renew_residency" if permit.kind == "residency" else "renew_work_permit",
            title=f"تجديد {kind_ar}: {name}",
            detail=f"{kind_ar} للعامل {name} تنتهي خلال {days_left} يومًا ({permit.expiry_date}).",
            related_entity_type="permit", related_entity_id=permit.id,
            severity=sev, due_date=permit.expiry_date, dedup_key=dk,
        )
        # للعامل بصياغة مناسبة
        notify_employee_self(
            db, permit.employee_id,
            type="doc_expiring",
            title=f"{kind_ar} الخاصة بك قاربت على الانتهاء",
            detail=f"{kind_ar} تنتهي بتاريخ {permit.expiry_date}. سيتم البدء في إجراءات التجديد.",
            related_entity_type="permit", related_entity_id=permit.id,
            severity=sev, due_date=permit.expiry_date, dedup_key=dk,
        )
        created += 1

    # 2) المستندات (جوازات وغيرها)
    for doc in db.scalars(
        select(models.Document).where(models.Document.is_current == True, models.Document.expiry_date.isnot(None))  # noqa: E712
    ).all():
        days_left = (doc.expiry_date - today).days
        bucket = expiry_bucket(days_left)
        if bucket is None:
            continue
        sev = expiry_severity(days_left)
        dk = f"doc_expiring:{doc.id}:{bucket}"
        title = doc.title or doc.document_type_code
        # مستندات رسمية (جوازات/إقامات) → شأن حكومي للمندوب فقط
        notify_roles(
            db, doc.company_id, ["delegate"],
            type="doc_expiring", title=f"مستند قارب على الانتهاء: {title}",
            detail=f"المستند ({title}) ينتهي خلال {days_left} يومًا ({doc.expiry_date}).",
            related_entity_type="document", related_entity_id=doc.id,
            severity=sev, due_date=doc.expiry_date, dedup_key=dk,
        )
        if doc.entity_type == "employee":
            notify_employee_self(
                db, doc.entity_id, type="doc_expiring",
                title=f"مستندك ({title}) قارب على الانتهاء",
                detail=f"يرجى متابعة تجديد ({title})، ينتهي بتاريخ {doc.expiry_date}.",
                related_entity_type="document", related_entity_id=doc.id,
                severity=sev, due_date=doc.expiry_date, dedup_key=dk,
            )
        created += 1

    # 3) التراخيص + مقارنة العمالة بالمسموح
    for lic in db.scalars(select(models.License).where(models.License.status == "active")).all():
        if lic.expiry_date:
            days_left = (lic.expiry_date - today).days
            bucket = expiry_bucket(days_left)
            if bucket is not None:
                sev = expiry_severity(days_left)
                notify_roles(
                    db, lic.company_id, ["delegate"],
                    type="license_expiring", title=f"ترخيص قارب على الانتهاء: {lic.name}",
                    detail=f"الترخيص {lic.name} ينتهي خلال {days_left} يومًا ({lic.expiry_date}).",
                    related_entity_type="license", related_entity_id=lic.id,
                    severity=sev, due_date=lic.expiry_date,
                    dedup_key=f"license_expiring:{lic.id}:{bucket}",
                )
                created += 1
        # تجاوز سعة العمالة
        if lic.allowed_workers:
            actual = len(db.scalars(
                select(models.Employee.id).where(
                    models.Employee.license_id == lic.id, models.Employee.status == "active"
                )
            ).all())
            if actual > lic.allowed_workers:
                notify_roles(
                    db, lic.company_id, ["delegate"],
                    type="capacity_exceeded",
                    title=f"تجاوز سعة الترخيص: {lic.name}",
                    detail=f"عدد العمالة {actual} يتجاوز المسموح {lic.allowed_workers}.",
                    related_entity_type="license", related_entity_id=lic.id,
                    severity="warning", dedup_key=f"capacity:{lic.id}",
                )
                created += 1

    db.commit()
    return {"generated": created, "scanned_at": today.isoformat()}
