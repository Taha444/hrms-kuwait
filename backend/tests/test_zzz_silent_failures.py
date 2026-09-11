# -*- coding: utf-8 -*-
"""مستثنًى يُلتقط فيُبتلع — كنٌس نتيجُته سالبة، وتُقال كما هي.

كُنِست ثلاٌث وأربعون معالجًة عريضة (``except Exception``) في ``app/``،
**ولم يكن فيها عطٌل واحد**. كلُّها تراجٌع مقصود بشرحه في موضعه:

- ``deps.py`` — ``iat`` تالٌف لا يمنع الوصول «لأسباب موازية».
- ``workflow.py`` — فشُل سجلّ المخوَّلين يسقط إلى آخر معتمٍِد والطباعُة تمضي.
- ``documents.py`` — حجٌم يُقرأ من التخزين، وغياُبه ``None`` لا صفًرا
  «فالصفر رقٌم يُقرأ».
- ``token_revocation.py`` — الخروُج ينجح دائًما من جهة المستخدم.
- ``storage.py`` — ``exists()`` تُعيد ``False`` لا ترفع.
- ``main.py`` و``admin.py`` — فحوُص الصحة تُخرِج «تعذّر» في حمولتها، وهي
  **بلاٌغ لا صمت**.

**وكنسي أنذر كاذًبا ثلاث مرات، فأُصلح القياس في كل مرة**:

1. ``apply_due_effects`` بدت تبتلع، وهي تُسجِّل الفشل في قيمتها المُعادة
   و``scheduler`` يكتبها في السجل.
2. وأكثُر ما بدا «بلا شرح» **مستثًنى ضّيق يُعيد فشًلا**::

       except (TypeError, ValueError):
           return False, f"مبلغ غير صالح: {p.get('amount')!r}"

   والنوُع الضيّق هو شرحُه، والإعادُة تقريٌر لا ابتلاع.
3. ثم طلب حارٌس كتبتُه عرًفا جديًدا (علٌّة مكتوبة) على خمسَة عشر موضًعا
   معقول. **وحاٌرس يسقط على شيفرٍة سليمة حاٌرس يُحذَف** — فأُنزل إلى حجمه:
   الكنُس أداٌة للمراجعة (``scripts/silent_failures.py``)، والحرّاس على ما
   يهمّ فعًلا.

**والتحسيُن الوحيد** هنا: رسُم صورة التوقيع كان يفشل بلا سطر. والموظف
يذهب إلى الشؤون في الحالين (قرار المالك: رسالٌة واحدة تسع الحالين) فلا
يمسّه — لكنّ فشًلا عاًمّا في القراءة (مجلُّد رفٍع تغيّر، أو صيغٌة لا تُقرأ)
يطبع **كلَّ** الأوراق فارغًة ولا يعلم به مشغّل. وهو من يستطيع إصلاحه.
"""
from __future__ import annotations

import inspect


def test_the_signature_render_failure_is_logged():
    """**فشٌل عامٌّ في الطباعة يراه المشغّل.**

    فمجلُّد رفٍع تغيّر يطبع كلَّ الأوراق فارغًة، ولا يعلم به إلا من يُصلحه.
    """
    from app import pdf_export

    src = inspect.getsource(pdf_export.ArabicPDF.signatures)
    assert "logger.warning" in src, "فشُل رسم التوقيع ما زال صامًتا"
    # ولا يُبدَّل السلوك: المكاُن يبقى فارًغا كما لو لم يوجد توقيع.
    assert "raise" not in src.split("except Exception")[-1][:400], \
        "صار الفشل يُسقِط الطباعة — والورقُة تُطبَع بخطٍّ فارغ بقرار المالك"


def test_the_deferred_sweep_reports_its_failures():
    """**وأثٌر مؤجٌَّل يفشل يُعَدّ ويُسجَّل** — لا يُطوى في صمت."""
    from app import request_effects, scheduler

    fn = inspect.getsource(request_effects.apply_due_effects)
    assert "failed.append" in fn, "الفشل لا يُحتسَب"
    sch = inspect.getsource(scheduler._run_daily_scan)
    assert 'due["failed"]' in sch, "المسح لا يقرأ فشل الآثار المؤجَّلة"


def test_the_daily_scan_itself_shouts_when_it_dies():
    """**ومسٌح يومّي يموت صامًتا يُسكِت النظام كلَّه.**

    فعليه هذه الجولُة كلُّها: التنبيهاُت والآثاُر المؤجَّلة وتصعيُد الـSLA.
    فيُقاس أنه يرفع صوته لا يكتفي بالسقوط.
    """
    from app import scheduler

    src = inspect.getsource(scheduler._run_daily_scan)
    assert "logger.exception" in src and "_alert_job_failure" in src, src[-400:]


def test_the_sweep_tool_exists_for_review():
    """والكنُس يبقى أداًة يُشغّلها إنسان — لا حارًسا يفرض عرًفا.

    فالمواضُع العريضة معقولٌة كما هي، والأداُة تُطبعها لمن يراجع.
    """
    import pathlib

    tool = (pathlib.Path(__file__).resolve().parents[1]
            / "scripts" / "silent_failures.py")
    assert tool.exists(), "ذهبت أداُة المراجعة"


def test_the_sqlite_foreign_keys_are_actually_on():
    """**ومفاتيُح أجنبية «تُفعَّل» ولا تُقاس قد تكون مطفأة.**

    ``PRAGMA foreign_keys=ON`` خاٌصّ بـSQLite، وكان يُنفَّذ على أيّ قاعدة
    ثم يُبتلع خطؤه: فعلى Postgres في الإنتاج يُرفَع استثناٌء ويُبتلع **عند
    كل اتصال**، وعلى SQLite فشلٌه صامٌت يعني أن المفاتيح **مطفأة**
    فتُقبَل صفوٌف يتيمة — وهو عين ما وُضعت لتمنعه.

    فهذا الحارس لا يقرأ الشيفرة: **يسأل القاعدة**.
    """
    from sqlalchemy import text

    from app.database import SessionLocal, _IS_SQLITE

    if not _IS_SQLITE:
        import pytest
        pytest.skip("القاعدة ليست SQLite — المحرّك يفرض المفاتيح بنفسه")

    db = SessionLocal()
    try:
        on = db.execute(text("PRAGMA foreign_keys")).scalar()
    finally:
        db.close()
    assert on == 1, f"المفاتيح الأجنبية مطفأة (PRAGMA={on!r})"
