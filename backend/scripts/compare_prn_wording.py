# -*- coding: utf-8 -*-
"""يقارن نصوص الـ 42 قالب طباعة (HRMS-PR-001..042) في seed.py مع النص التشغيلي المقترح
في V1.4 Engineer Spec، ويولّد تقرير Markdown يظهر:

- نسبة تشابه لكل قالب (SequenceMatcher ratio على النص المُطبَّع)
- Placeholders المطلوبة بالـ spec لكن الغائبة في الـ seed
- Placeholders الموجودة في الـ seed لكن غير مذكورة في الـ spec
- نص الـ spec ونص الـ seed لكل قالب للمقارنة اليدوية عند الحاجة

يُحفَظ التقرير في: docs/PRN_WORDING_DIFF.md

التشغيل:  python -m scripts.compare_prn_wording  [مسار PDF spec — اختياري]
افتراضيًا: يقرأ v14_spec.txt المُستخرَج مسبقًا من:
  C:/Users/CORE~1/AppData/Local/Temp/claude/D--11/c04d7d4d-1cf1-4541-9e1c-a8b6ad8fb635/scratchpad/v14_spec.txt
"""
from __future__ import annotations

import io
import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

# نسمح بالتشغيل من جذر المشروع مباشرة
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.seed import DEFAULT_TEMPLATES  # noqa: E402


SPEC_PATH_DEFAULT = (
    r"C:/Users/CORE~1/AppData/Local/Temp/claude/D--11/"
    r"c04d7d4d-1cf1-4541-9e1c-a8b6ad8fb635/scratchpad/v14_spec.txt"
)
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "PRN_WORDING_DIFF.md"


