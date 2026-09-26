# -*- coding: utf-8 -*-
"""M23 #1 — عربي/إنجليزي متسق: كل مفتاحٍ تستعمله الواجهة معرَّفٌ بلغتين، ولا نصَّ فارغًا ولا مخلوطًا.

يمسح ملفّات الترجمة والواجهة نفسها: مفتاحٌ يُستعمل بلا تعريفٍ يعرض اسمَه الخام للمستخدم، ونصٌّ إنجليزيٌّ فيه عربيّ
(أو العكس) يُريه لغتين في شاشةٍ واحدة.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend" / "src"
B = chr(92)
ARABIC = re.compile("[" + B + "u0600-" + B + "u06FF]")
ENTRY = re.compile("([A-Za-z0-9_]+):" + B + "s*" + B + "{" + B + "s*ar:" + B + "s*\"((?:[^\"" + B + B + "]|" + B + B + ".)*)\""
                   + B + "s*," + B + "s*en:" + B + "s*\"((?:[^\"" + B + B + "]|" + B + B + ".)*)\"")
USE = re.compile("(?:" + B + "bt|" + B + "btr)" + B + "(" + B + "s*\"([A-Za-z0-9_]+)\"")


def _entries():
    out = {}
    for f in ("i18n.tsx", "i18n_screens.ts"):
        for k, ar, en in ENTRY.findall((ROOT / f).read_text(encoding="utf-8")):
            out[k] = (ar, en)
    return out


def test_every_used_key_is_defined_in_both_languages():
    defs = _entries()
    assert len(defs) > 1000, "الاستخراج معطوب"
    used = set()
    for p in ROOT.rglob("*.tsx"):
        if not p.name.startswith("i18n"):
            used |= set(USE.findall(p.read_text(encoding="utf-8")))
    missing = sorted(k for k in used if k not in defs)
    assert not missing, f"مفاتيحُ تُستعمل بلا تعريف: {missing[:20]}"


def test_no_entry_is_empty_or_mixes_the_two_languages():
    bad = []
    for k, (ar, en) in _entries().items():
        if not ar.strip() or not en.strip():
            bad.append((k, "فارغ"))
        elif ARABIC.search(en):
            bad.append((k, "الإنجليزي فيه عربي"))
        elif not ARABIC.search(ar) and re.search("[A-Za-z]{3,}", ar) and ar.strip() != en.strip():
            bad.append((k, "العربي بلا عربي"))
    assert not bad, f"إدخالاتٌ معيبة: {bad[:15]}"
