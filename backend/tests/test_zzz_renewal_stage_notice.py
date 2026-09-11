# -*- coding: utf-8 -*-
"""بوّابٌة تنتظر فاعًلا لا يعلم أنها تنتظره.

**القياس**: كُنِست آلُة حاالت تجديد الإقامة — اثنتا عشرة حالة — بحًثا عن
باٍب بلا مخرج. ولم يكن فيها باٌب مسدود: كلُّ حالٍة تُكتب تُقرأ.

**لكنّ الكنس كشف ما هو أدقّ**: ``_notify_stage`` سلسلٌة من
``if/elif`` على الحالة، و``PENDING_HR_VERIFY`` **ليست فيها**. وكلا
الانتقالين إليها (رفُع البطاقة المدنية، وإدخاُل بيانات الحكومة) **ينادي**
``_notify_stage`` — فيقع النداء ولا يُرسَل شيء.

وهي **آخُر بوّابة قبل الإغلاق**: الشؤون تطابق رقم الإقامة الجديد وتاريخه
والرسوم ثم تُغلق. والنظاُم يعرف الفاعل — ``STAGE_ACTOR`` يقول «شؤون
الموظفين» — **ولا يخبره**. فتبقى المعاملة ساكنًة حتى يمرّ عليها أحٌد
بالمصادفة، وهو سبُب سكون المعاملات عند هذه المرحلة بعينها.

**وبصمٌة ناقصٌة كانت ستُبطل الإصلاح**: ``_close_superseded_stage_tasks``
تُبقي بصمَة المرحلة الحالية وتُغلق ما عداها. و``STAGE_TASK_PREFIX`` لم
تحمل هذه الحالة، فلو أُرسل الإشعار بلا بصمٍة معروفة **أُغلق في النداء
نفسه الذي أنشأه**. فأُضيفت البصمة مع الفرع.

**وحالتان ميّتتان قِستُهما ولم أحذفهما**: ``NEW`` و``WITH_DELEGATE`` لا
يكتبهما شيء — الإنشاُء يسنِد ``PENDING_MANAGER`` للمبكر و
``AWAITING_CONTRACTS`` للعادي دائًما، و``WITH_DELEGATE`` اسٌم نُسخ معناه
إلى ``AWAITING_CONTRACTS``. و``NEW`` لا تُبلَغ إلا من **افتراض العمود**
في ``models.py`` — فهي فٌّخ كامٌن لا عطٌل قائم. تُحرَس هنا بالقياس فلا
يُبنى عليها، ويُرصَد إن صارت تُكتب.

**وما لم يكن عطًلا قيل كما هو**:

- ``REJECTED`` لا فرَع لها في ``_notify_stage``، **والرفُض يُخطِر الموظف
  في موضع القرار نفسه** بسببه — فلا نقص.
- و``RENEWING`` يكتبها المندوب بفعله، ولا فاعَل جديد يُخطَر.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete as sa_delete, select

from app import models, renewal as R
from app.database import SessionLocal


def _hr_ids(company_id: int = 1) -> set[int]:
    db = SessionLocal()
    try:
        return {u.id for u in db.scalars(select(models.User).where(
            models.User.role == "hr", models.User.company_id == company_id,
            models.User.is_active == True)).all()}  # noqa: E712
    finally:
        db.close()


def _case(status: str) -> int:
    db = SessionLocal()
    try:
        emp = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1))
        rn = models.ResidencyRenewal(company_id=1, employee_id=emp.id,
                                     status=status)
        db.add(rn)
        db.commit()
        return rn.id
    finally:
        db.close()


def _cleanup(rid: int) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Task).where(
            models.Task.related_entity_type == "renewal",
            models.Task.related_entity_id == rid))
        db.execute(sa_delete(models.ResidencyRenewal).where(
            models.ResidencyRenewal.id == rid))
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# البوّابة تُخطِر فاعلها
# ---------------------------------------------------------------------------

def test_the_verification_gate_tells_hr_it_is_waiting():
    """**جوهر البند**: آخُر بوّابٍة قبل الإغلاق تُخطِر من يفتحها."""
    from app.routers.renewals import _notify_stage

    rid = _case(R.PENDING_HR_VERIFY)
    try:
        db = SessionLocal()
        try:
            _notify_stage(db, db.get(models.ResidencyRenewal, rid))
            db.commit()
            got = db.scalars(select(models.Task).where(
                models.Task.related_entity_type == "renewal",
                models.Task.related_entity_id == rid,
                models.Task.status.in_(("open", "in_progress")))).all()
            assignees = {t.assignee_user_id for t in got}
        finally:
            db.close()
        assert got, "وصلت المعاملة إلى التحقّق ولم يُخطَر أحد"
        assert assignees & _hr_ids(), (assignees, _hr_ids())
    finally:
        _cleanup(rid)


def test_the_notice_survives_the_superseded_task_sweep():
    """**وبصمٌة ناقصٌة تُغلق ما أُرسل للتوّ.**

    فـ``_close_superseded_stage_tasks`` تُبقي بصمَة المرحلة الحالية
    وتُغلق ما عداها — ومرحلٌة بلا بصمٍة في ``STAGE_TASK_PREFIX`` تُغلَق
    مهمُّتها في النداء نفسه الذي أنشأها.
    """
    from app.routers.renewals import STAGE_TASK_PREFIX, _notify_stage

    assert R.PENDING_HR_VERIFY in STAGE_TASK_PREFIX, "المرحلة بلا بصمة"

    rid = _case(R.PENDING_HR_VERIFY)
    try:
        db = SessionLocal()
        try:
            rn = db.get(models.ResidencyRenewal, rid)
            _notify_stage(db, rn)
            _notify_stage(db, rn)          # نداٌء ثاٍن: لا يُغلق ولا يُكرّر
            db.commit()
            live = db.scalars(select(models.Task).where(
                models.Task.related_entity_type == "renewal",
                models.Task.related_entity_id == rid,
                models.Task.status.in_(("open", "in_progress")))).all()
        finally:
            db.close()
        assert live, "أُغلقت المهمُّة في النداء الذي أنشأها"
        assert len(live) == len(_hr_ids()), [t.dedup_key for t in live]
    finally:
        _cleanup(rid)


def test_every_stage_with_a_declared_actor_is_notified():
    """**والقاعدُة أعمّ من موضعها**: مرحلٌة يُعلَن لها فاعٌل تُخطِره.

    ``STAGE_ACTOR`` يعلن من يقوم بكل مرحلة. فمرحلٌة لها فاعٌل معلٌن ولا
    فرَع لها في ``_notify_stage`` بوّابٌة تنتظر من لا يعلم — وهو العطل
    بعينه. وتُستثنى بعلّتها فقط.
    """
    import inspect

    from app.routers import renewals as RN

    src = inspect.getsource(RN._notify_stage)
    #: يُخطَر فاعلُها في موضع القرار لا في هذه الدالة، أو لا فاعَل جديد لها.
    excused = {
        R.REJECTED: "الرفُض يُخطِر الموظف بسببه في موضع القرار",
        R.RENEWING: "يكتبها المندوب بفعله — لا فاعَل جديد",
        R.NEW: "حالٌة ميّتة: افتراُض العمود ولا ينشئها شيء",
        R.WITH_DELEGATE: "حالٌة ميّتة: نُسخ معناها إلى AWAITING_CONTRACTS",
    }
    missing = []
    for status, who in RN.STAGE_ACTOR.items():
        if not who or who == "—" or status in excused:
            continue
        const = next((k for k, v in vars(R).items()
                      if k.isupper() and v == status), None)
        if const and f"R.{const}" not in src:
            missing.append((status, who))
    assert not missing, f"مراحُل لها فاعٌل معلٌن ولا تُخطِره: {missing}"


# ---------------------------------------------------------------------------
# والحالتان الميّتتان تبقيان ميّتتين
# ---------------------------------------------------------------------------

def test_the_dead_states_are_still_dead():
    """**فٌّخ كامٌن يُرصَد لا يُبنى عليه.**

    ``NEW`` لا تُبلَغ إلا من افتراض العمود، ولا انتقاَل منها. فلو صار
    شيٌء يكتبها، سقط هذا الحارس معلًنا أنها صارت حالًة حّية تحتاج مخرًجا.
    """
    import pathlib
    import re

    app = pathlib.Path(__file__).resolve().parents[1] / "app"
    blob = "".join(p.read_text(encoding="utf-8") for p in app.rglob("*.py"))
    for const in ("NEW", "WITH_DELEGATE"):
        value = getattr(R, const)
        assert not re.search(rf'status\s*=\s*(?:R\.)?{const}\b', blob), \
            f"{const} صارت تُكتب — تحتاج فرًعا في _notify_stage ومخرًجا"
        assert not re.search(rf'status\s*=\s*"{value}"', blob), const


def test_the_column_default_is_the_only_way_into_new():
    """**وافتراُض العمود هو الفّخ نفسه** — يُقاس فلا يُنسى.

    فأيُّ صٍّف يُنشأ بلا حالٍة يُولَد في ``new``: لا فرَع يُخطِره، ولا
    انتقاَل منه. والإنشاُء في المسار يسنِد الحالة صراحًة دائًما.
    """
    import inspect

    from app.routers import renewals as RN

    src = inspect.getsource(RN.create_renewal) if hasattr(RN, "create_renewal") else ""
    if not src:
        src = "".join(inspect.getsource(RN).split("ResidencyRenewal(")[1][:400])
    assert "status=" in src, "الإنشاء لا يسنِد حالًة — فتُولَد المعاملة في new"

    col = models.ResidencyRenewal.__table__.c.status
    assert col.default is not None and col.default.arg == R.NEW, \
        "تغيّر افتراُض العمود — يُعاد النظر في هذا الحارس"