def _strip_html(s: str) -> str:
    """يحذف وسوم HTML وينظّم المسافات."""
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _normalize_ar(s: str) -> str:
    """تطبيع النص العربي للمقارنة الدلالية:
    - يوحّد أشكال الألف/الياء/التاء المربوطة
    - يحذف الحركات (fatha/kasra/damma/tanween/shadda/sukun)
    - يستبدل {{key}} أو }key{ بمكان موحّد {KEY}
    """
    s = s or ""
    # حذف الحركات
    s = re.sub(r"[ً-ْٰـ]", "", s)
    # توحيد الألف
    s = re.sub(r"[إأآٱ]", "ا", s)
    # توحيد الياء
    s = s.replace("ى", "ي")
    # توحيد التاء المربوطة → هاء (شائع في المقارنة)
    s = s.replace("ة", "ه")
    # توحيد صيغة الـ placeholder: {{name}} أو }name{ → {NAME}
    s = re.sub(r"\{\{\s*([A-Za-z_][\w]*)\s*\}\}", lambda m: "{" + m.group(1).upper() + "}", s)
    s = re.sub(r"\}\s*([A-Za-z_][\w]*)\s*\{", lambda m: "{" + m.group(1).upper() + "}", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_placeholders(s: str) -> set[str]:
    """يستخرج مفاتيح الـ placeholders من نصوص بأي صيغة معروفة."""
    out: set[str] = set()
    for m in re.finditer(r"\{\{\s*([A-Za-z_][\w]*)\s*\}\}", s):
        out.add(m.group(1).lower())
    for m in re.finditer(r"\}\s*([A-Za-z_][\w]*)\s*\{", s):
        out.add(m.group(1).lower())
    return out


def load_spec_prns(spec_text: str) -> dict[str, dict]:
    """يفصل نص الـ spec إلى أقسام لكل PRN-XXX ويستخرج (بأفضل جهد):
    - `operational_text`: أول فقرة من "النص التشغيلي المقترح"
    - `mandatory_fields`: قائمة الحقول من "الحقول الإلزامية"
    - `approvers`: من "الاعتمادات"
    """
    prns: dict[str, dict] = {}
    # PDF مستخرَج بترتيب RTL، فرمز القالب يظهر في نهاية سطر العنوان لا بدايته. نستخدم
    # كل ظهور لـ "PRN-XXX" متبوعًا بسطر جديد كنقطة تقسيم لبداية قسم القالب.
    positions = [(m.group(1), m.end()) for m in re.finditer(r"(PRN-\d{3})\s*\n", spec_text)]
    if not positions:
        # احتياطي: أي ظهور لرمز — قد يعطي مواقع مكرّرة لكن نأخذ أول تعريف لكل رمز
        positions = [(m.group(1), m.start()) for m in re.finditer(r"(PRN-\d{3})", spec_text)]
    # نبني نطاقات (start, end) لكل رمز بحيث يمتد جسم القسم حتى بداية القسم التالي
    seen: dict[str, tuple[int, int]] = {}
    for i, (code, start) in enumerate(positions):
        if code in seen:
            continue
        end = positions[i + 1][1] if i + 1 < len(positions) else len(spec_text)
        seen[code] = (start, end)
    for code, (start, end) in seen.items():
        body = spec_text[start:end]
        # نص تشغيلي مقترح
        op = re.search(r"النص التشغيلي المقترح[:\s]*(.*?)(?=الاعتمادات|ضابط القبول|Templates\s*&|$)",
                       body, re.DOTALL)
        # حقول إلزامية
        mand = re.search(r"الحقول الإلزامية[:\s]*(.*?)(?=النص التشغيلي|الاعتمادات|$)",
                         body, re.DOTALL)
        # اعتمادات
        appr = re.search(r"الاعتمادات[:\s]*(.*?)(?=ضابط القبول|$)", body, re.DOTALL)
        prns[code] = {
            "operational_text": _strip_html(op.group(1)) if op else "",
            "mandatory_fields": _strip_html(mand.group(1)) if mand else "",
            "approvers": _strip_html(appr.group(1)) if appr else "",
            "raw": body[:2000],
        }
    return prns


def load_seed_prns() -> dict[str, dict]:
    """يحوّل DEFAULT_TEMPLATES إلى dict بمفتاح رمز القالب (HRMS-PR-XXX → PRN-XXX)."""
    out: dict[str, dict] = {}
    for code, name, name_en, cat, body in DEFAULT_TEMPLATES:
        prn_code = code.replace("HRMS-PR-", "PRN-")
        out[prn_code] = {
            "name": name,
            "name_en": name_en or "",
            "category": cat,
            "body_html": body,
            "body_text": _strip_html(body),
        }
    return out


def compare_one(spec: dict, seed: dict) -> dict:
    """يعيد قياس التشابه بين قالب spec وقالب seed:
    - similarity: نسبة SequenceMatcher (0..1)
    - missing_placeholders: مفاتيح ذُكرت في spec لكن غير موجودة في seed
    - extra_placeholders: مفاتيح موجودة في seed لكن ليست في spec
    """
    spec_norm = _normalize_ar(spec.get("operational_text", ""))
    seed_norm = _normalize_ar(seed.get("body_text", ""))
    ratio = SequenceMatcher(None, spec_norm, seed_norm).ratio() if spec_norm and seed_norm else 0.0
    spec_ph = _extract_placeholders(spec.get("operational_text", ""))
    seed_ph = _extract_placeholders(seed.get("body_html", ""))
    return {
        "similarity": ratio,
        "spec_placeholders": sorted(spec_ph),
        "seed_placeholders": sorted(seed_ph),
        "missing_in_seed": sorted(spec_ph - seed_ph),
        "extra_in_seed": sorted(seed_ph - spec_ph),
    }


def build_report(spec_prns: dict, seed_prns: dict) -> str:
    codes = sorted(set(spec_prns) | set(seed_prns),
                   key=lambda c: int(c.split("-")[1]) if c.startswith("PRN-") else 0)
    lines: list[str] = []
    lines.append("# PRN Wording Diff Report — V1.4 spec vs seed.py")
    lines.append("")
    lines.append("| Code | Name (seed) | Similarity | Missing placeholders | Notes |")
    lines.append("| --- | --- | --- | --- | --- |")

    summary = {"identical": 0, "close": 0, "diverges": 0, "missing_in_seed": 0, "missing_in_spec": 0}
    per_code: list[tuple[str, str, dict, dict]] = []

    for code in codes:
        s = spec_prns.get(code)
        d = seed_prns.get(code)
        if not s and d:
            summary["missing_in_spec"] += 1
            lines.append(f"| {code} | {d['name']} | — | — | in seed only |")
            continue
        if s and not d:
            summary["missing_in_seed"] += 1
            lines.append(f"| {code} | — | — | — | in spec only |")
            continue
        cmp = compare_one(s, d)
        sim = cmp["similarity"]
        if sim >= 0.9:
            summary["identical"] += 1
            note = "≈identical"
        elif sim >= 0.5:
            summary["close"] += 1
            note = "close — minor rewording"
        else:
            summary["diverges"] += 1
            note = "**REVIEW** — significant divergence"
        miss = ", ".join(f"`{{{{{p}}}}}`" for p in cmp["missing_in_seed"]) or "—"
        lines.append(f"| {code} | {d['name']} | {sim:.2f} | {miss} | {note} |")
        per_code.append((code, note, s, d))

    lines.append("")
    lines.append("## Summary")
    lines.append(f"- ≈Identical (≥0.9): **{summary['identical']}**")
    lines.append(f"- Close (0.5–0.9): **{summary['close']}**")
    lines.append(f"- Diverges (<0.5): **{summary['diverges']}**")
    lines.append(f"- Missing in seed: **{summary['missing_in_seed']}**")
    lines.append(f"- Missing in spec extract: **{summary['missing_in_spec']}**")

    # تحليل ثاني: كم قالب seed لا يحوي placeholder واحد بصيغة {{key}}؟
    seed_no_placeholders = sum(
        1 for c in codes
        if c in seed_prns and not _extract_placeholders(seed_prns[c]["body_html"])
    )
    lines.append(f"- Seed templates with **zero** `{{{{placeholders}}}}`: **{seed_no_placeholders} / {len(seed_prns)}**")
    lines.append("")
    lines.append("## Root-cause finding")
    lines.append("")
    lines.append("الفرق الأكبر بين seed.py وV1.4 spec ليس صياغة النص — بل أن **قوالب seed تستخدم "
                 "تسميات عربية حرفية** مثل `اسم الشركة` و `اسم الموظف` في مواضع كان يجب أن تحتوي على "
                 "placeholders `{{company_name}}` و `{{employee_name}}`. النتيجة: عند الطباعة لا "
                 "يحدث أي استبدال بالبيانات الفعلية للموظف/الشركة، ويطبع النص كما هو لأي موظف. "
                 "الـ spec يذكر هذا صراحة في P0-PDF-01 (Templates & Wording, ص 26): "
                 "`placeholders يعتمد renderer` — استخدم placeholders، لا نصًا ثابتًا.")
    lines.append("")
    lines.append("**الحل المقترح:** استبدل التسميات الحرفية في قوالب seed.py بالـ placeholders "
                 "الصحيحة (`{{employee_name}}`, `{{company_name}}`, `{{civil_id}}`, `{{job_title}}`, "
                 "`{{hire_date}}`, `{{basic_salary}}`, `{{allowances_total}}`, `{{gross_salary}}`, "
                 "إلخ). محرك templates.py يقوم بالفعل باستبدال `{{key}}` عند طباعة القالب (راجع "
                 "`_TOKEN_RE` و`_build_context` في `app/routers/templates.py`)، فالتعديل عمل نصي "
                 "بحت على seed.py يليه إعادة seed.")
    lines.append("")
    lines.append("_ملاحظة تقنية: النص المستخرَج من PDF spec يظهر بترتيب RTL معكوس (`}key{` بدل "
                 "`{{key}}`) — التطبيع يعالجه قبل المقارنة، لكن للفحص البصري لأي صف REVIEW يُنصح "
                 "بمراجعة الـ spec الأصلي مباشرة._")
    lines.append("")

    # تفاصيل لكل بند يحتاج مراجعة
    lines.append("## Detailed diffs (rows marked REVIEW)")
    lines.append("")
    for code, note, s, d in per_code:
        if "REVIEW" not in note:
            continue
        lines.append(f"### {code} — {d['name']}")
        lines.append("")
        lines.append("**Spec operational text (extracted):**")
        lines.append("")
        lines.append("```")
        lines.append(s["operational_text"][:1500])
        lines.append("```")
        lines.append("")
        lines.append("**Current seed body (stripped HTML):**")
        lines.append("")
        lines.append("```")
        lines.append(d["body_text"][:1500])
        lines.append("```")
        lines.append("")
        cmp = compare_one(s, d)
        if cmp["missing_in_seed"]:
            lines.append(f"**Placeholders missing in seed:** {', '.join(cmp['missing_in_seed'])}")
        if cmp["extra_in_seed"]:
            lines.append(f"**Placeholders in seed not mentioned by spec:** {', '.join(cmp['extra_in_seed'])}")
        lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    spec_path = sys.argv[1] if len(sys.argv) > 1 else SPEC_PATH_DEFAULT
    if not os.path.exists(spec_path):
        print(f"ERROR: spec text not found: {spec_path}")
        return 2
    with io.open(spec_path, "r", encoding="utf-8", errors="replace") as f:
        spec_text = f.read()

    spec_prns = load_spec_prns(spec_text)
    seed_prns = load_seed_prns()
    report = build_report(spec_prns, seed_prns)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with io.open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"OK — {len(seed_prns)} seed templates × {len(spec_prns)} spec templates")
    print(f"Report written to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
