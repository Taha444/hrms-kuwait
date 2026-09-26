# -*- coding: utf-8 -*-
"""صندوق المهام لكل مستخدم (Task Inbox) + تشغيل المسح اليومي يدويًا."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import assert_same_company, audit, get_current_user, require_perm, scope_company_id
from ..notifications import daily_scan

from ..gov_tasks import GOV_TASK_TYPES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# تصنيف الإشعارات (Rule / 3.10)
#
# BKL-06 — الأنواع الحكومية **تُشتقّ** من ``gov_tasks.GOV_TASK_TYPES`` لا
# تُكتب هنا ثانيًة. كانت القائمتان متطابقتين بالمصادفة، ونوع يُضاف هناك
# ويُنسى هنا يجعل مهمة تُعدّ في اللوحة ولا تظهر في فلتر «حكومي» — وهو
# العطل نفسه بصورة أخرى.
_CATEGORY = {
    **{tp: "government" for tp in GOV_TASK_TYPES},
    "request_stage": "approvals", "request_update": "approvals",
    "pickup_ready": "hr", "appointment": "hr", "warning_no_reply": "hr",
}


#: ما يعود إلى موظٍف — فرُعه فرُع الموظف.
_EMPLOYEE_OWNED = {"request": models.Request, "renewal": models.ResidencyRenewal,
                   "permit": models.Permit, "eos_case": models.EosCase}


def _task_branch(db: Session, task: models.Task) -> int | None:
    """فرُع المهمة من الكيان الذي تخصّه؛ ``None`` لمهمٍة على مستوى الشركة."""
    et, eid = task.related_entity_type, task.related_entity_id
    if not eid:
        return None
    emp_id = None
    if et == "employee":
        emp_id = eid
    elif et == "branch":
        return eid
    elif et in _EMPLOYEE_OWNED:
        row = db.get(_EMPLOYEE_OWNED[et], eid)
        emp_id = getattr(row, "employee_id", None)
    elif et == "document":
        doc = db.get(models.Document, eid)
        if doc and doc.entity_type == "employee":
            emp_id = doc.entity_id
        elif doc and doc.entity_type == "branch":
            return doc.entity_id
    emp = db.get(models.Employee, emp_id) if emp_id else None
    return emp.branch_id if emp else None


def _may_claim_scope(db: Session, user: models.User, task: models.Task) -> bool:
    """قرار المالك (2026-09-18): الالتقاُط بنطاق الفرع.

    من له نطاق فروع لا يلتقط إلا مهمًة في فروعه — أو مهمًة أُسندت إليه
    هو. ومهمُة الشركة (ترخيص، رواتب) بلا فرع: لمن لا نطاَق فروٍع له.
    """
    from ..deps import resolve_scope

    if task.assignee_user_id == user.id:
        return True
    allowed = resolve_scope(user, db).branch_ids
    if allowed is None:
        return True
    return _task_branch(db, task) in allowed


def _category(task_type: str) -> str:
    return _CATEGORY.get(task_type, "system")


# QA-12 — الفرق بين المهمة والإشعار (SKILL-8).
#
# ROOT CAUSE: جدول واحد يحمل النوعين، والواجهة تعرض "إنجاز/تجاهل" على كل سطر
# فيه. فيُطلب من المستخدم أن "يُنجز" خبًرا لا إجراء فيه ("تم اعتماد طلبك")،
# ولا يفهم ماذا يفعل، وإن تجاهله ظنّ أنه فوّت عمًلا.
#
# المهمة: مطلوب منك إجراء، لها صاحب واحد وتُقفل حين يتم.
# الإشعار: معلومة. لا أزرار، ومكانه مركز الإشعارات.
# التعريف في app/task_kinds — يستعمله المحرّك والعرض معًا. وبقاؤه هنا
# كان يجعل من يعرض المهام يعرف الفرق ومن يغلقها لا يعرفه.
from ..task_kinds import NOTIFICATION_TYPES, inbox_query, is_notification  # noqa: E402,F401


#: كيانُ المهمة ← شاشتُه. المصدرُ الواحد الذي تقرؤه الواجهة؛ لا خريطةٌ ثانية عندها تتقادم.
_TARGET_BY_ENTITY = {
    "renewal": "/renewals", "payroll_run": "/payroll", "eos_case": "/eos/cases", "license": "/operations",
    "user": "/users", "branch": "/branches",
}


def task_target_path(t: "models.Task") -> str | None:
    et, eid = t.related_entity_type, t.related_entity_id
    if et == "request" and eid:
        return f"/requests/{eid}"
    if et == "employee" and eid:
        return f"/employees/{eid}"
    if et == "permit":
        return "/renewals" if t.type == "renew_residency" else "/pro"
    return _TARGET_BY_ENTITY.get(et or "")


@router.get("/my")
def my_tasks(response: Response, status: str | None = "open",
             category: str | None = None,
             kind: str | None = None, company_id: int | None = None,
             all_companies: bool = False, limit: int = 200, offset: int = 0,
             user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """``kind=task`` للصندوق، ``kind=notification`` لمركز الإشعارات.

    **والنطاق شركة الفاعل**: من يخدم شركتين كان يرى الصندوق نفسه في
    كلتيهما، بجانب عدادات مقصورة على المختارة — فيُقرأ على أنها له.
    و``all_companies=true`` مخرج صريح لمن يريد الكل، لا سلوك ضمني.
    """
    from ..deps import scope_company_id

    cid = None if all_companies else scope_company_id(user, company_id)
    q = inbox_query(user.id, status, kind, company_id=cid)

    # **والترشيُح بالفئة ينزل إلى الاستعلام.**
    #
    # كان يُطبَّق **بعد** بناء القائمة كلّها: فالخادم يقرأ كلَّ صفوف
    # المستخدم ويُسلسِلها ثم يُلقي ما ليس من الفئة. ومع سقٍف للصفوف يصير
    # ذلك عطًلا لا بطًئا: نأخذ أحدَث مئتين ثم نُرشِّح، فتُعرَض ثالٌث من
    # فئٍة فيها خمسون.
    if category:
        if category == "system":
            q = q.where(models.Task.type.notin_(tuple(_CATEGORY)))
        else:
            types = tuple(t for t, c in _CATEGORY.items() if c == category)
            q = q.where(models.Task.type.in_(types or ("",)))

    # **وصندوٌق بلا سقٍف ينكسر بالنموّ لا بالخطأ.**
    #
    # الافتراض ``status="open"`` كان يحميه وحده، والمعامَل بيد العميل:
    # ``?status=`` يُلغي الترشيح فيُعيد **كلَّ ما أُسند للمستخدم في عمره**.
    # والـdigest اليومي وحده يضيف صًفّا لكل مستخدم كلَّ يوم، فبعد سنٍة
    # تُقاس القائمة بالآالف — وهي أكثُر شاشٍة تُفتَح في النظام.
    #
    # والعدُد الكّلي يُردّ في ترويسة: الجواُب يبقى مصفوفًة كما كان، فلا
    # تُكسَر واجهٌة قائمة، وتعرف الشاشُة أن بعده بقيًّة.
    limit = max(1, min(int(limit or 200), 1000))
    offset = max(0, int(offset or 0))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    response.headers["X-Total-Count"] = str(total)
    rows = db.scalars(q.order_by(models.Task.created_at.desc())
                      .limit(limit).offset(offset)).all()

    # TSK-CLM — من يعمل على المهمة الآن. المهمة تُوزَّع على مجموعة، ولها
    # التقاٌط يمنع أن يعملها اثنان — وكان لا يُقرأ من الشاشة ولا يُلتقَط
    # منها: حقٌل يُكتَب بالواجهة البرمجية ولا يُقرأ، والتكرار الذي بُني
    # الالتقاط لمنعه يقع كأنه غير مبنيّ.
    names: dict[int, str | None] = {}
    for t in rows:
        uid = t.claimed_by_user_id
        if uid and uid not in names:
            u = db.get(models.User, uid)
            names[uid] = u.full_name if u else None

    out = [{"id": t.id, "type": t.type, "category": _category(t.type), "title": t.title,
            # وجهةُ المهمة: كان الصندوق طريقًا مسدودًا («تجديد الإقامة: فلان» بلا مكانٍ يُبدأ منه التجديد)
            "target_path": task_target_path(t),
            "detail": t.detail, "status": t.status, "severity": t.severity,
            "due_date": t.due_date, "related_entity_type": t.related_entity_type,
            "related_entity_id": t.related_entity_id, "created_at": t.created_at,
            # QA-12 — الواجهة تعرف من هنا أيّهما إجراء وأيّهما خبر
            "kind": "notification" if is_notification(t.type) else "task",
            "claimed_by_user_id": t.claimed_by_user_id,
            "claimed_by": names.get(t.claimed_by_user_id),
            "claimed_at": t.claimed_at,
            # والأعلام من شرط المنع نفسه — لا زرٌّ يظهر ثم يفشل.
            "can_claim": bool(t.status in ("open", "in_progress")
                              and not is_notification(t.type)
                              and _may_claim_scope(db, user, t)
                              and (not t.claimed_by_user_id
                                   or t.claimed_by_user_id == user.id)),
            "can_release": bool(t.claimed_by_user_id
                                and (t.claimed_by_user_id == user.id
                                     or user.role in ("hr", "super_admin"))),
            "template_code": t.template_code, "channel": t.channel} for t in rows]
    return out


@router.get("/count")
def my_open_count(company_id: int | None = None,
                  user: models.User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """TSK-03 — رقمان لا رقم واحد: ما يحتاج إجراًء، وما يُقرأ.

    ``open`` يبقى المجموع كما كان (لا نكسر من يقرأه)، والفصل يُضاف
    بجانبه. وكلها مشتقّة من ``inbox_query`` نفسها التي تُغذّي القائمة،
    فيستحيل أن يعدّ الرقم شيًئا وتعرض القائمة تحته شيًئا آخر.
    """
    from ..deps import scope_company_id

    cid = scope_company_id(user, company_id)

    def _n(kind, scope=True):
        return db.scalar(select(func.count()).select_from(
            inbox_query(user.id, "open", kind,
                        company_id=cid if scope else None).subquery())) or 0

    total = _n(None)
    return {
        # ``open`` مجموع الصندوق — اسٌم يضلّل من يقرأ «عندي 54 مهمة»
        # وأمامه 9 تحتاج إجراًء. يبقى للتوافق، والاسم الصادق بجانبه.
        "open": total,
        "total_inbox_items": total,
        "tasks": _n("task"),
        "open_tasks": _n("task"),
        "notifications": _n("notification"),
        "unread_notifications": _n("notification"),
        # والمجموع عبر الشركات معروض صراحًة باسمه: لا يختفي عمٌل بل
        # يُنسَب إلى مكانه. ومن يخدم شركة واحدة يتساوى الرقمان.
        "open_tasks_all_companies": _n("task", scope=False),
    }


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
        # **يُقرأ المحفوُظ ويُختَم UTC** في ``sla_scan`` — فلتُكتَب بها.
        task.completed_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "status": status}


@router.post("/run-scan")
def run_scan(request: Request, user: models.User = Depends(require_perm("manage_tasks")), db: Session = Depends(get_db)):
    """تشغيل المسح اليومي يدويًا لتوليد المهام (يستخدمه HR/المدير عند الحاجة).

    **ولا يتزامن مع جولةٍ جارية** — مجدولةٍ أو يدويةٍ أخرى. ويُسجَّل كجولةٍ
    بمفتاحها (``manual:…``) فيراه المجدوَلُ ويراه نقرٌ ثانٍ.
    """
    from ..clock import now as _now
    from ..job_lock import run_once, running_elsewhere

    if running_elsewhere(db, "daily_scan"):
        raise HTTPException(status_code=409, detail=(
            "المسح اليومي يعمل الآن — أعد المحاولة بعد انتهائه."))
    key = f"manual:{_now():%Y-%m-%dT%H:%M:%S}:u{user.id}"
    with run_once(db, "daily_scan", key) as granted:
        if not granted:
            raise HTTPException(status_code=409, detail=(
                "المسح اليومي يعمل الآن — أعد المحاولة بعد انتهائه."))
        result = daily_scan(db)
        # نجاحُ المسح اليدويّ يُغلق تنبيهات فشل المسح اليومي كنجاحه المجدوَل — وإلا بقيت
        # «فشل مهمة مجدولة: daily_scan» حرجةً حتى جولة الصباح التالية رغم أن المسح نجح الآن.
        from ..scheduler import _resolve_job_failures

        result["failure_alerts_closed"] = _resolve_job_failures(db, "daily_scan")
        audit(db, user, "run_daily_scan_manual", "system", None,
              detail=f"generated={result.get('generated')}", request=request)
        db.commit()
        return result


@router.post("/{task_id}/claim")
def claim_task(task_id: int, user: models.User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """V1.5 Phase 3 — التقاط مهمة موزعة على مجموعة أدوار قبل التنفيذ لمنع التكرار.

    يفشل بـ409 إن كانت المهمة مُلتقَطة من مستخدم آخر ولم تُطلَق بعد.

    **وكان بال تحقٍّق من شركٍة ولا من إسناد**: ``get_current_user`` وحده،
    فأيُّ مستخدٍم مصدٍَّق يلتقط أيَّ مهمٍة بمعرِّفها — من أي شركة. فتصير
    ``in_progress`` باسمه، **ويُمنَع صاحبُها** بـ409 «ملتقطة من مستخدم
    آخر»: تعطيُل عمٍل في شركٍة أخرى بنداٍء واحد، وأثٌر يُنسَب إلى غريب.

    **والإسناُد ال يُشترَط — وهذا قراٌر معلٌَّق ال سهو.** ظننتُ المهمَة
    شخصيًَّة (ال موضَع يُنشئها بال ``assignee_user_id``، و``notify_roles``
    تُنشئ صًفّا لكل مستقبِل)، فأضفتُ شرَط الإسناد — فأسقط
    ``test_task_claim_blocked_when_another_user_already_claimed``: العقُد
    القائُم أن مستخدًما آخَر في الشركة **يصل** إلى الالتقاط، و409 «ملتقطة
    من مستخدم آخر» موجودٌة لهذا بعينه. فلو كان الالتقاُط شخصًيا لما كان
    لها معنى.

    فيبقى العقُد كما هو، **ويُضاف النطاُق وحده** — وهو العطُل المقيس. وهل
    يحقُّ لغير المُسنَد إليه أن يلتقط مهمًة في شركته؟ سؤاٌل إداريٌّ ال
    تقنيّ: يُحسم بكلمِة صاحب القرار، ال باستنباٍط من الشيفرة.
    """
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="المهمة غير موجودة")
    assert_same_company(user, task.company_id, db=db)
    if task.status not in ("open", "in_progress"):
        raise HTTPException(status_code=400, detail="لا يمكن التقاط مهمة غير مفتوحة")
    if not _may_claim_scope(db, user, task):
        raise HTTPException(status_code=403, detail="هذه المهمة خارج نطاق فروعك")
    if task.claimed_by_user_id and task.claimed_by_user_id != user.id:
        raise HTTPException(status_code=409,
                            detail="المهمة ملتقطة من مستخدم آخر — انتظر إطلاقها أو تنفيذها")
    task.claimed_by_user_id = user.id
    task.claimed_at = datetime.now(timezone.utc)
    task.status = "in_progress"
    db.commit()
    return {"ok": True, "claimed_by_user_id": user.id,
            "claimed_at": task.claimed_at.isoformat()}


@router.post("/{task_id}/release")
def release_task(task_id: int, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    """يُطلق التقاط المهمة ليتمكن مستخدم آخر من التقاطها. متاح للمالك أو HR.

    **وعطالن كانا هنا:**

    1. **بال شركة** — والشرُط أدناه يسقط كلُّه إن كانت المهمُّة **غيَر
       ملتقَطة** (``claimed_by_user_id`` فارًغا). فأيُّ مستخدٍم مصدٍَّق يصل
       إلى أي مهمٍة في أي شركة.
    2. **وبال فحص حالة** — ثم يُكتَب ``status = "open"``. فمهمٌَّة ``done``
       أو ``dismissed`` **تُعاد مفتوحًة**: صندوٌق يُظهر عمًلا أُنجز، وعدّاٌد
       يكذب، وقارٌئ يفقد الثقَة بالصندوق فيُهمله كلَّه — وهو الدرُس نفسه
       المكتوب في ``_close_stage_tasks``، مقلوًبا.

    فالإطلاُق لما هو مفتوٌح أو جاٍر، ومن داخل الشركة.
    """
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="المهمة غير موجودة")
    assert_same_company(user, task.company_id, db=db)
    if task.status not in ("open", "in_progress"):
        raise HTTPException(status_code=409,
                            detail="لا يمكن إطلاق مهمة منتهية — أُنجزت أو أُلغيت")
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
    now = datetime.now(timezone.utc)
    for t in db.scalars(q).all():
        t.status = action
        t.completed_at = now
        updated += 1
    db.commit()
    return {"ok": True, "count": updated}


@router.post("/cleanup-orphans")
def cleanup_orphan_tasks(request: Request,
                         user: models.User = Depends(require_perm("manage_tasks")),
                         db: Session = Depends(get_db)):
    """V2.2 §19 — تنظيف مهام يتيمة: المهام المفتوحة المرتبطة بطلب مغلق (نهائية).
    يستخدمها HR لتصحيح حالات نادرة تسبق تفعيل _close_open_tasks.

    **والكنُس مقيٌَّد بشركة الكانس.** ``manage_tasks`` يحملها
    ``company_manager`` و``delegate`` — وكلاهما مقيٌَّد بشركته — وكان
    الاستعلام بلا قيد شركة، فمديُر الشركة الأولى يكنس مهامّ الشركة
    الثانية. والفعُل صحيٌح في كل صّف على حدة (المهمة يتيمٌة فعًلا)، لكنّ
    **الفاعل يتخطّى نطاقه** ويُقيَّد في التدقيق فاعًلا في بيانات لا يراها.
    والنطاق من ``scope_company_id`` نفسها التي يحتكم إليها باقي النظام:
    من هو فوق الشركات يكنس الكلّ، وغيره يكنس شركته.
    """
    closed_statuses = {"completed", "rejected", "cancelled"}
    cid = scope_company_id(user)
    q = select(models.Task).where(
        models.Task.status.in_(("open", "in_progress")),
        models.Task.related_entity_type == "request",
    )
    if cid is not None:
        q = q.where(models.Task.company_id == cid)
    fixed = 0
    now = datetime.now(timezone.utc)
    for t in db.scalars(q).all():
        req = db.get(models.Request, t.related_entity_id)
        if req and req.status in closed_statuses:
            t.status = "dismissed"
            t.completed_at = now
            fixed += 1
    # **وكنٌس جماعّي بلا سطٍر لا يُفسَّر**: من كنس، وفي أيّ نطاق، وكم صًفّا.
    audit(db, user, "cleanup_orphan_tasks", "task", 0,
          detail=f"أُسقِطت {fixed} مهمًة يتيمة", request=request,
          company_id=cid, after={"cleaned": fixed, "company_id": cid})
    db.commit()
    return {"ok": True, "cleaned": fixed}


@router.post("/{task_id}/retry-delivery")
def retry_delivery(task_id: int,
                   user: models.User = Depends(require_perm("manage_tasks")),
                   db: Session = Depends(get_db)):
    """V2.2 §20 — إعادة محاولة تسليم إشعار فشل في قناته الأصلية (email/SMS).
    يزيد delivery_attempts ويفوّض للـchannel handler عبر channels.dispatch.

    **وكان بال شركة**: و``manage_tasks`` يحملها ``company_manager``
    و``delegate`` — وكالهما مقيٌَّد بشركته. فمديُر الشركة الأولى يُعيد
    إرسال إشعاٍر (بريًدا أو رسالًة) **إلى مستخدٍم في الشركة الثانية**: أثٌر
    يخرج من النظام إلى خارجه، بيٍد ال تملكه.
    """
    task = db.get(models.Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="المهمة غير موجودة")
    assert_same_company(user, task.company_id, db=db)
    MAX_ATTEMPTS = 5
    if task.delivery_attempts >= MAX_ATTEMPTS:
        raise HTTPException(status_code=409,
                            detail=f"وصلت للحد الأقصى ({MAX_ATTEMPTS}) — لا مزيد من المحاولات")
    task.delivery_attempts += 1
    task.last_delivery_at = datetime.now(timezone.utc)
    try:
        from ..channels import redispatch_task
        redispatch_task(db, task)
        task.last_delivery_error = None
    except Exception as e:
        # **والسبُب يُحفَظ ولا يُفشى.** نصُّ الاستثناء يحمل مضيَف المزوّد
        # ورأَس طلٍب ومفتاًحا مقطوًعا — ويُقرأ من السجّل والعمود لا من ردّ
        # واجهٍة يراه مستخدم. والردُّ يقول **ما يُفعل**.
        task.last_delivery_error = str(e)[:400]
        logger.warning("فشل إعادة تسليم المهمة %s: %s", task.id, type(e).__name__)
        db.commit()
        raise HTTPException(
            status_code=502,
            detail=("تعذّر تسليم الإشعار في قناته — حُفظ سبُب الفشل على "
                    "المهمة، وأعد المحاولة أو راجع إعدادات القناة"))
    db.commit()
    return {"ok": True, "attempts": task.delivery_attempts}


@router.post("/run-sla-scan")
def run_sla_scan(request: Request, user: models.User = Depends(require_perm("manage_tasks")),
                 db: Session = Depends(get_db)):
    """تشغيل مسح SLA يدويًا لتصعيد المهام المتأخرة (اختياري — يعمل تلقائيًا كل ساعة).

    يعمل على **كل الشركات** (مسحٌ عام) رغم أن صلاحيته بمستوى الشركة — فمن شغّله يُقيَّد في التدقيق."""
    from ..notifications import sla_scan
    result = sla_scan(db)
    audit(db, user, "run_sla_scan_manual", "system", None, request=request)
    db.commit()
    return result


@router.post("/run-digest")
def run_digest(request: Request, user: models.User = Depends(require_perm("manage_tasks")),
               db: Session = Depends(get_db)):
    """V2.2 §20 — تشغيل digest يومي يدويًا. يُشغَّل تلقائيًا كل يوم في 8 صباحًا. (عامٌّ لكل الشركات: يُقيَّد من شغّله)"""
    from ..notifications import digest_scan
    result = digest_scan(db)
    audit(db, user, "run_digest_manual", "system", None, request=request)
    db.commit()
    return result
