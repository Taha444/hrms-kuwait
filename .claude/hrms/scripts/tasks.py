#!/usr/bin/env python3
"""
HRMS V3 Task Tracker — 29 بندا عبر 6 فئات.

  python3 .claude/hrms/scripts/tasks.py --init
  python3 .claude/hrms/scripts/tasks.py                  # الكل
  python3 .claude/hrms/scripts/tasks.py --cat contract
  python3 .claude/hrms/scripts/tasks.py --sev blocker
  python3 .claude/hrms/scripts/tasks.py --open
  python3 .claude/hrms/scripts/tasks.py --next
  python3 .claude/hrms/scripts/tasks.py --set GC-04 done --note "commit abc / render check"
  python3 .claude/hrms/scripts/tasks.py --verify-template  # بصمة القالب

الحالات: open · in_progress · done · blocked
يخرج بكود 1 لو بقي أي blocker مفتوح.
"""
import json, os, sys, argparse, datetime, hashlib

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(BASE, "tasks.json")
ST = os.path.join(BASE, "tasks-status.json")
TPL = os.path.join(os.path.dirname(BASE), "skills", "hrms-gov-contract-template",
                   "assets", "GOV-CONTRACT-RENEWAL.docx")
TPL_SHA16 = "2a9cf6e4c2098e03"

DONE = {"done"}
VALID = {"open", "in_progress", "done", "blocked"}
MARK = {"open": "[   ]", "in_progress": "[ > ]", "done": "[ X ]", "blocked": "[ ! ]"}
W = {"blocker": 0, "high": 1, "medium": 2, "low": 3}


def reg():
    return json.load(open(REG, encoding="utf-8"))


def st():
    return json.load(open(ST, encoding="utf-8")) if os.path.exists(ST) else {}


def save(s):
    json.dump(s, open(ST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def verify_template():
    if not os.path.exists(TPL):
        print(f"!! القالب غير موجود: {TPL}")
        return 1
    h = hashlib.sha256(open(TPL, "rb").read()).hexdigest()
    print(f"المسار:   {TPL}")
    print(f"sha256:   {h}")
    if h.startswith(TPL_SHA16):
        print("النتيجة:  مطابق للأصل — لم يُعدَّل")
        return 0
    print(f"النتيجة:  !! غير مطابق — المتوقع يبدأ بـ {TPL_SHA16}")
    print("          شخص ما عدّل النموذج الرسمي. أوقف وأبلغ.")
    return 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--init", action="store_true")
    p.add_argument("--cat"); p.add_argument("--sev")
    p.add_argument("--open", action="store_true"); p.add_argument("--next", action="store_true")
    p.add_argument("--verify-template", action="store_true")
    p.add_argument("--set", nargs=2, metavar=("ID", "STATUS")); p.add_argument("--note", default="")
    a = p.parse_args()

    if a.verify_template:
        return verify_template()

    r = reg()
    if a.init:
        save({i["id"]: {"status": "open", "note": "", "updated": ""} for i in r["items"]})
        print(f"تم إنشاء {ST} بـ {len(r['items'])} بندا")
        return 0

    s = st()
    if a.set:
        iid, v = a.set[0].upper(), a.set[1].lower()
        if v not in VALID:
            print(f"حالة غير صالحة. المسموح: {', '.join(sorted(VALID))}"); return 2
        item = next((i for i in r["items"] if i["id"] == iid), None)
        if not item:
            print(f"غير موجود: {iid}"); return 2
        if v == "done" and not a.note:
            print("!! الإغلاق يحتاج --note بالدليل (commit أو اختبار أو مخرَج)"); return 2
        s[iid] = {"status": v, "note": a.note, "updated": datetime.date.today().isoformat()}
        save(s)
        print(f"{MARK[v]} {iid} → {v}" + (f"  {a.note}" if a.note else ""))
        return 0

    items = r["items"]
    if a.cat:
        items = [i for i in items if i["cat"] == a.cat.lower()]
    if a.sev:
        items = [i for i in items if i["sev"] == a.sev.lower()]

    if a.next:
        cand = [i for i in items if s.get(i["id"], {}).get("status", "open") not in DONE]
        cand.sort(key=lambda i: W.get(i["sev"], 9))
        if not cand:
            print("لا يوجد بند مفتوح في هذا النطاق."); return 0
        i = cand[0]
        print(f"\n{i['id']}  [{i['sev'].upper()}]  ({r['categories'][i['cat']]})")
        print(f"{i['text']}")
        print(f"\nالسكيل: {i['skill']}")
        print(f"(متبقٍ {len(cand)})")
        return 0

    cur, counts, blockers = None, {}, []
    order = list(r["categories"])
    for i in sorted(items, key=lambda i: (order.index(i["cat"]), W.get(i["sev"], 9))):
        v = s.get(i["id"], {}).get("status", "open")
        counts[v] = counts.get(v, 0) + 1
        if i["sev"] == "blocker" and v not in DONE:
            blockers.append(i)
        if a.open and v in DONE:
            continue
        if i["cat"] != cur:
            cur = i["cat"]
            print(f"\n=== {r['categories'][cur]} ===")
        b = "*" if i["sev"] == "blocker" else " "
        print(f"{MARK[v]}{b} {i['id']:<8} {i['text']}")
        n = s.get(i["id"], {}).get("note", "")
        if n:
            print(f"          {n}")

    tot = len(items)
    done = sum(counts.get(k, 0) for k in DONE)
    print(f"\n--- {done}/{tot} ({round(100*done/tot) if tot else 0}%) | " +
          " ".join(f"{k}={v}" for k, v in sorted(counts.items())) + " ---")
    print("* = blocker")
    if blockers:
        print(f"\n!! {len(blockers)} blocker مفتوح:")
        for i in blockers:
            print(f"   {i['id']}  {i['text']}")
        return 1
    print("\nكل الـ blockers مغلقة.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
