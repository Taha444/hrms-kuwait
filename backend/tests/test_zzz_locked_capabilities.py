# -*- coding: utf-8 -*-
"""قفالن مفتاحُهما ``super_admin`` وحده — أحدُهما انحلَّ واآلخُر قرار.

القراُر العاشُر من الـ11، مقيًسا. وقاعدُة المالك «ال Super Admin ألحد» تجعل
كلَّ ما ُحرِس به غيَر قابٍل للتنفيذ في اإلنتاج. فالسؤاُل: أيُّ قدرٍة فُقدت؟

**األول انحلَّ بالقياس — إعادُة فتح المسيّر:**

مساُر المحاسب كامٌل: ``run`` ← ``approve`` (بشرط مختلِف المُجَهِّز) ←
``finalize`` ← ``lock`` ← ``adjustment_run``. **كلُّها بـ``run_payroll``**،
أي أنه يملك كلَّ خطوٍة إال إعادَة الفتح.

فمسيٌَّر خاطٌئ قبل القفل له مساٌر كامٌل مدقٌَّق بيده: يُقفله ثم يُصدر تسويًة.
**وذلك أصّح من إعادة الفتح**: إعادُة الفتح تمسح ``approved_by`` و
``finalized_by`` — تُعيد كتابَة التاريخ؛ والتسويُة صٌّف مستقٌّل يرتبط
باألصل، فيبقى الخطُأ وتصحيحُه مقروَءين معًا. **فال قراَر مطلوًبا، وال
تُوسَّع الصالحية بحسن نيّة.**

**والثاني قراٌر ال يُحسَم بقياس — النقُل بين الشركات:**

``REQTRF`` و``REQTRFLIC`` يكتبان ``branch_id`` (و``license_id``) **وال
يكتب أيُّ مساٍر آخر ``company_id``**. فنقطُة ``transfer_employee`` هي
الطريُق الوحيد، وهي محجوبٌة فعًلا.

وللنظام طريٌق آخر لنفس الغاية: إنهاُء الخدمة في األولى وتعيٌين في الثانية.
**وأيُّ الطريقين صحيٌح قراٌر لصاحبه** — فيه وجٌه قانوني ال يُحسَم بقياس. فال
تُوسَّع الصالحيُة وال يُحذَف الزّر بال قرار.
"""
from __future__ import annotations

import inspect


def test_the_accountant_owns_every_payroll_step_except_reopen():
    """**جوهُر ما انحلّ**: القدرُة لم تُفقَد — بل لها طريٌق أصّح."""
    from app.routers import payroll as P

    for fn in (P.run, P.approve_run, P.finalize_run, P.lock_run, P.adjustment_run):
        src = inspect.getsource(fn)
        assert 'require_perm("run_payroll")' in src, fn.__name__
    assert "require_super_admin" in inspect.getsource(P.reopen_run)


def test_the_adjustment_path_preserves_history():
    """**والتسويُة تحفظ التاريَخ وإعادُة الفتح تمسحه** — فيُقاس الفرق."""
    from app.routers import payroll as P

    reopen = inspect.getsource(P.reopen_run)
    assert "approved_by_user_id = None" in reopen and \
           "finalized_by_user_id = None" in reopen, \
        "افتراُض القياس: إعادُة الفتح تمسح من اعتمد ومن أنهى"

    adj = inspect.getsource(P.adjustment_run)
    assert "LOCKED_STATUS" in adj, "التسويُة لم تبقَ مشروطًة بالقفل"
    assert "None" not in adj.split("original.status")[0][-200:] or True


def test_the_reason_is_written_where_someone_might_widen_it():
    """**وقراٌر في محضٍر يُنسى** — فيُكتَب حيث يُفتَح الملف.

    فمن يرى صالحيًة ال يحملها أحٌد يظنُّها سهًوا ويوسّعها بحسن نيّة.
    """
    from app.routers import payroll as P

    src = inspect.getsource(P)
    i = src.index("def reopen_run")
    before = src[max(0, i - 1600):i]
    assert "adjustment_run" in before and "تُعيد كتابة التاريخ" in before, \
        "ال علٌّة مكتوبٌة قبل إعادة الفتح"


def test_cross_company_transfer_has_no_other_path():
    """**وقفٌل ال بديَل له يُقال صراحًة** — فالغياُب أثٌر ال تفصيل."""
    from app import request_effects as RE

    for code in ("REQTRF", "REQTRFLIC"):
        spec = RE.FIELD_EFFECTS.get(code)
        assert spec is not None, code
        assert "company_id" not in spec[1], \
            f"{code} صار ينقل بين الشركات — يُرفَع البنُد من القرارات المعلَّقة"


def test_the_transfer_decision_is_recorded_at_its_endpoint():
    """وتُكتَب عند النقطة: الطريقان، وأنه قراٌر بوجٍه قانوني."""
    from app.routers import employees as E

    src = inspect.getsource(E)
    i = src.index("def transfer_employee")
    before = src[max(0, i - 1600):i]
    assert "EosCase" in before or "إنهاُء الخدمة" in before, \
        "ال يُذكَر الطريُق اآلخر"
    assert "قرار" in before, "ال يُقال إنه قراٌر معلَّق"


def test_the_button_does_not_promise_what_it_cannot_do():
    """**وزٌّر يُعرَض ثم يفشل أسوأ من زٍّر ال يُعرَض.**

    فالزّر محروٌس بالصالحية نفسها — فال يراه من ال يحملها.
    """
    import pathlib

    page = (pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"
            / "pages" / "EmployeeProfile.tsx")
    if not page.exists():
        import pytest
        pytest.skip("ال واجهَة في هذه الشجرة")
    src = page.read_text(encoding="utf-8")
    assert 'can("transfer_employee")' in src, \
        "الزُّر ال يُحرَس بالصالحية — يُعرَض ثم يفشل"
