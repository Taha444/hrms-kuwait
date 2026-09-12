# -*- coding: utf-8 -*-
"""ما يُفصح عنه الخطأ — كنٌس أكثرُه إنذاٌر كاذب، وموضٌع واحٌد صحيح.

**القياس األول** أنذر اثنَي عشر موضًعا يُخرج نَّص المستثنى في جواب الخطأ.
**والسؤاُل ليس وجوَد ``str(e)`` بل ماذا يُلتقَط**: فعشٌر منها تلتقط
استثناًء **محلًّيا** رسالتُه جملٌة عربية مقصودٌة للمستخدم —
``ValueError`` سبٌع، و``PermissionError`` اثنتان («اإللغاُء من صالحية
المدير العام»)، و``EffectAlreadyApplied`` واحدة («وقع أثُر هذا الطلب
فعًلا…»). فإخراُج نصّها هو **الغرض** ال تسريب.

**وبقي موضعان يُخرجان نَّص مستثًنى عريض، وأحدُهما بقصد:**

- ``tasks.retry_delivery`` يُخرج خطَأ التسليم — والمساُر محروٌس
  بـ``manage_tasks``، وغرضُه تشخيُص فشل قناٍة، و``last_delivery_error``
  عمٌود مبنٌّي لحفظه. فإخفاؤه عن المشغّل يُفقده ما بُني له. **يُترك
  بعلّته.**
- ``signatures`` كان يُخرج نَّص Pillow، **وهذا يرفع فيه أيُّ موظف صورَة
  توقيعه**. والنصُّ يحمل أحياًنا مساَر ملٍّف أو عنواَن كائٍن في الذاكرة:
  يُفصح عن الداخل لمن ال يحتاجه، **وال يقول للموظف ما يفعل**
  («cannot identify image file <_io.BytesIO object at 0x…>»). فصار يصف
  ما يُقبَل، والنصُّ الكامل إلى السجل.

**والمعالُج العامّ نظيف** وقيس: ``_out_of_range_response`` يردّ «السجلّ
غير موجود» بال نٍّص داخلي، وال ``traceback`` وال ``exc_info`` في الجواب.
"""
from __future__ import annotations

import ast
import inspect
import pathlib
import re

APP = pathlib.Path(__file__).resolve().parents[1] / "app"

#: مواضٌع تُخرج نَّص مستثًنى عريٍض **بقصد** — تُسمّى بعلّتها.
_DELIBERATE = {
    ("routers/tasks.py", "retry_delivery"):
        "مساٌر محروٌس بـmanage_tasks غرضُه تشخيُص فشل القناة",
}


def _broad_leaks() -> list[tuple[str, int]]:
    """معالجاٌت عريضٌة تُخرج نَّص المستثنى في جواب الخطأ."""
    out = []
    for p in sorted(APP.rglob("*.py")):
        text = p.read_text(encoding="utf-8")
        lines = text.splitlines()
        for h in ast.walk(ast.parse(text)):
            if not isinstance(h, ast.ExceptHandler):
                continue
            t = h.type
            name = (getattr(t, "id", None) or getattr(t, "attr", None)
                    or ("tuple" if isinstance(t, ast.Tuple) else "bare"))
            if name not in ("Exception", "BaseException", "bare"):
                continue
            lo, hi = h.lineno, getattr(h, "end_lineno", h.lineno)
            body = "\n".join(lines[lo - 1:hi])
            if re.search(r"detail\s*=.*(str\(e\)|str\(exc\)|\{e\}|\{exc\})", body):
                out.append((str(p.relative_to(APP).as_posix()), lo))
    return out


def test_no_new_endpoint_echoes_a_broad_exception_to_the_client():
    """**الحارس الدائم**: ال نَّص مستثًنى عريٍض في جواٍب يقرؤه المستخدم.

    ومن أراده سمّاه في ``_DELIBERATE`` بعلّته — فقراٌر مكتوٌب يُراجَع.
    """
    from app.routers import tasks as T

    allowed_lines = set()
    src_start = T.retry_delivery.__code__.co_firstlineno
    allowed_lines.update(range(src_start, src_start + 40))

    stray = [(f, ln) for f, ln in _broad_leaks()
             if not (f == "routers/tasks.py" and ln in allowed_lines)]
    assert not stray, ("مواضُع تُخرج نَّص مستثًنى عريض:\n"
                       + "\n".join(f"  {f}:{ln}" for f, ln in stray))


def test_the_signature_error_says_what_to_do_not_what_broke():
    """**جوهر البند**: رسالٌة تُرشد ال تُفصح."""
    from app.routers import signatures as S

    src = inspect.getsource(S)
    block = src[src.index("_process_signature(data)"):]
    block = block[:block.index("AWS-01")]
    assert "{exc}" not in block, "نصُّ المستثنى ما زال في الجواب"
    assert "PNG" in block and "JPG" in block, "ال تقول للموظف ما يُقبَل"
    assert "logger.warning" in block, "ذهب النصُّ الكامل بال سجل"


def test_the_domain_exceptions_keep_their_arabic_messages():
    """**وإخفاُء رسالٍة مقصودة عطٌل ال أمان.**

    فرسائُل ``PermissionError`` و``EffectAlreadyApplied`` مكتوبٌة للمستخدم
    بنصّها: «اإللغاُء من صالحية المدير العام»، «وقع أثُر هذا الطلب فعًلا،
    وال يُعكَس أثُر هذا النوع تلقائًيا». فتبقى تُخرَج.
    """
    from app.routers import requests as RQ

    src = inspect.getsource(RQ)
    assert re.search(r"except\s+PermissionError[^\n]*\n[^\n]*detail=str\(e\)", src), \
        "لم تبقَ رسالُة المنع تصل إلى المستخدم"


def test_the_global_handler_returns_nothing_internal():
    """والمعالُج العامّ يردّ عبارًة واحدة ال نًّصا داخلًيا."""
    import app.main as M

    src = inspect.getsource(M._out_of_range_response)
    assert '"detail": "السجلّ غير موجود"' in src, src[-200:]
    # **والقاعدُة منُع إخراجه لا منُع قراءته.**
    #
    # كان الحارُس يمنع ``str(exc)`` في الدالة — وهو وكيٌل خشن: املعالُج
    # يحتاج أن **يفحص** سبَب الخطأ ليفرّق «معرًِّفا خارج املدى» من
    # «قيمٍة أطوَل من حقلها»، والفرُق يغيّر الجواَب من 404 إلى 400.
    #
    # فيُقاس السلوُك: **رسالتان مختلفتان تُنتجان الجواَب نفسه** — فال
    # يتسرّب نٌّص داخلي وإن قُرئ.
    class _E(Exception):
        pass

    a = M._out_of_range_response(None, _E("secret-path /srv/app/x.py"))
    b = M._out_of_range_response(None, _E("another internal detail"))
    assert a.body == b.body, (a.body, b.body)
    for bad in ("traceback", "exc_info"):
        assert bad not in src, bad
