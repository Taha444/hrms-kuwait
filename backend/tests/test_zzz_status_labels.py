# -*- coding: utf-8 -*-
"""حالٌة يكتبها الخادم ولا تسمّيها الواجهة — فيُعرَض الكود تسميًة.

``labels.ts`` تبني ``statusAr`` من خريطٍة، والدالُة **تُعيد المفتاح نفسه
عند الغياب**::

    const M = (m) => (k) => { const p = m[k]; return p ? p[getLang()] : k; };

فالحالُة غير المسمّاة لا تُخرِج خطًأ ولا فراًغا: تُخرِج كوَدها الإنجليزي
داخل شاشٍة عربية، **فيبدو الكود تسميًة مقصودة**. والملُف نفسه يوثّق هذا
العطَل لحالات المسيّر (``prepared`` · ``finalized``) وقد أُصلحت.

**وبقيت واحدة، وهي أحوجُها إلى اسم**: ``apply_failed`` — طلٌب اكتملت
موافقاته **ولم يقع أثره على البيانات**. يُكتب في ``workflow.py:2179``،
ويحمل الخادم لافتته «فشل التطبيق — يحتاج إجراء» في ``STATUS_MAP``،
ويُصدرها على ``/api/requests/status-map`` — **ولا تنادي الواجهة ذلك
المسار**، ولا تعرف الحالة. فكان المستخدم يرى «apply_failed» في قائمة
الطلبات وفي تفصيلها، في أخطر حالٍة يحتاج فهمها.

والمخرُج من الحالة موصوٌل (``retry-apply`` وزّره في ``RequestDetail``)،
فالنقُص كان في الاسم وحده.
"""
from __future__ import annotations

import pathlib
import re

import pytest

FRONT = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"
LABELS = FRONT / "labels.ts"

#: حالاٌت تُكتب على صفوٍف غير الطلب (المسيّر، طلب تعديل الراتب) وتُعرض
#: بلافتٍة خاّصة بشاشتها لا بـ``statusAr`` — تُستثنى بقياٍس لا بحدس.
_NOT_VIA_STATUS_AR = {"applied", "active"}


def _status_ar_keys() -> set[str]:
    """مفاتيُح ``statusAr`` — تُقرأ من الكتلة وحدها لا من الملف كلّه."""
    src = LABELS.read_text(encoding="utf-8")
    start = src.index("export const statusAr")
    end = src.index("});", start)
    return set(re.findall(r"(\w+)\s*:\s*\{\s*ar\s*:", src[start:end]))


def _statuses_written_to_requests() -> dict[str, set[str]]:
    """الحالاُت التي يكتبها الخادم فعًلا على الطلب — بالقياس لا بقائمة."""
    root = pathlib.Path(__file__).resolve().parents[1] / "app"
    pat = re.compile(r'(?:req|request)\.status\s*=\s*"([a-z_]+)"')
    out: dict[str, set[str]] = {}
    for p in root.rglob("*.py"):
        for m in pat.finditer(p.read_text(encoding="utf-8")):
            out.setdefault(m.group(1), set()).add(p.name)
    return out


@pytest.mark.skipif(not LABELS.exists(), reason="لا واجهَة في هذه الشجرة")
def test_every_status_the_server_writes_has_an_arabic_name():
    """**جوهر البند**: لا حالَة تُعرض بكودها الإنجليزي.

    والقياس من الشيفرة: ما يُكتب على ``Request.status`` فعًلا، لا قائمٌة
    تُحفَظ بالي;د فتنحرف عمّا يجري.
    """
    written = _statuses_written_to_requests()
    named = _status_ar_keys()
    missing = sorted(s for s in written
                     if s not in named and s not in _NOT_VIA_STATUS_AR)
    assert not missing, (
        "حالاٌت يكتبها الخادم ولا تسمّيها الواجهة (تُعرض بكودها): "
        + ", ".join(f"{s} ← {sorted(written[s])}" for s in missing))


@pytest.mark.skipif(not LABELS.exists(), reason="لا واجهَة في هذه الشجرة")
def test_the_failed_apply_status_is_named_as_the_server_names_it():
    """**ولا تُقرأ الحالُة الواحدة باسمين.**

    فالخادم يحمل لافتتها في ``STATUS_MAP`` ويُصدرها على ``status-map``،
    فاسُم الواجهة هو اسُمه لا ترجمٌة ثانية له.
    """
    from app.workflow import STATUS_MAP

    src = LABELS.read_text(encoding="utf-8")
    server = STATUS_MAP["apply_failed"]["label"]
    assert "apply_failed:" in src, "الحالة ما زالت بلا اسم"
    assert server in src, f"اسٌم ثاٍن للحالة — نصُّ الخادم: {server!r}"


@pytest.mark.skipif(not LABELS.exists(), reason="لا واجهَة في هذه الشجرة")
def test_the_label_function_still_falls_back_to_the_key():
    """**افتراُض القياس يُثبَّت**: الدالة تُعيد المفتاح عند الغياب.

    فلو صارت تُخرِج فراًغا أو ترفع خطًأ، تغيّر شكُل العطل ووجب إعادة
    كتابة الحارس — لا أن يمضي وهو يقيس ما لم يبقَ.
    """
    src = LABELS.read_text(encoding="utf-8")
    assert "return p ? p[getLang()] : k;" in src, \
        "تغيّر سلوُك الغياب في statusAr — يُعاد النظر في هذا الحارس"


@pytest.mark.skipif(not LABELS.exists(), reason="لا واجهَة في هذه الشجرة")
def test_the_status_this_guard_was_written_for_is_still_reachable():
    """وحارٌس يحرس حالًة لم تبقَ حارٌس بلا عمل — فيُقاس أنها تُكتب."""
    assert "apply_failed" in _statuses_written_to_requests(), \
        "لم يعد الخادم يكتب apply_failed — يُراجع هذا الملف"
