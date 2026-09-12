# -*- coding: utf-8 -*-
"""مسيّر الرواتب: حساب شهري + دورة اعتماد متدرجة + قسائم.

PILOT-P0-7 — دورة الرواتب الآمنة:
    prepared → approved → finalized → locked
    (adjustment_run كبديل عند الحاجة بعد lock)

قواعد الأمان:
- company_id إلزامي — لا "All Companies" لتشغيل الرواتب
- المُجَهِّز ≠ المُعتمِد النهائي (فصل السلطات)
- مسيّر واحد لكل (شركة، فترة) — لا تكرار
- Archived employees مستبعدون تلقائيًا في compute_payroll
- بعد قفل الفترة لا يُعدَّل عليها — يجب adjustment_run منفصل
"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, payroll as payroll_engine
from ..database import get_db
from ..deps import audit, require_perm, require_super_admin, scope_company_id
from ..clock import today as kuwait_today

router = APIRouter(prefix="/payroll", tags=["payroll"])

# دورة الرواتب — الترتيب المسموح فقط:
# prepared → approved → finalized → locked
# adjustment_run دخول جانبي بعد lock (تسويات لاحقة)
STATUS_ORDER = {"prepared": 0, "approved": 1, "finalized": 2, "locked": 3, "adjustment_run": 3}
LOCKED_STATUS = "locked"


def _parse_period(period: str) -> tuple[int, int]:
    try:
        y, m = (int(x) for x in period.split("-"))
        if not (1 <= m <= 12):
            raise ValueError
        return y, m
    except Exception:
        raise HTTPException(status_code=400, detail="صيغة الفترة يجب أن تكون YYYY-MM")


def _company(user: models.User, company_id: int | None) -> int:
    cid = scope_company_id(user, company_id)
    if cid is None:
        raise HTTPException(status_code=400, detail="يجب تحديد الشركة لتشغيل المسيّر")
    return cid


#: PR-UI — رسالة فصل السلطات: **مكتوبة مرّة** ويقرؤها المنع والشاشة معًا.
#: كتابتها في الخادم وحده يجعل الشاشة تعرض زًرا يفشل؛ وكتابتها في
#: الشاشة وحدها يجعل نصّين لقاعدة واحدة ينحرفان.
SELF_APPROVAL_BLOCK = "لا يمكنك اعتماد مسيّر جهّزته بنفسك — فصل السلطات إلزامي"


def _self_approval_blocked(user: models.User, pr: models.PayrollRun) -> bool:
    """هل يمنعه فصل السلطات من اعتماد هذا المسيّر؟"""
    return pr.prepared_by_user_id == user.id and user.role != "super_admin"


def _notify_payroll_ready(db: Session, pr: models.PayrollRun) -> None:
    """NTF-021 — **مسيٌَّر يصير جاهًزا ولا يعلم به من يعتمده.**

    كان ``payroll.py`` و``routers/payroll.py`` لا يُنشئان إشعاًرا واحًدا:
    لا ``create_task`` ولا ``notify_``. فالمسيّر يُجهَّز ويقف عند
    ``prepared`` بانتظار مُعتمٍِد **لا شيء يخبره أن ينظر**. والقالب
    ``NTF-021`` «مسيّر الرواتب جاهز للمراجعة» مكتوٌب في الكتالوج منذ
    ``FIX-004`` ولم يُستدعَ قط — نٌّص أُعلن ولا يُرسَل.

    ولا يُخطَر به من جهّزه: فصُل السلطات يمنعه من اعتماده، فرسالٌة تطلب
    منه ما لا يستطيعه. **والقاعدة تُقرأ من موضعها** —
    ``_self_approval_blocked`` نفسها التي يحتكم إليها المنع — لا تُكتب
    ثانيًة هنا فتنحرف.

    وإن لم يبقَ محايٌد، فالمسيّر عالٌق: يُرفَع إلى المالك ثغرَة إعداد،
    على نسق ``_warn_no_impartial_approver`` في مسار الطلبات. **وعالٌق
    ظاهٌر خيٌر من عالٍق صامت.**
    """
    from ..notifications import (create_task, notify_from_template, oversight_users,
                                 users_by_role)
    from ..permissions import ROLE_DEFAULT_PERMS

    roles = [r for r, perms in ROLE_DEFAULT_PERMS.items() if "run_payroll" in perms]
    impartial = [u for u in users_by_role(db, pr.company_id, roles)
                 if not _self_approval_blocked(u, pr)]

    if not impartial:
        for u in oversight_users(db, pr.company_id):
            create_task(
                db, company_id=pr.company_id, type="config_gap",
                assignee_user_id=u.id, severity="critical",
                title="مسيّر رواتب بلا معتمٍِد محايد",
                detail=(f"مسيّر {pr.period} جاهٌز ولا يوجد من يعتمده: فصُل "
                        f"السلطات يمنع من جهّزه من اعتماده. أسنِد صلاحية "
                        f"«تشغيل الرواتب» لشخٍص آخر لتمضي المعالجة."),
                related_entity_type="payroll_run", related_entity_id=pr.id,
                # **وبصمٌة واحدٌة لعدّة مستقبلين تحجب كلَّ من بعد الأول** —
                # فتُلحَق بمعرّف المستقبِل، كما يفعل ``notify_roles``.
                dedup_key=f"payroll_no_impartial:{pr.id}:u{u.id}",
            )
        return

    for u in impartial:
        notify_from_template(
            db, code="NTF-021", assignee_user_id=u.id, company_id=pr.company_id,
            context={"period": pr.period},
            related_entity_type="payroll_run", related_entity_id=pr.id,
            dedup_key=f"payroll_ready:{pr.id}:u{u.id}", severity="warning")


@router.get("/preview")
def preview(period: str, request: Request, company_id: int | None = None,
            user: models.User = Depends(require_perm("view_payroll")),
            db: Session = Depends(get_db)):
    y, m = _parse_period(period)
    cid = _company(user, company_id)
    result = payroll_engine.compute_payroll(db, cid, y, m)
    audit(db, user, "view_payroll_preview", "company", cid, detail=result["period"], request=request)
    db.commit()
    return result


@router.post("/run")
def run(period: str, request: Request, company_id: int | None = None, force_future: bool = False,
        allow_open_attendance: bool = False,
        user: models.User = Depends(require_perm("run_payroll")),
        db: Session = Depends(get_db)):
    """PILOT-P0-7 — تجهيز مسيّر جديد بحالة `prepared` (مش finalized مباشرة).
    يحتاج للاعتماد المنفصل عبر `/runs/{id}/approve` من مستخدم مختلف."""
    y, m = _parse_period(period)
    cid = _company(user, company_id)

    # منع الشهر المستقبلي بدون استثناء صريح
    today = kuwait_today()
    if (y, m) > (today.year, today.month) and not force_future:
        raise HTTPException(status_code=400,
                            detail="لا يمكن تشغيل مسيّر لشهر مستقبلي دون تأكيد صريح (force_future)")

    # ATT-07 / DLV-01 — لا مسيّر على فترة حضور لم تُغلَق.
    #
    # ROOT CAUSE: المسيّر كان يُحسب على حضور لم يُراجَع — أيام بلا سجل،
    # وتصحيحات معلّقة، وإجازات لم تُعتمَد. ثم يُصرف ويُكتشف الخطأ في راتب
    # موظف، والتصحيح بعد الصرف أصعب من منعه بكثير.
    #
    # allow_open_attendance مخرج صريح لحالة مبرَّرة، ويُسجَّل في التدقيق —
    # لا إعداد صامت يُنسى.
    from .. import attendance_close
    if not allow_open_attendance and not attendance_close.is_closed(db, cid, period):
        pending = attendance_close.unrecorded_day_count(db, cid, period)
        raise HTTPException(status_code=409, detail=(
            f"فترة الحضور {period} لم تُغلَق بعد ({pending} يوم بلا سجل). "
            "أغلقها من مراجعة الحضور أوًلا، أو مرّر allow_open_attendance=true "
            "بمسؤوليتك."))
    if allow_open_attendance and not attendance_close.is_closed(db, cid, period):
        audit(db, user, "payroll_run_on_open_attendance", "company", cid,
              detail=f"period={period}", request=request)

    result = payroll_engine.compute_payroll(db, cid, y, m)

    existing = db.scalar(select(models.PayrollRun).where(
        models.PayrollRun.company_id == cid, models.PayrollRun.period == result["period"]))
    if existing:
        # لا نسمح بإعادة التجهيز فوق مسيّر متقدّم عن prepared — يحتاج adjustment_run صريح
        if existing.status in ("approved", "finalized", "locked"):
            raise HTTPException(
                status_code=409,
                detail=(f"مسيّر هذه الفترة في حالة '{existing.status}' — يجب adjustment_run "
                        "بدل إعادة التجهيز فوقه"))
        existing.totals_json = result
        existing.status = "prepared"
        existing.prepared_by_user_id = user.id
        existing.prepared_at = datetime.utcnow()
        run_id = existing.id
    else:
        pr = models.PayrollRun(
            company_id=cid, period=result["period"],
            status="prepared", totals_json=result,
            prepared_by_user_id=user.id, prepared_at=datetime.utcnow(),
        )
        db.add(pr)
        db.flush()
        run_id = pr.id
    audit(db, user, "prepare_payroll", "payroll_run", run_id,
          detail=result["period"], request=request)
    db.commit()
    # **بعد الالتزام**: لا يُخطَر بمسيٍّر لم يُكتب بعد.
    _notify_payroll_ready(db, db.get(models.PayrollRun, run_id))
    db.commit()
    return {"ok": True, "run_id": run_id, "status": "prepared", **result}


@router.post("/runs/{run_id}/approve")
def approve_run(run_id: int, request: Request,
                user: models.User = Depends(require_perm("run_payroll")),
                db: Session = Depends(get_db)):
    """PILOT-P0-7 — اعتماد المسيّر (prepared → approved) بشرط مختلف المُجَهِّز."""
    from ..deps import assert_same_company
    pr = db.get(models.PayrollRun, run_id)
    if not pr:
        raise HTTPException(status_code=404, detail="المسيّر غير موجود")
    assert_same_company(user, pr.company_id, db=db)
    if pr.status != "prepared":
        raise HTTPException(status_code=409,
                            detail=f"لا يمكن اعتماد مسيّر في حالة '{pr.status}' — يجب أن يكون prepared")
    if _self_approval_blocked(user, pr):
        raise HTTPException(status_code=403, detail=SELF_APPROVAL_BLOCK)
    pr.status = "approved"
    pr.approved_by_user_id = user.id
    pr.approved_at = datetime.utcnow()
    audit(db, user, "approve_payroll_run", "payroll_run", pr.id,
          detail=pr.period, request=request)
    db.commit()
    return {"ok": True, "status": "approved"}


@router.post("/runs/{run_id}/finalize")
def finalize_run(run_id: int, request: Request,
                 user: models.User = Depends(require_perm("run_payroll")),
                 db: Session = Depends(get_db)):
    """PILOT-P0-7 — finalize بعد الاعتماد (approved → finalized). قابل للـlock بعده.
    SEC2-17: يمنع finalize في وضع STRICT فقط (SEC2_17_STRICT_FINALIZE=true)."""
    import os
    from ..deps import assert_same_company
    from sqlalchemy import or_
    pr = db.get(models.PayrollRun, run_id)
    if not pr:
        raise HTTPException(status_code=404, detail="المسيّر غير موجود")
    assert_same_company(user, pr.company_id, db=db)
    if pr.status != "approved":
        raise HTTPException(status_code=409,
                            detail=f"يجب أن يكون المسيّر approved قبل finalize (الحالي: {pr.status})")
    if os.environ.get("SEC2_17_STRICT_FINALIZE", "").lower() in ("1", "true", "yes"):
        unresolved = db.scalar(select(models.Employee).where(
            models.Employee.company_id == pr.company_id,
            models.Employee.status == "active",
            models.Employee.attendance_mode == "none",
            or_(models.Employee.attendance_exempt.is_(False),
                models.Employee.attendance_exempt.is_(None)),
        ).limit(1))
        if unresolved:
            raise HTTPException(
                status_code=409,
                # ATT-POL — كانت الرسالة تسمّي **مساًرا خاًما** لا شاشة له:
                # نصٌّ داخلي يتسرّب للمستخدم، وأمٌر بفعل بلا باب. صارت
                # تسمّي الشاشة التي تفعله فعًلا.
                detail=(f"لا finalize قبل توثيق سياسة حضور كل الموظفين (مثال: {unresolved.name}). "
                        "افتح «مراجعة الحضور» ← «موظفون بلا سياسة حضور» وثبّت سياسة كلٍّ منهم.")
            )
    pr.status = "finalized"
    pr.finalized_by_user_id = user.id
    pr.finalized_at = datetime.utcnow()
    audit(db, user, "finalize_payroll_run", "payroll_run", pr.id,
          detail=pr.period, request=request)
    db.commit()
    return {"ok": True, "status": "finalized"}


@router.post("/runs/{run_id}/lock")
def lock_run(run_id: int, request: Request,
            user: models.User = Depends(require_perm("run_payroll")),
            db: Session = Depends(get_db)):
    """يقفل المسيّر نهائًيا (finalized → locked). بعد Lock يجب adjustment_run بدل إعادة التشغيل."""
    from ..deps import assert_same_company

    pr = db.get(models.PayrollRun, run_id)
    if not pr:
        raise HTTPException(status_code=404, detail="المسيّر غير موجود")
    assert_same_company(user, pr.company_id, db=db)
    if pr.status != "finalized":
        raise HTTPException(status_code=409, detail="يجب أن يكون المسيّر بحالة finalized قبل القفل")
    pr.status = LOCKED_STATUS
    pr.locked_by_user_id = user.id
    pr.locked_at = datetime.utcnow()
    audit(db, user, "lock_payroll_run", "payroll_run", pr.id, detail=pr.period, request=request)
    db.commit()
    return {"ok": True, "status": pr.status}


@router.post("/runs/{run_id}/reopen")
#: **ولماذا تبقى إعادُة الفتح للإدارة العليا وحدها — قياٌس لا تضييق.**
#:
#: قيس مساُر المحاسب كامًلا: ``run`` ← ``approve`` (بشرط مختلِف المُجَهِّز)
#: ← ``finalize`` ← ``lock`` ← ``adjustment_run``. **كلُّها بـ
#: ``run_payroll``**، أي أن المحاسب يملك كلَّ خطوٍة إلا هذه.
#:
#: فمسيٌَّر خاطٌئ قبل القفل له مساٌر كامٌل مدقٌَّق بيده: يُقفله ثم يُصدر
#: تسويًة. **وذلك المساُر أصّح من إعادة الفتح**: إعادُة الفتح تمسح
#: ``approved_by`` و``finalized_by`` — أي **تُعيد كتابة التاريخ**؛
#: والتسويُة تُقيَّد صًفّا مستقًّلا يرتبط بالأصل، فيبقى الخطُأ وتصحيحُه
#: مقروَءين معًا. وهو ما تقتضيه المحاسبة.
#:
#: فقاعدُة المالك «لا Super Admin لأحد» لا تُعطِّل شيًئا هنا — تعني: **لا
#: نُعيد كتابة تاريخ الرواتب، بل نُصدر تسوية.** فلا تُوسَّع هذه الصلاحية
#: بحسن نيّة: توسيعُها يفتح محَو تاريٍخ لا يحتاجه أحد.
def reopen_run(run_id: int, reason: str, request: Request,
              user: models.User = Depends(require_super_admin),
              db: Session = Depends(get_db)):
    """P0-#8 — إعادة فتح مسيّر (approved/finalized → prepared) لتصحيح خطأ قبل الـlock.

    القيود:
    - super_admin فقط (Business impact عالي).
    - reason إلزامي — يظهر في audit مع correlation_id.
    - locked ما يُعاد فتحه — يحتاج adjustment_run بدل ذلك.
    - يمسح الـapproved/finalized markers (لكن يحتفظ prepared_by/at الأصليين).
    """
    from ..deps import assert_same_company
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="سبب إعادة الفتح مطلوب")
    pr = db.get(models.PayrollRun, run_id)
    if not pr:
        raise HTTPException(status_code=404, detail="المسيّر غير موجود")
    assert_same_company(user, pr.company_id, db=db)
    if pr.status not in ("approved", "finalized"):
        raise HTTPException(status_code=409, detail=(
            f"لا يمكن إعادة فتح مسيّر بحالة '{pr.status}'. "
            "المسموح: approved أو finalized. الـlocked يحتاج adjustment_run."
        ))

    before_status = pr.status
    pr.status = "prepared"
    # نمسح markers المراحل اللاحقة — الاعتماد لازم يُعاد
    pr.approved_by_user_id = None
    pr.approved_at = None
    pr.finalized_by_user_id = None
    pr.finalized_at = None
    audit(db, user, "reopen_payroll_run", "payroll_run", pr.id,
          detail=f"from={before_status} reason={reason.strip()}", request=request,
          correlation_id=f"payroll:{pr.id}",
          before={"status": before_status},
          after={"status": "prepared", "reason": reason.strip()})
    db.commit()
    # **وإعادُة الفتح تُعيد الحاجة إلى معتمِد** — فتُعيد الإخطار.
    _notify_payroll_ready(db, pr)
    db.commit()
    return {"ok": True, "status": "prepared", "reopened_from": before_status}


@router.post("/runs/{run_id}/adjustment")
def adjustment_run(run_id: int, reason: str, request: Request,
                   user: models.User = Depends(require_perm("run_payroll")),
                   db: Session = Depends(get_db)):
    """PILOT-P0-7 — تسوية بعد الـlock: ينشئ سجل adjustment_run منفصل يرتبط بالأصلي.
    السبب إلزامي ويتسجل في audit."""
    from ..deps import assert_same_company
    if not reason or not reason.strip():
        raise HTTPException(status_code=400, detail="سبب التسوية مطلوب")
    original = db.get(models.PayrollRun, run_id)
    if not original:
        raise HTTPException(status_code=404, detail="المسيّر الأصلي غير موجود")
    assert_same_company(user, original.company_id, db=db)
    if original.status != LOCKED_STATUS:
        raise HTTPException(status_code=409,
                            detail="التسويات تُنشأ فقط بعد قفل المسيّر الأصلي")
    y, m = _parse_period(original.period)
    result = payroll_engine.compute_payroll(db, original.company_id, y, m)
    pr = models.PayrollRun(
        company_id=original.company_id,
        period=f"{original.period}-ADJ-{original.id}",  # تمييز التسوية
        status="adjustment_run", totals_json=result,
        prepared_by_user_id=user.id, prepared_at=datetime.utcnow(),
        adjustment_of_run_id=original.id, adjustment_reason=reason.strip(),
    )
    db.add(pr)
    db.flush()
    audit(db, user, "payroll_adjustment_run", "payroll_run", pr.id,
          detail=f"of={original.id} reason={reason}", request=request)
    db.commit()
    return {"ok": True, "run_id": pr.id, "status": pr.status,
            "adjustment_of": original.id}


@router.get("/runs")
def list_runs(company_id: int | None = None,
              user: models.User = Depends(require_perm("view_payroll")),
              db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    q = select(models.PayrollRun)
    if cid is not None:
        q = q.where(models.PayrollRun.company_id == cid)
    rows = db.scalars(q.order_by(models.PayrollRun.period.desc())).all()

    # PR-UI — الصفّ يحمل ما يكفي الشاشة لتعرض **خطوة تالية أو سبب توقّف**.
    #
    # كانت القائمة تعيد الحالة وحدها ولا شيء غيرها، والشاشة تعرضها كلها
    # بلون النجاح بلا زرّ واحد. فالمسيّر يُجهَّز ولا يُعتمَد ولا يُقفَل ولا
    # يُقفل نهائًيا — دورة حياة كاملة بلا مخرج من الواجهة.
    #
    # والأعلام تُحسب من نفس الشروط التي يفرضها المنع (``_self_approval_blocked``)
    # لا من نسخة ثانية منها: زرٌّ يظهر ثم يفشل بـ403 أسوأ من زرّ غائب.
    from ..deps import get_user_perms
    from ..permissions import has_permission

    perms = get_user_perms(user, db)
    may_run = has_permission(user.role, perms, "run_payroll")
    names = {u.id: u.full_name for u in db.scalars(select(models.User).where(
        models.User.company_id == (cid or user.company_id)))}

    out = []
    for r in rows:
        self_blocked = may_run and r.status == "prepared" and _self_approval_blocked(user, r)
        out.append({
            "id": r.id, "period": r.period, "status": r.status,
            "totals": (r.totals_json or {}).get("totals"),
            "employees_count": (r.totals_json or {}).get("employees_count"),
            "created_at": r.created_at,
            "prepared_by": names.get(r.prepared_by_user_id),
            "prepared_at": r.prepared_at,
            "approved_by": names.get(r.approved_by_user_id),
            "approved_at": r.approved_at,
            "finalized_at": r.finalized_at,
            "locked_at": r.locked_at,
            "adjustment_of_run_id": r.adjustment_of_run_id,
            "adjustment_reason": r.adjustment_reason,
            "can_approve": bool(may_run and r.status == "prepared" and not self_blocked),
            "can_finalize": bool(may_run and r.status == "approved"),
            "can_lock": bool(may_run and r.status == "finalized"),
            "can_reopen": bool(user.role == "super_admin"
                               and r.status in ("approved", "finalized")),
            "can_adjust": bool(may_run and r.status == LOCKED_STATUS),
            # سبب التوقّف يُسمّى، فلا يقف المستخدم أمام صفٍّ بلا زرّ ولا تفسير.
            "blocked_reason": SELF_APPROVAL_BLOCK if self_blocked else None,
        })
    return out


@router.get("/runs/{run_id}")
def get_run(run_id: int, user: models.User = Depends(require_perm("view_payroll")),
            db: Session = Depends(get_db)):
    pr = db.get(models.PayrollRun, run_id)
    if not pr:
        raise HTTPException(status_code=404, detail="المسيّر غير موجود")
    from ..deps import assert_same_company
    assert_same_company(user, pr.company_id, db=db)
    return pr.totals_json or {}
