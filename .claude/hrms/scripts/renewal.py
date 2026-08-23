#!/usr/bin/env python3
"""
HRMS Residency Renewal Tracker
آلة حالات معاملة التجديد + 24 معيار قبول + تتبّع التنفيذ.

  python3 .claude/hrms/scripts/renewal.py --init
  python3 .claude/hrms/scripts/renewal.py --states           # آلة الحالات
  python3 .claude/hrms/scripts/renewal.py --show RENEWAL_STARTED
  python3 .claude/hrms/scripts/renewal.py --flow             # المسار مختصرا
  python3 .claude/hrms/scripts/renewal.py --accept           # معايير القبول
  python3 .claude/hrms/scripts/renewal.py --pending          # المتبقي
  python3 .claude/hrms/scripts/renewal.py --next             # البند التالي
  python3 .claude/hrms/scripts/renewal.py --set RNW-01 done --note "commit abc / test x"
  python3 .claude/hrms/scripts/renewal.py --report

الحالات: open · in_progress · done · blocked
يخرج بكود 1 لو بقي أي blocker مفتوح.
"""
import json, os, sys, argparse, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(BASE, "renewal", "workflow.json")
ST = os.path.join(BASE, "renewal", "status.json")

DONE = {"done"}
VALID = {"open", "in_progress", "done", "blocked"}
MARK = {"open": "[   ]", "in_progress": "[ > ]", "done": "[ X ]", "blocked": "[ ! ]"}
SEV = {"blocker": 0, "high": 1, "medium": 2}


def wf():
    return json.load(open(WF, encoding="utf-8"))


def st():
    return json.load(open(ST, encoding="utf-8")) if os.path.exists(ST) else {}


def save(s):
    json.dump(s, open(ST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--init", action="store_true")
    p.add_argument("--states", action="store_true"); p.add_argument("--flow", action="store_true")
    p.add_argument("--show"); p.add_argument("--accept", action="store_true")
    p.add_argument("--pending", action="store_true"); p.add_argument("--next", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--set", nargs=2, metavar=("ID", "STATUS")); p.add_argument("--note", default="")
    a = p.parse_args()
    w = wf()

    if a.init:
        save({c["id"]: {"status": "open", "note": "", "updated": ""} for c in w["acceptance"]})
        print(f"تم إنشاء {ST} بـ {len(w['acceptance'])} معيارا")
        return 0

    if a.flow:
        print(f"=== {w['name']} ===\n{w['principle']}\n")
        for s in w["states"]:
            if s.get("exception"):
                continue
            tag = "" if s.get("is_case") else "   (تنبيه، ليس معاملة)"
            print(f"  {s['code']:<28} [{s['actor']}]{tag}")
        print("\nاستثنائية: " + " · ".join(s["code"] for s in w["states"] if s.get("exception")))
        print("\nالنسخ الثلاث للعقد:")
        for k, v in w["artifacts"].items():
            if k.startswith("GOV_CONTRACT"):
                print(f"  v{v['v']}  {k:<32} {v['desc']}")
        return 0

    if a.states:
        for s in w["states"]:
            flag = " (استثنائية)" if s.get("exception") else ""
            term = " [نهائية]" if s.get("terminal") else ""
            print(f"\n{s['code']}{flag}{term}  — {s['actor']}")
            print(f"  {s['desc']}")
            if s.get("next"):
                print(f"  التالي: {', '.join(s['next'])}")
        return 0

    if a.show:
        s = next((x for x in w["states"] if x["code"] == a.show.upper()), None)
        if not s:
            print(f"حالة غير موجودة: {a.show}")
            print("المتاح: " + ", ".join(x["code"] for x in w["states"]))
            return 2
        print(f"\n{'='*58}\n{s['code']}   [{s['actor']}]\n{'='*58}")
        print(f"{s['desc']}\n")
        print(f"ملف معاملة؟ {'نعم' if s.get('is_case') else 'لا — تنبيه محسوب'}")
        if s.get("next"):
            print(f"الانتقالات: {', '.join(s['next'])}")
        print("\nشروط الخروج:")
        for e in s["exit"].split(" · "):
            print(f"  - {e}")
        return 0

    s = st()

    if a.set:
        cid, v = a.set[0].upper(), a.set[1].lower()
        if v not in VALID:
            print(f"حالة غير صالحة. المسموح: {', '.join(sorted(VALID))}"); return 2
        c = next((x for x in w["acceptance"] if x["id"] == cid), None)
        if not c:
            print(f"معيار غير موجود: {cid}"); return 2
        if v == "done" and not a.note:
            print("!! الإغلاق بـ done يحتاج --note بالدليل (commit أو اختبار أو مخرَج)"); return 2
        s[cid] = {"status": v, "note": a.note, "updated": datetime.date.today().isoformat()}
        save(s)
        print(f"{MARK[v]} {cid} → {v}" + (f"  {a.note}" if a.note else ""))
        return 0

    items = sorted(w["acceptance"], key=lambda c: (SEV.get(c["sev"], 9), c["id"]))

    if a.next:
        cand = [c for c in items if s.get(c["id"], {}).get("status", "open") not in DONE]
        if not cand:
            print("كل المعايير مغلقة."); return 0
        c = cand[0]
        print(f"\n{c['id']}  [{c['sev'].upper()}]\n{c['text']}\n")
        print(f"(متبقٍ {len(cand)} معيارا)")
        return 0

    counts, open_blockers = {}, []
    for c in items:
        v = s.get(c["id"], {}).get("status", "open")
        counts[v] = counts.get(v, 0) + 1
        if c["sev"] == "blocker" and v not in DONE:
            open_blockers.append(c)
        if a.pending and v in DONE:
            continue
        if a.accept or a.pending or a.report or not (a.accept or a.pending):
            b = "*" if c["sev"] == "blocker" else " "
            print(f"{MARK[v]}{b} {c['id']}  {c['text']}")
            n = s.get(c["id"], {}).get("note", "")
            if n:
                print(f"        {n}")

    tot = len(items)
    done = sum(counts.get(k, 0) for k in DONE)
    print(f"\n--- {done}/{tot} ({round(100*done/tot) if tot else 0}%) | " +
          " ".join(f"{k}={v}" for k, v in sorted(counts.items())) + " ---")
    print("* = blocker")
    if open_blockers:
        print(f"\n!! {len(open_blockers)} blocker مفتوح — المسار غير جاهز:")
        for c in open_blockers:
            print(f"   {c['id']}  {c['text']}")
        return 1
    print("\nكل الـ blockers مغلقة.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
