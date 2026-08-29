#!/usr/bin/env python3
"""
HRMS V4 Tracker — 21 بندا عبر 5 فئات.

  python3 .claude/hrms/scripts/v4.py --init
  python3 .claude/hrms/scripts/v4.py
  python3 .claude/hrms/scripts/v4.py --cat tasks
  python3 .claude/hrms/scripts/v4.py --sev blocker
  python3 .claude/hrms/scripts/v4.py --open
  python3 .claude/hrms/scripts/v4.py --next
  python3 .claude/hrms/scripts/v4.py --set TSK-01 done --note "commit abc / spec/tasks_spec.rb"

الحالات: open · in_progress · done · blocked
يخرج بكود 1 لو بقي أي blocker مفتوح.
"""
import json, os, sys, argparse, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(BASE, "v4-tasks.json")
ST = os.path.join(BASE, "v4-status.json")
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--init", action="store_true")
    p.add_argument("--cat"); p.add_argument("--sev")
    p.add_argument("--open", action="store_true"); p.add_argument("--next", action="store_true")
    p.add_argument("--set", nargs=2, metavar=("ID", "STATUS")); p.add_argument("--note", default="")
    a = p.parse_args()
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
        print(f"{MARK[v]} {iid} → {v}  {a.note}")
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
        print(f"{i['text']}\n\nالسكيل: {i['skill']}\n(متبقٍ {len(cand)})")
        return 0

    cur, counts, blk = None, {}, []
    order = list(r["categories"])
    for i in sorted(items, key=lambda i: (order.index(i["cat"]), W.get(i["sev"], 9))):
        v = s.get(i["id"], {}).get("status", "open")
        counts[v] = counts.get(v, 0) + 1
        if i["sev"] == "blocker" and v not in DONE:
            blk.append(i)
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
    if blk:
        print(f"\n!! {len(blk)} blocker مفتوح:")
        for i in blk:
            print(f"   {i['id']}  {i['text']}")
        return 1
    print("\nكل الـ blockers مغلقة.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
