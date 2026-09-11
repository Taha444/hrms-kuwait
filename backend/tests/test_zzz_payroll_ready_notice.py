# -*- coding: utf-8 -*-
"""مسيٌَّر جاهز ولا يعلم به من يعتمده — ونٌّص أُعلن ولا يُرسَل.

**القياس**: لا ``payroll.py`` ولا ``routers/payroll.py`` ينشئ إشعاًرا
واحًدا — لا ``create_task`` ولا ``notify_``. فالمسيّر يُجهَّز ويقف عند
``prepared`` بانتظار معتمٍِد **لا شيء يخبره أن ينظر**. والقالب
``NTF-021`` «مسيّر الرواتب جاهز للمراجعة» مكتوٌب في كتالوج ``FIX-004``
منذ أُنشئ، ولم يُستدعَ قط.

وهو وجٌه من عطٍل أوسع قِسته: **خمسٌة وسبعون قالًبا معلَنًا، تسعَة عشر
منها يُرسَل**. تسٌع وعشرون من الصامتة تكراٌر لقوالب عامّة حيّة
(``NTF-033`` «{{request_type}} بانتظار موافقتك» يغطّي ثمانيَة عشر منها
بنصّها) — وتلك قاعدٌة في موضعين ينحرف ميُتها. وسبٌع وعشرون حدٌث **لا
إشعار له إطلاًقا**.

**وما لم أصله بقصد**: ``NTF-022`` «قسيمة راتبك جاهزة». فالموظف **لا
شاشَة له لقسيمة راتبه** — ``MyProfile`` تعرض الراتب الأساسي وحده،
و``/payroll`` محروسٌة بـ``view_payroll`` ولا يحملها الموظف. فوصُلها
رسالٌة تأمر بما لا تستطيعه الشاشة، وبناء الشاشة ميزٌة لا إصلاح. ويحرسه
``test_the_payslip_notice_stays_unwired_until_there_is_a_screen``.
"""
from __future__ import annotations

from sqlalchemy import delete as sa_delete, select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

ACC = ("100000000007", "account123")
OWNER = ("111111111111", "owner123")
#: إعادُة الفتح للإدارة العليا وحدها (``require_super_admin``) —
#: **قيست ولم تُفترض**: المحاسب يُردّ بـ403.
ADMIN = ("000000000000", "admin123")
PERIOD = "2031-03"
SECOND = "100000000777"


def _tasks(dedup_prefix: str) -> list[models.Task]:
    db = SessionLocal()
    try:
        return list(db.scalars(select(models.Task).where(
            models.Task.dedup_key.like(f"{dedup_prefix}%"))).all())
    finally:
        db.close()


def _purge(run_id: int | None = None) -> None:
    db = SessionLocal()
    try:
        db.execute(sa_delete(models.Task).where(
            models.Task.related_entity_type == "payroll_run"))
        if run_id is not None:
            db.execute(sa_delete(models.PayrollRun).where(
                models.PayrollRun.id == run_id))
        db.commit()
    finally:
        db.close()


def _prepare(client) -> tuple[int, dict]:
    hdr = auth_headers(login(client, *ACC))
    r = client.post(
        f"/api/payroll/run?period={PERIOD}&company_id=1&force_future=true&allow_open_attendance=true",
        headers=hdr)
    assert r.status_code == 200, r.text[:300]
    return r.json()["run_id"], hdr


def _second_accountant(company_id: int = 1) -> models.User:
    """محاسٌب ثاٍن — فصُل السلطات يقتضي اثنين، والبذُر يبذر واحًدا."""
    from app.security import hash_password

    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(
            models.User.civil_id == SECOND))
        if u is None:
            u = models.User(civil_id=SECOND,
                            password_hash=hash_password("acc2pass1"),
                            full_name="محاسب ثاٍن", role="accountant",
                            company_id=company_id, must_change_password=False)
            db.add(u)
            db.commit()
        return u
    finally:
        db.close()


def _drop_second() -> None:
    db = SessionLocal()
    try:
        u = db.scalar(select(models.User).where(models.User.civil_id == SECOND))
        if u is not None:
            db.delete(u)
            db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# الإشعار يُرسَل — ولمن يستطيع
# ---------------------------------------------------------------------------

def test_preparing_a_run_notifies_an_impartial_approver(client):
    """**جوهر البند**: مسيٌَّر يصير جاهًزا فيعلم به من يعتمده."""
    other = _second_accountant()
    run_id = None
    try:
        run_id, _ = _prepare(client)
        got = _tasks(f"payroll_ready:{run_id}:")
        assert got, "جُهِّز المسيّر ولم يُخطَر أحد"
        assert {t.assignee_user_id for t in got} == {other.id}, \
            [(t.assignee_user_id, t.title) for t in got]
    finally:
        _purge(run_id)
        _drop_second()


