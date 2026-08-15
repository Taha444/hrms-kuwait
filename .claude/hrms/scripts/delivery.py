#!/usr/bin/env python3
"""
HRMS Delivery Readiness
تتبّع 66 متطلب تسليم لشركة.

  python3 .claude/hrms/scripts/delivery.py --init
  python3 .claude/hrms/scripts/delivery.py                      # الحالة الكاملة
  python3 .claude/hrms/scripts/delivery.py --cat backup         # فئة واحدة
  python3 .claude/hrms/scripts/delivery.py --pending            # الناقص فقط
  python3 .claude/hrms/scripts/delivery.py --critical           # الحرج فقط
  python3 .claude/hrms/scripts/delivery.py --set DLV-17 done --note "استرجاع مُختبَر 2026-08-14"
  python3 .claude/hrms/scripts/delivery.py --report             # تقرير الجاهزية

الحالات: pending · in_progress · done · na · client (مسؤولية العميل)
يخرج بكود 1 لو بقي أي بند critical غير مكتمل.
"""
import json, os, sys, argparse, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(BASE, "delivery.json")
ST = os.path.join(BASE, "delivery-status.json")

DONE = {"done", "na"}
VALID = {"pending", "in_progress", "done", "na", "client"}
MARK = {"pending": "[   ]", "in_progress": "[ > ]", "done": "[ X ]",
        "na": "[N/A]", "client": "[CLI]"}
W = {"critical": 0, "high": 1, "medium": 2}


def reg():
    return json.load(open(REG, encoding="utf-8"))


def st():
    return json.load(open(ST, encoding="utf-8")) if os.path.exists(ST) else {}


def save(s):
    json.dump(s, open(ST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--init", action="store_true")
    p.add_argument("--cat"); p.add_argument("--pending", action="store_true")
    p.add_argument("--critical", action="store_true"); p.add_argument("--report", action="store_true")
    p.add_argument("--set", nargs=2, metavar=("ID", "STATUS")); p.add_argument("--note", default="")
    a = p.parse_args()
    r = reg()

    if a.init:
        save({i["id"]: {"status": "pending", "note": "", "updated": ""} for i in r["items"]})
        print(f"تم إنشاء {ST} بـ {len(r['items'])} متطلبا")
        return 0

    s = st()

    if a.set:
        iid, v = a.set[0].upper(), a.set[1].lower()
        if v not in VALID:
            print(f"حالة غير صالحة. المسموح: {', '.join(sorted(VALID))}"); return 2
        item = next((i for i in r["items"] if i["id"] == iid), None)
        if not item:
            print(f"غير موجود: {iid}"); return 2
        if v in ("done", "na") and item["weight"] == "critical" and not a.note:
            print("!! البنود الحرجة تحتاج --note بالدليل"); return 2
        s[iid] = {"status": v, "note": a.note, "updated": datetime.date.today().isoformat()}
        save(s)
        print(f"{MARK[v]} {iid} → {v}" + (f"  {a.note}" if a.note else ""))
        return 0

    items = r["items"]
    if a.cat:
        items = [i for i in items if i["cat"] == a.cat.lower()]
    if a.critical:
        items = [i for i in items if i["weight"] == "critical"]

    cur, counts, open_crit = None, {}, []
    for i in sorted(items, key=lambda i: (list(r["categories"]).index(i["cat"]), W.get(i["weight"], 9))):
        v = s.get(i["id"], {}).get("status", "pending")
        counts[v] = counts.get(v, 0) + 1
        if i["weight"] == "critical" and v not in DONE:
            open_crit.append(i)
        if a.pending and v in DONE:
            continue
        if i["cat"] != cur:
            cur = i["cat"]
            print(f"\n=== {r['categories'][cur]} ===")
        w = "*" if i["weight"] == "critical" else " "
        print(f"{MARK[v]}{w} {i['id']}  {i['text']}")
        n = s.get(i["id"], {}).get("note", "")
        if n:
            print(f"        {n}")

    tot = len(items)
    done = sum(counts.get(k, 0) for k in DONE)
    print(f"\n--- {done}/{tot} ({round(100*done/tot) if tot else 0}%) | " +
          " ".join(f"{k}={v}" for k, v in sorted(counts.items())) + " ---")
    print("* = حرج، لا تسليم بدونه")

    if a.report:
        client = [i for i in r["items"] if s.get(i["id"], {}).get("status") == "client"]
        if client:
            print("\n=== بنود على مسؤولية العميل ===")
            for i in client:
                print(f"  {i['id']}  {i['text']}")
                if s[i["id"]].get("note"):
                    print(f"        {s[i['id']]['note']}")

    if open_crit:
        print(f"\n!! {len(open_crit)} بند حرج غير مكتمل — النظام غير جاهز للتسليم:")
        for i in open_crit:
            print(f"   {i['id']}  {i['text']}")
        return 1
    print("\nكل البنود الحرجة مكتملة.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
