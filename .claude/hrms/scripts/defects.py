#!/usr/bin/env python3
"""
HRMS Remediation Tracker
سجل العيوب الموحّد + تتبّع حالة كل بند + تقرير التسليم.

الاستخدام:
  python3 .claude/hrms/scripts/defects.py --init
  python3 .claude/hrms/scripts/defects.py                      # التقرير الكامل
  python3 .claude/hrms/scripts/defects.py --cluster WF         # عنقود واحد
  python3 .claude/hrms/scripts/defects.py --sev blocker        # حسب الخطورة
  python3 .claude/hrms/scripts/defects.py --open               # غير المغلق فقط
  python3 .claude/hrms/scripts/defects.py --show WF-01         # تفاصيل بند
  python3 .claude/hrms/scripts/defects.py --conflicts          # التناقضات بين المصادر
  python3 .claude/hrms/scripts/defects.py --next               # البند التالي بالأولوية
  python3 .claude/hrms/scripts/defects.py --set WF-01 fixed --note "commit abc / spec/x_spec.rb"
  python3 .claude/hrms/scripts/defects.py --report             # تقرير Fixed/Not Completed للعميل

الحالات:
  open        لم يُبدأ
  verifying   قيد التحقق من وجوده فعلا في البناء الحالي
  verified    تم التحقق أنه سليم بالفعل ولا يحتاج تعديلا
  in_progress قيد الإصلاح
  fixed       أُصلح ومُثبت بدليل
  blocked     يحتاج قرارا خارجيا
  wontfix     خارج النطاق بقرار موثق

يخرج بكود 1 لو بقي أي blocker غير مغلق.
"""
import json, sys, os, argparse, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(BASE, "defects.json")
ST = os.path.join(BASE, "remediation-status.json")

DONE = {"fixed", "verified", "wontfix"}
VALID = {"open", "verifying", "verified", "in_progress", "fixed", "blocked", "wontfix"}
MARK = {"open": "[    ]", "verifying": "[ ?? ]", "verified": "[ OK ]",
        "in_progress": "[ >> ]", "fixed": "[DONE]", "blocked": "[BLKD]", "wontfix": "[SKIP]"}