def test_the_notice_uses_the_declared_template(client):
    """ونٌّص مكتوٌب في الكتالوج يُستعمل — لا نٌّص ثاٍن بجانبه."""
    _second_accountant()
    run_id = None
    try:
        run_id, _ = _prepare(client)
        got = _tasks(f"payroll_ready:{run_id}:")
        assert got and all(t.template_code == "NTF-021" for t in got), \
            [t.template_code for t in got]
        assert PERIOD in (got[0].detail or ""), got[0].detail
    finally:
        _purge(run_id)
        _drop_second()


def test_the_preparer_is_never_asked_to_approve_his_own_run(client):
    """**ولا يُطلَب من أحٍد ما يمنعه فصُل السلطات منه.**

    فالمُجَهِّز محجوٌب عن الاعتماد (``_self_approval_blocked``)، ورسالٌة
    تطلب منه المراجعة تأمر بما لا يستطيعه.
    """
    _second_accountant()
    run_id = None
    try:
        run_id, _ = _prepare(client)
        db = SessionLocal()
        try:
            preparer = db.scalar(select(models.User).where(
                models.User.civil_id == ACC[0]))
        finally:
            db.close()
        got = _tasks(f"payroll_ready:{run_id}:")
        assert preparer.id not in {t.assignee_user_id for t in got}
    finally:
        _purge(run_id)
        _drop_second()


def test_the_rule_is_read_from_its_one_source():
    """والقاعدُة تُقرأ من موضعها لا تُكتب ثانيًة فتنحرف."""
    import inspect

    from app.routers import payroll as P

    src = inspect.getsource(P._notify_payroll_ready)
    assert "_self_approval_blocked" in src, "قاعدٌة ثانية لفصل السلطات"
    assert "ROLE_DEFAULT_PERMS" in src, "قائمٌة أدواٍر مكتوبة بالي;د"


# ---------------------------------------------------------------------------
# وعالٌق ظاهٌر خيٌر من عالٍق صامت
# ---------------------------------------------------------------------------

def test_a_run_with_no_impartial_approver_is_raised_not_buried(client):
    """**ومحاسٌب واحٌد يعني مسيًَّرا لا يعتمده أحد.**

    والبذُر يبذر محاسًبا واحًدا لكل شركة، فهذه هي حالُة الإنتاج الأرجح:
    فصُل السلطات يمنع من جهّزه، ولا ثانَي له. فيُرفَع إلى المالك ثغرَة
    إعداد بصراحة — على نسق ``_warn_no_impartial_approver`` في الطلبات.
    """
    _drop_second()
    run_id = None
    try:
        run_id, _ = _prepare(client)
        gap = _tasks(f"payroll_no_impartial:{run_id}")
        assert gap, "مسيٌَّر بلا معتمٍِد وُقِف صامًتا"
        assert all(t.severity == "critical" for t in gap), [t.severity for t in gap]
        db = SessionLocal()
        try:
            owner = db.scalar(select(models.User).where(
                models.User.civil_id == OWNER[0]))
        finally:
            db.close()
        assert owner.id in {t.assignee_user_id for t in gap}
        # ولا يُرسَل «راجِع» إلى من لا يستطيع المراجعة.
        assert not _tasks(f"payroll_ready:{run_id}:")
    finally:
        _purge(run_id)


def test_reopening_asks_for_approval_again(client):
    """**وإعادُة الفتح تُعيد الحاجة إلى معتمِد** — فتُعيد الإخطار."""
    other = _second_accountant()
    run_id = None
    try:
        run_id, hdr = _prepare(client)
        db = SessionLocal()
        try:
            for t in db.scalars(select(models.Task).where(
                    models.Task.dedup_key.like(f"payroll_ready:{run_id}:%"))).all():
                t.status = "done"          # اعتمد ثم أُعيد الفتح
            pr = db.get(models.PayrollRun, run_id)
            pr.status = "approved"
            pr.approved_by_user_id = other.id
            db.commit()
        finally:
            db.close()

        r = client.post(f"/api/payroll/runs/{run_id}/reopen",
                        params={"reason": "تصحيح بدل"},
                        headers=auth_headers(login(client, *ADMIN)))
        assert r.status_code == 200, r.text[:300]
        again = [t for t in _tasks(f"payroll_ready:{run_id}:")
                 if t.status != "done"]
        assert again, "أُعيد الفتح ولم يُخطَر معتمٌِد"
    finally:
        _purge(run_id)
        _drop_second()


def test_preparing_twice_does_not_pile_up_notices(client):
    """ولا يتراكم «راجِع» مرتين لمسيٍّر واحد — البصمُة تحرسه."""
    _second_accountant()
    run_id = None
    try:
        run_id, _ = _prepare(client)
        first = len(_tasks(f"payroll_ready:{run_id}:"))
        again, _ = _prepare(client)
        assert again == run_id, (run_id, again)
        assert len(_tasks(f"payroll_ready:{run_id}:")) == first
    finally:
        _purge(run_id)
        _drop_second()


