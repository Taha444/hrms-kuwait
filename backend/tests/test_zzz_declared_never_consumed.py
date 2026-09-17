# -*- coding: utf-8 -*-
"""حقٌل يُقبَل في الـAPI ولا يقرؤه شيء — وعٌد في المخطَّط لا يُوفى.

**القياس**: أربعٌة وثمانون ومئتان من حقول المدخلات، ستٌّ لا يقرؤها شيٌء
ظاهًرا. ثلاٌث منها زائفٌة (``token_type`` قياسيّ، وأثُر تحليٍل خاطئ)،
واثنتان حقيقيَّتان — **ولكلٍّ منهما أثٌر مختلف**:

**١) ``Branch.auto_checkout_minutes``** — عمٌود على الفرع، افتراضُه خمَس
عشرة دقيقة، يقبله ``BranchIn`` و``BranchUpdate``، **ولا يقرؤه موضٌع واحد**
ولا تعرضه الواجهة. وهو العلاُج المصمَّم لسلسلٍة تنتهي بالمال:

- الانصراُف **بلا قيد تاريخ**: يأخذ أحدَث سجٍّل مفتوٍح ويُغلقه بـ``now``.
- ``_finalize_out`` يحسب الدقائَق فرَق اللحظتين **بلا سقف**، ثم
  ``overtime = worked − shift``.
- و``payroll`` يدفع ``hourly × 1.25 × (overtime / 60)`` في ``gross``.

فنسياٌن يُغلَق بعد أربٍع وعشرين ساعًة = خمَس عشرة ساعَة إضافّي = **66.436
د.ك** على متوسط الراتب في هذه القاعدة. والقياُس في
``scripts/overtime_exposure.py``.

**٢) ``Employee.actual_license_id``** «ترخيُص الدوام الفعلي» — عمٌود ومُدخٌَل،
**لم يُملأ قطّ** (صفٌر من ستٍّ وعشرين)، ولا ترسله الواجهة، ولا يقرؤه شيء.
وسعُة الترخيص تُعَدّ بـ``license_id`` (ترخيُص التسجيل) — وهو الصحيُح
قانونًيا للسعة. فهذا حقُل **تعرٍُّض تفتيشي**: من يعمل على غير ترخيصه.
والمخطَُّط يوهم أن النظاَم يتابعه.

**ولماذا يُحرَسان هنا ال في ``test_zzz_dead_columns``**: ذاك الكنُس يستثني
كلَّ عموٍد ينتهي بـ``_id`` (وإال أنذر على كل مفتاٍح أجنبّي يُستعمل
بالعالقات) — وهناك مكتوٌب أن بديله **حاٌرس مخصَّص**، وأن المخصَّص أدقُّ من
قائمٍة ال يمسّها الكنس. وهذا هو.

**وال يُصلَح أٌّي منهما بال كلمة**: الأوُل يغيّر رقًما يُدفَع (Payroll لا
يُمسّ بلا اعتماد)، والثاني يحتاج قراًرا عن **ماذا** يفعله النظاُم بالفرق.
فيُحرَسان ليُريا: من يبنيهما يبنيهما بقصد، ومن يتركهما يتركهما بقصد.
"""
from __future__ import annotations

import pathlib
import re

from app import models

BE = pathlib.Path(__file__).resolve().parents[1] / "app"
FE = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"

#: حقٌل معلٌَن ال يقرؤه شيء — ولكلٍّ **سببُه وأثرُه** مكتوًبا.
_DECLARED_NEVER_CONSUMED = {
    # ``actual_license_id`` بُني تنبيهًا تفتيشيًا بقرار المالك (2026-09-17) —
    # وحارسُه السلوكي في ``test_zzz_license_mismatch``.
}


def _consumers(field: str) -> list[str]:
    """مواضُع تقرأ الحقَل **قراءًة عاملة** — لا تعريًفا ولا شرًحا."""
    out = []
    for p in sorted(BE.rglob("*.py")):
        if p.name in ("models.py", "schemas.py"):
            continue
        for i, ln in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            stripped = ln.lstrip()
            if stripped.startswith("#") or '"""' in ln or "``" in ln:
                continue
            if re.search(rf"\b\w+\.{re.escape(field)}\b", ln) or \
               re.search(rf"\b{re.escape(field)}\s*=", ln):
                out.append(f"{p.relative_to(BE.parent)}:{i}")
    return out


def test_each_declared_field_is_still_unconsumed():
    """**الحارُس الأصلي**: ما قيل عنه «لا يُقرأ» يبقى كذلك — أو يُرفَع.

    فإن صار له قارٌئ سقط الحارس: يُنظَر هل بُني العلاُج فعًلا (فيُرفَع من
    القائمة ويُكتَب حارسُه السلوكي)، أم أُسند سهًوا.
    """
    revived = {f: _consumers(f)[:3] for f in _DECLARED_NEVER_CONSUMED
               if _consumers(f)}
    assert not revived, ("حقوٌل صار يقرؤها شيٌء — فتُرفَع من القائمة ويُكتَب "
                         f"لها حاٌرس سلوكي:\n{revived}")


def test_the_fields_are_still_declared_at_all():
    """**وحقٌل حُذف ال يُحرَس** — فتُنظَّف القائمُة ولا تبقى تحرس عدًما."""
    missing = [f for f in _DECLARED_NEVER_CONSUMED
               if not hasattr(models.Branch, f) and not hasattr(models.Employee, f)]
    assert not missing, f"حقوٌل لم تعد معلَنًة: {missing}"


# ``auto_checkout_minutes`` وسقفُ الإضافي بُنيا بقرار المالك (2026-09-17) —
# وحارساهما السلوكيّان في ``test_zzz_overtime_approval``.


def test_the_manual_remedy_still_has_no_screen():
    """**وعلاٌج بال باٍب يُسمّى** — ``correct`` موجوٌد وال شاشَة تناديه.

    فإن بُنيت الشاشُة سقط الحارس، فيُصحَّح ما يُقال عن هذا البند.
    """
    if not FE.exists():
        import pytest
        pytest.skip("ال واجهَة في هذا المسار")
    callers = [str(p.relative_to(FE)) for p in FE.rglob("*.ts*")
               if "/correct" in p.read_text(encoding="utf-8", errors="ignore")]
    assert not callers, f"صارت للتصحيح شاشة: {callers}"


# بدلُ الإنذار كان هنا حارسًا «مبنيٌّ ومنفصل». وقد رُبط بقرار المالك
# (2026-09-17) — والحارسُ الذي يقيس مقداره في ``test_zzz_notice_pay``.