SEV_ORDER = {"blocker": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def reg():
    with open(REG, encoding="utf-8") as f:
        return json.load(f)


def st():
    return json.load(open(ST, encoding="utf-8")) if os.path.exists(ST) else {}


def save(s):
    json.dump(s, open(ST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def find(r, did):
    return next((d for d in r["defects"] if d["id"] == did.upper()), None)


def show(d, r):
    print(f"\n{'='*60}\n{d['id']}  [{d['sev'].upper()}]  {d['cluster']}\n{'='*60}")
    print(f"العنوان: {d['title']}")
    print(f"المصادر: {', '.join(d['src'])}")
    if d.get("detail"):
        print(f"\nالتفصيل:\n  {d['detail']}")
    if d.get("verify"):
        print(f"\nكيف تتحقق:\n  {d['verify']}")
    print("\nالمطلوب:")
    for part in d["fix"].split(" · "):
        print(f"  - {part}")
    if d.get("conflict"):
        c = next((x for x in r["conflicts"] if x["id"] == d["conflict"]), None)
        if c:
            print(f"\n!! تناقض بين المصادر ({c['id']}):\n  {c['note']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--init", action="store_true")
    p.add_argument("--cluster")
    p.add_argument("--sev")
    p.add_argument("--open", action="store_true")
    p.add_argument("--show")
    p.add_argument("--conflicts", action="store_true")
    p.add_argument("--next", action="store_true")
    p.add_argument("--report", action="store_true")
    p.add_argument("--set", nargs=2, metavar=("ID", "STATUS"))
    p.add_argument("--note", default="")
    a = p.parse_args()
    r = reg()

    if a.init:
        save({d["id"]: {"status": "open", "note": "", "updated": ""} for d in r["defects"]})
        print(f"تم إنشاء {ST} بـ {len(r['defects'])} بندا")
        return 0

    s = st()

    if a.show:
        d = find(r, a.show)
        if not d:
            print(f"غير موجود: {a.show}"); return 2
        show(d, r)
        cur = s.get(d["id"], {})
        print(f"\nالحالة: {cur.get('status','open')}  {cur.get('note','')}")
        return 0

    if a.conflicts:
        print("=== تناقضات بين المصادر — تحقق قبل أي تعديل ===")
        for c in r["conflicts"]:
            print(f"\n{c['id']}  ({', '.join(c['items'])})\n  {c['note']}")
        return 0

    if a.set:
        did, stt = a.set[0].upper(), a.set[1].lower()
        if stt not in VALID:
            print(f"حالة غير صالحة. المسموح: {', '.join(sorted(VALID))}"); return 2
        if not find(r, did):
            print(f"معرّف غير موجود: {did}"); return 2
        if stt == "fixed" and not a.note:
            print("!! الإغلاق بـ fixed يحتاج --note بالدليل (commit أو ملف اختبار أو مخرَج فعلي)")
            return 2
        s[did] = {"status": stt, "note": a.note, "updated": datetime.date.today().isoformat()}
        save(s)
        print(f"{MARK[stt]} {did} → {stt}" + (f"  ({a.note})" if a.note else ""))
        return 0

    ds = r["defects"]
    if a.cluster:
        ds = [d for d in ds if d["cluster"] == a.cluster.upper()]
    if a.sev:
        ds = [d for d in ds if d["sev"] == a.sev.lower()]

    if a.next:
        cand = [d for d in ds if s.get(d["id"], {}).get("status", "open") not in DONE]
        cand.sort(key=lambda d: SEV_ORDER.get(d["sev"], 9))
        if not cand:
            print("لا يوجد بند مفتوح في هذا النطاق."); return 0
        show(cand[0], r)
        print(f"\n(متبقٍ {len(cand)} بندا مفتوحا في هذا النطاق)")
        return 0

    if a.report:
        print("=== تقرير التسليم — Fixed / Not Completed ===\n")
        for d in sorted(r["defects"], key=lambda d: (SEV_ORDER.get(d["sev"], 9), d["id"])):
            cur = s.get(d["id"], {})
            stt = cur.get("status", "open")
            label = "Fixed" if stt in ("fixed", "verified") else ("Skipped" if stt == "wontfix" else "Not Completed")
            print(f"{d['id']} | {d['sev']} | {label} | {d['title']}")
            if cur.get("note"):
                print(f"          دليل: {cur['note']}")
        print("\nأرفق مع التقرير: Full Commit SHA · وقت الـ Deployment · Migration Version")
        return 0

    counts = {}
    open_blockers = 0
    cur_cluster = None
    for d in sorted(ds, key=lambda d: (d["cluster"], SEV_ORDER.get(d["sev"], 9))):
        stt = s.get(d["id"], {}).get("status", "open")
        counts[stt] = counts.get(stt, 0) + 1
        if d["sev"] == "blocker" and stt not in DONE:
            open_blockers += 1
        if a.open and stt in DONE:
            continue
        if d["cluster"] != cur_cluster:
            cur_cluster = d["cluster"]
            print(f"\n=== {cur_cluster} — {r['clusters'].get(cur_cluster,'')} ===")
        flag = " !!" if d.get("conflict") else ""
        print(f"{MARK[stt]} {d['id']:<10} [{d['sev']:<7}] {d['title']}{flag}")
        note = s.get(d["id"], {}).get("note", "")
        if note:
            print(f"           {note}")

    total = len(ds)
    done = sum(counts.get(k, 0) for k in DONE)
    print(f"\n--- {done}/{total} مغلق ({round(100*done/total) if total else 0}%) | " +
          " ".join(f"{k}={v}" for k, v in sorted(counts.items())) + " ---")
    if open_blockers:
        print(f"!! {open_blockers} blocker ما زال مفتوحا — الحالة NO-GO")
    return 1 if open_blockers else 0


if __name__ == "__main__":
    sys.exit(main())
