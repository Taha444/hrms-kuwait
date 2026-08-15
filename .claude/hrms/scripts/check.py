#!/usr/bin/env python3
"""
HRMS Compliance Checker
يقرأ compliance.json (السجل المرجعي) + status.json (الحالة الفعلية)
ويطبع تقريرا بالبنود المنفذة والناقصة.

الاستخدام:
  python3 .claude/hrms/scripts/check.py                 # كل البوابات
  python3 .claude/hrms/scripts/check.py --gate engine   # بوابة واحدة
  python3 .claude/hrms/scripts/check.py --pending       # الناقص فقط
  python3 .claude/hrms/scripts/check.py --set RW-08 pass --note "tested in tasks_spec.rb"
  python3 .claude/hrms/scripts/check.py --init          # إنشاء status.json فارغ

يخرج بكود 1 إذا وُجد أي بند FAIL في البوابة المطلوبة.
"""
import json, sys, os, argparse, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(BASE, "compliance.json")
STATUS = os.path.join(BASE, "status.json")

VALID = {"pass", "fail", "pending", "na", "blocked"}
MARK = {"pass": "[PASS]", "fail": "[FAIL]", "pending": "[ .. ]",
        "na": "[ NA ]", "blocked": "[BLOCK]"}


def load_registry():
    with open(REG, encoding="utf-8") as f:
        return json.load(f)


def load_status():
    if not os.path.exists(STATUS):
        return {}
    with open(STATUS, encoding="utf-8") as f:
        return json.load(f)


def save_status(s):
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


def init(reg):
    s = {c["id"]: {"status": "pending", "note": "", "updated": ""} for c in reg["criteria"]}
    save_status(s)
    print(f"تم إنشاء {STATUS} بـ {len(s)} بندا بحالة pending")


def report(reg, status, gate=None, pending_only=False):
    crits = reg["criteria"]
    if gate:
        crits = [c for c in crits if c["gate"] == gate]
    counts = {k: 0 for k in VALID}
    failed = 0
    current_gate = None
    for c in crits:
        st = status.get(c["id"], {})
        s = st.get("status", "pending")
        counts[s] = counts.get(s, 0) + 1
        if s == "fail":
            failed += 1
        if pending_only and s in ("pass", "na"):
            continue
        if c["gate"] != current_gate:
            current_gate = c["gate"]
            print(f"\n=== GATE: {current_gate} ===")
        note = st.get("note", "")
        exp = c.get("expected", c.get("evidence", ""))
        print(f"{MARK.get(s,'[ ?? ]')} {c['id']}  ({c['spec']})  {c['text']}")
        print(f"        المتوقع: {exp}")
        if note:
            print(f"        ملاحظة: {note}")
    total = len(crits)
    done = counts["pass"] + counts["na"]
    pct = round(100 * done / total) if total else 0
    print(f"\n--- الإجمالي: {done}/{total} ({pct}%) | "
          f"pass={counts['pass']} fail={counts['fail']} "
          f"pending={counts['pending']} blocked={counts['blocked']} na={counts['na']} ---")
    return 1 if failed else 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--gate")
    p.add_argument("--pending", action="store_true")
    p.add_argument("--init", action="store_true")
    p.add_argument("--set", nargs=2, metavar=("ID", "STATUS"))
    p.add_argument("--note", default="")
    a = p.parse_args()

    reg = load_registry()
    if a.init:
        init(reg)
        return 0

    status = load_status()
    if a.set:
        cid, st = a.set[0].upper(), a.set[1].lower()
        if st not in VALID:
            print(f"حالة غير صالحة: {st}. المسموح: {', '.join(sorted(VALID))}")
            return 2
        if not any(c["id"] == cid for c in reg["criteria"]):
            print(f"معرّف غير موجود في السجل: {cid}")
            return 2
        status[cid] = {"status": st, "note": a.note,
                       "updated": datetime.date.today().isoformat()}
        save_status(status)
        print(f"{MARK[st]} {cid} → {st}" + (f"  ({a.note})" if a.note else ""))
        return 0

    if a.gate and a.gate not in reg["gates"]:
        print(f"بوابة غير معروفة. المتاح: {', '.join(reg['gates'])}")
        return 2
    return report(reg, status, a.gate, a.pending)


if __name__ == "__main__":
    sys.exit(main())
