# -*- coding: utf-8 -*-
"""M23 #2 — أرقامٌ لاتينيةٌ في كل مكان: التواريخ بلغة ``ar-EG`` كانت تُعرض بأرقامٍ هندية (٢٠٢٦) بجانب مبالغَ ورقمٍ مدنيٍّ لاتينيّ.

الحارس يقيس السلوك الفعليّ في node: التنسيقُ العربيّ يُخرج أرقامًا لاتينيةً بتوقيت الكويت.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"


def test_no_screen_formats_with_a_locale_that_renders_indic_digits():
    offenders = []
    for p in SRC.rglob("*.ts*"):
        text = p.read_text(encoding="utf-8")
        for m in re.finditer(r"\"(ar(?:-[A-Z]{2})?)\"", text):
            # ``ar`` وحدها/``ar-EG`` بلا لاحقة nu-latn تُخرج أرقامًا هندية عند التنسيق
            ctx = text[max(0, m.start() - 40):m.end() + 5]
            if "toLocale" in ctx or "Intl." in ctx:
                offenders.append((p.name, m.group(0)))
    assert not offenders, f"تنسيقٌ بأرقامٍ هندية: {offenders}"


@pytest.mark.skipif(shutil.which("node") is None, reason="node غير متاح")
def test_the_arabic_date_format_uses_latin_digits_in_kuwait_time():
    dt = (SRC / "utils" / "datetime.ts").read_text(encoding="utf-8")
    m = re.search(r'lang === "en" \? "en-GB" : "([^"]+)"', dt)
    assert m, "لم يُوجَد محدّد اللغة"
    js = ('const d=new Date("2026-09-25T20:26:59Z");'
          f'console.log(d.toLocaleString("{m.group(1)}",{{timeZone:"Asia/Kuwait",year:"numeric",month:"2-digit",'
          'day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}));')
    proc = subprocess.run(["node", "-e", js], capture_output=True, text=True, encoding="utf-8")
    out = proc.stdout or ""
    assert proc.returncode == 0 and out, (proc.returncode, proc.stderr[:200])
    assert re.search(r"2026", out) and "23:26" in out, out
    assert not re.search("[\u0660-\u0669]", out), f"أرقامٌ هندية: {out!r}"