# ---------------------------------------------------------------------------
# وما لم يوصَل بقصد
# ---------------------------------------------------------------------------

def test_the_payslip_notice_stays_unwired_until_there_is_a_screen():
    """**``NTF-022`` لا تُوصَل ما لم تُبنَ الشاشة.**

    «قسيمة راتب {{period}} متاحة للعرض» — والموظف لا شاشَة له يعرضها
    فيها. فهذا الحارس يوثّق القرار: إن بُنيت شاشُة القسيمة فليُوصَل
    القالب، وحتى ذلك الحين **لا تُرسَل رسالٌة تأمر بما لا تستطيعه
    الشاشة**.
    """
    import pathlib
    import re

    root = pathlib.Path("app")
    blob = "".join(p.read_text(encoding="utf-8") for p in root.rglob("*.py")
                   if p.name != "notification_templates.py")
    wired = "NTF-022" in blob

    mine = pathlib.Path("../frontend/src/pages/MyProfile.tsx")
    screen = bool(mine.exists()
                  and re.search("payslip|قسيمة", mine.read_text(encoding="utf-8")))

    assert wired == screen, (
        "قالُب القسيمة وشاشتها لا يفترقان: "
        f"موصوٌل={wired} وشاشٌة للموظف={screen}")


# ---------------------------------------------------------------------------
# وتحذيٌر لا يصل لا يُفرَّق عن الصمت
# ---------------------------------------------------------------------------

def test_escalation_is_not_scoped_to_a_company_that_has_no_overseer():
    """**العطُل الذي كشفه هذا الحارس، في موضعين.**

    المالك والإدارة العليا ``company_id = None`` — فهما فوق الشركات
    (``CROSS_COMPANY_ROLES``). وكان كلا التصعيدين يستعلم
    ``users_by_role(db, company_id, [...])``، والاستعلام يقيّد
    ``User.company_id == company_id`` — **فيعيد قائمًة فارغة دائًما**.

    فكان «طلٌب سرّي بلا معتمٍِد محايد» في مسار الطلبات يُصعَّد إلى لا
    أحد. وتحذيٌر لا يصل لا يُفرَّق عن الصمت الذي بُني ليمنعه.
    """
    from app.notifications import oversight_users
    from app.permissions import CROSS_COMPANY_ROLES

    db = SessionLocal()
    try:
        # **لا يُؤكَّد أن الاستعلام المقيَّد فارغ**: سويٌت أخرى قد تُسنِد
        # مالًكا إلى الشركة 1 بحّق، فيصير ذلك التأكيدُ حارًسا يحمل العطل.
        # المقصود أدقّ: **من هو فوق الشركات يُشمَل، لا يُستثنى بنطاق.**
        above = list(db.scalars(select(models.User).where(
            models.User.role.in_(sorted(CROSS_COMPANY_ROLES)),
            models.User.company_id.is_(None),
            models.User.is_active == True)).all())  # noqa: E712
        overseers = {u.id for u in oversight_users(db, 1)}
    finally:
        db.close()
    assert above, "افتراض القياس: النظام يحمل مشرًفا فوق الشركات"
    missing = [u.civil_id for u in above if u.id not in overseers]
    assert not missing, f"تصعيٌد لا يصل إلى من هو فوق الشركات: {missing}"


def test_both_escalations_read_the_one_overseer_rule():
    """والقاعدُة في موضٍع واحد — لا نسخٌة في المسيّر وأخرى في الطلبات."""
    import inspect

    from app import workflow
    from app.routers import payroll as P

    for fn in (workflow._warn_no_impartial_approver, P._notify_payroll_ready):
        src = inspect.getsource(fn)
        assert "oversight_users" in src, fn.__name__
        assert 'users_by_role(db, req.company_id, ["company_owner"' not in src
        assert 'users_by_role(db, pr.company_id, ["company_owner"' not in src


def test_an_escalation_reaches_every_overseer_not_just_the_first():
    """**وبصمٌة واحدٌة لعدّة مستقبلين تحجب كلَّ من بعد الأول.**

    ``create_task`` لا يكرّر بصمًة لمهمٍة مفتوحة، فبصمٌة لا تحمل
    المستقبِل تجعل التحذير يصل إلى واحٍد ويُسقَط عن الباقين — وهو ما
    وقع في التصعيدين حتى أُلحقت ``:u{id}`` كما يفعل ``notify_roles``.
    """
    import inspect

    from app import workflow
    from app.routers import payroll as P

    for fn in (workflow._warn_no_impartial_approver, P._notify_payroll_ready):
        src = inspect.getsource(fn)
        for line in src.splitlines():
            if "dedup_key=" in line and "u{u.id}" not in line and "u{u.id}" not in src:
                raise AssertionError(f"بصمٌة بلا مستقبِل في {fn.__name__}: {line.strip()}")
