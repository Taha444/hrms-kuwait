# -*- coding: utf-8 -*-
"""الواجهة الإنجليزية — قرار المالك (2026-09-17): ترجمةٌ كاملة، ولا يعود نصٌّ عربيٌّ مكتوبٌ مباشرة.

كانت الشاشاتُ تحمل مئاتِ الأسطر العربية خارج القاموس، فلا تتبدّل عند اختيار
الإنجليزية. فنُقلت إلى ``i18n_screens.ts`` (ومعها ``tr()`` للوحدات التي ليست
مكوّنات). وهذا الحارسُ يمنع عودتها:

- لا سطرَ فيه حرفٌ عربيّ خارج: التعليقات، والقواميس، والثلاثيّ الذي يحمل
  اللغتين (``isEn ? … : …``)، وكائنات ``{ ar, en }``، وما وُسم ``i18n: data``
  (قيمةٌ مخزَّنة أو محتوى مستند لا نصُّ واجهة).
- كلُّ مفتاحٍ حرفيٍّ يُمرَّر إلى ``t()``/``tr()`` موجودٌ في القاموس — وإلا
  ظهر اسمُ المفتاح نفسُه للمستخدم.
- ولكلِّ مدخلٍ نصٌّ إنجليزيٌّ غيرُ فارغ ولا عربيَّ فيه.
- والقاموسُ المحليُّ في شاشةٍ (``i18n: local-dictionary``) كتلتاه بالمفاتيح نفسها.

ولا يشمل رسائلَ الخادم (``detail``) ولا تسمياتِه — تلك عربيةٌ من الخادم.
"""
from __future__ import annotations

import pathlib
import re

import pytest

SRC = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "src"
AR = re.compile("[؀-ۿ]")
BIL = re.compile(r"isEn|isAr|lang\s*===?\s*[\"'](?:en|ar)[\"']")
PAIR = re.compile(r"\bar:\s*[\"'`]")
DICTS = {"i18n.tsx", "labels.ts", "i18n_screens.ts"}

pytestmark = pytest.mark.skipif(not SRC.exists(), reason="لا واجهة في هذا المسار")


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)
    out = []
    for ln in text.splitlines():
        i, q, cut = 0, None, len(ln)
        while i < len(ln):
            c = ln[i]
            if q:
                if c == "\\":
                    i += 2
                    continue
                if c == q:
                    q = None
            elif c in "\"'`":
                q = c
            elif ln.startswith("//", i):
                cut = i
                break
            i += 1
        out.append(ln[:cut])
    return "\n".join(out)


def _sources():
    return [p for p in sorted(SRC.rglob("*.ts*")) if p.name not in DICTS]


def test_no_hard_coded_arabic_in_the_screens():
    hits = []
    for p in _sources():
        raw_text = p.read_text(encoding="utf-8")
        if "i18n: local-dictionary" in raw_text:
            continue
        raw = raw_text.splitlines()
        lines = _strip_comments(raw_text).splitlines()
        for n, ln in enumerate(lines, 1):
            if not AR.search(ln) or "i18n: data" in raw[n - 1]:
                continue
            if BIL.search(" ".join(lines[max(0, n - 4):n])):
                continue
            if PAIR.search(ln) and "en:" in " ".join(lines[n - 1:n + 3]):
                continue
            hits.append(f"{p.relative_to(SRC)}:{n}: {ln.strip()[:90]}")
    assert not hits, ("نصٌّ عربيٌّ مكتوبٌ مباشرة — انقله إلى i18n_screens.ts:\n"
                      + "\n".join(hits[:40]))


def _dictionary():
    keys = {}
    for name in ("i18n.tsx", "i18n_screens.ts"):
        txt = (SRC / name).read_text(encoding="utf-8")
        for m in re.finditer(r"\b([A-Za-z0-9_]+): \{\s*ar:\s*(\"(?:[^\"\\]|\\.)*\")\s*,\s*en:\s*(\"(?:[^\"\\]|\\.)*\")",
                             txt, re.S):
            keys[m.group(1)] = (m.group(2), m.group(3))
    return keys


def test_every_literal_key_exists():
    keys = _dictionary()
    missing = set()
    for p in _sources():
        txt = p.read_text(encoding="utf-8")
        for m in re.finditer(r"\b(?:t|tr)\(\s*\"([a-z][a-z0-9_]*)\"", txt):
            if m.group(1) not in keys:
                missing.add(f"{p.relative_to(SRC)}: {m.group(1)}")
    assert not missing, f"مفاتيحُ لا مقابل لها — يُعرض اسمُ المفتاح للمستخدم: {sorted(missing)}"


def test_every_entry_has_real_english():
    bad = [k for k, (_, en) in _dictionary().items()
           if en.strip('"') == "" or AR.search(en)]
    assert not bad, f"مدخلاتٌ بلا إنجليزية حقيقية: {bad[:30]}"


def test_the_new_dictionary_is_merged():
    main = (SRC / "i18n.tsx").read_text(encoding="utf-8")
    assert 'import { screens } from "./i18n_screens"' in main
    assert "...screens," in main
    assert "export function tr(" in main


def test_local_dictionaries_carry_both_languages():
    for p in _sources():
        txt = p.read_text(encoding="utf-8")
        if "i18n: local-dictionary" not in txt:
            continue
        ar = re.search(r"\n  ar: \{(.*?)\n  \},", txt, re.S)
        en = re.search(r"\n  en: \{(.*?)\n  \},", txt, re.S)
        assert ar and en, p.name
        ka = set(re.findall(r"^\s+([a-z0-9_]+):", ar.group(1), re.M))
        ke = set(re.findall(r"^\s+([a-z0-9_]+):", en.group(1), re.M))
        assert ka and ka == ke, (p.name, sorted(ka ^ ke))
