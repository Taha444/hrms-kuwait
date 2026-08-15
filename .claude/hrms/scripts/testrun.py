#!/usr/bin/env python3
"""
HRMS Test Run Tracker
يدير جولات الاختبار الحي ويربط كل رحلة بنتيجتها ودليلها.

  python3 .claude/hrms/scripts/testrun.py --new "جولة قبل التسليم" --build v1.0.1 --commit abc123
  python3 .claude/hrms/scripts/testrun.py --list                    # كل الرحلات
  python3 .claude/hrms/scripts/testrun.py --list --role HR          # رحلات دور
  python3 .claude/hrms/scripts/testrun.py --list --type security
  python3 .claude/hrms/scripts/testrun.py --show EMP-03             # تفاصيل رحلة
  python3 .claude/hrms/scripts/testrun.py --next                    # الرحلة التالية
  python3 .claude/hrms/scripts/testrun.py --result EMP-03 fail --note "..." --evidence run1/emp03.png
  python3 .claude/hrms/scripts/testrun.py --summary                 # ملخص الجولة
  python3 .claude/hrms/scripts/testrun.py --report                  # تقرير للعميل

النتائج: pass · fail · blocked · skipped · partial
يخرج بكود 1 لو أي رحلة blocker فشلت أو لم تُنفَّذ.
"""
import json, os, sys, argparse, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAT = os.path.join(BASE, "journeys", "catalog.json")
RUN = os.path.join(BASE, "journeys", "current-run.json")
EV = os.path.join(BASE, "evidence")

VALID = {"pass", "fail", "blocked", "skipped", "partial", "pending"}
MARK = {"pass": "[PASS]", "fail": "[FAIL]", "blocked": "[BLKD]",
        "skipped": "[SKIP]", "partial": "[PART]", "pending": "[  . ]"}


def cat():
    return json.load(open(CAT, encoding="utf-8"))


def run():
    return json.load(open(RUN, encoding="utf-8")) if os.path.exists(RUN) else None


def save(r):
    json.dump(r, open(RUN, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def find(c, jid):
    return next((j for j in c["journeys"] if j["id"] == jid.upper()), None)


def show(j):
    sev = f"  [{j.get('severity','normal').upper()}]"
    print(f"\n{'='*62}\n{j['id']}  {j['role']}  ({j['type']}){sev}\n{'='*62}")
    print(f"{j['title']}\n")
    print("الخطوات:")
    for i, s in enumerate(j["steps"], 1):
        print(f"  {i}. {s}")
    print("\nالمتوقع:")
    for e in j["expect"].split(" · "):
        print(f"  - {e}")
    if j.get("blocks"):
        print(f"\nيغطي بنود: {', '.join(j['blocks'])}")
    if j.get("note"):
        print(f"\nملاحظة: {j['note']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--new"); p.add_argument("--build", default=""); p.add_argument("--commit", default="")
    p.add_argument("--env", default=""); p.add_argument("--url", default="")
    p.add_argument("--list", action="store_true"); p.add_argument("--role"); p.add_argument("--type")
    p.add_argument("--show"); p.add_argument("--next", action="store_true")
    p.add_argument("--summary", action="store_true"); p.add_argument("--report", action="store_true")
    p.add_argument("--result", nargs=2, metavar=("ID", "RESULT"))
    p.add_argument("--note", default=""); p.add_argument("--evidence", default="")
    a = p.parse_args()
    c = cat()

    if a.new:
        rid = datetime.datetime.now().strftime("run-%Y%m%d-%H%M")
        os.makedirs(os.path.join(EV, rid), exist_ok=True)
        save({"run_id": rid, "label": a.new, "build": a.build, "commit": a.commit,
              "env": a.env, "url": a.url, "started": datetime.datetime.now().isoformat(timespec="minutes"),
              "results": {j["id"]: {"result": "pending", "note": "", "evidence": ""} for j in c["journeys"]}})
        print(f"جولة جديدة: {rid}  ({a.new})")
        print(f"الأدلة في: .claude/hrms/evidence/{rid}/")
        if not (a.build and a.commit):
            print("!! سجّل build و commit — بدونهما التقرير غير صالح للتسليم")
        return 0

    if a.show:
        j = find(c, a.show)
        if not j:
            print(f"غير موجود: {a.show}"); return 2
        show(j)
        r = run()
        if r:
            cur = r["results"].get(j["id"], {})
            print(f"\nالنتيجة: {cur.get('result','pending')}  {cur.get('note','')}")
        return 0

    js = c["journeys"]
    if a.role:
        js = [j for j in js if j["role"].lower() in (a.role.lower(), "all", "any")]
    if a.type:
        js = [j for j in js if j["type"] == a.type.lower()]

    r = run()
    if a.result:
        if not r:
            print("لا توجد جولة نشطة. شغّل --new أولا."); return 2
        jid, res = a.result[0].upper(), a.result[1].lower()
        if res not in VALID:
            print(f"نتيجة غير صالحة. المسموح: {', '.join(sorted(VALID))}"); return 2
        if not find(c, jid):
            print(f"رحلة غير موجودة: {jid}"); return 2
        if res == "fail" and not a.note:
            print("!! الفشل يحتاج --note يصف ما حدث بالضبط"); return 2
        r["results"][jid] = {"result": res, "note": a.note, "evidence": a.evidence,
                             "at": datetime.datetime.now().isoformat(timespec="minutes")}
        save(r)
        print(f"{MARK[res]} {jid}" + (f"  {a.note}" if a.note else ""))
        return 0

    if a.next:
        if not r:
            print("لا توجد جولة نشطة. شغّل --new أولا."); return 2
        order = {"smoke": 0, "security": 1, "journey": 2, "ux": 3}
        cand = [j for j in js if r["results"].get(j["id"], {}).get("result", "pending") == "pending"]
        cand.sort(key=lambda j: (order.get(j["type"], 9), 0 if j.get("severity") == "blocker" else 1))
        if not cand:
            print("كل الرحلات في هذا النطاق نُفِّذت."); return 0
        show(cand[0])
        print(f"\n(متبقٍ {len(cand)} رحلة)")
        return 0

    if a.report or a.summary:
        if not r:
            print("لا توجد جولة نشطة."); return 2
        print(f"=== {r['label']} ===")
        print(f"Run: {r['run_id']} · Build: {r['build'] or '—'} · Commit: {r['commit'] or '—'} · Env: {r['env'] or '—'}")
        counts, failed_blockers = {}, []
        for j in c["journeys"]:
            res = r["results"].get(j["id"], {})
            v = res.get("result", "pending")
            counts[v] = counts.get(v, 0) + 1
            if j.get("severity") == "blocker" and v != "pass":
                failed_blockers.append((j, res))
            if a.report and v in ("fail", "partial", "blocked"):
                print(f"\n{MARK[v]} {j['id']}  {j['title']}")
                print(f"       {res.get('note','')}")
                if res.get("evidence"):
                    print(f"       دليل: {res['evidence']}")
                if j.get("blocks"):
                    print(f"       بنود متأثرة: {', '.join(j['blocks'])}")
        total = len(c["journeys"])
        print(f"\n--- {counts.get('pass',0)}/{total} نجحت | " +
              " ".join(f"{k}={v}" for k, v in sorted(counts.items())) + " ---")
        if failed_blockers:
            print(f"\n!! {len(failed_blockers)} رحلة blocker لم تنجح — الحكم NO-GO:")
            for j, res in failed_blockers:
                print(f"   {j['id']}  {j['title']}  ({res.get('result','pending')})")
            return 1
        print("\nكل رحلات الـ blocker نجحت.")
        return 0

    # default: list
    cur = None
    for j in sorted(js, key=lambda j: j["id"]):
        v = r["results"].get(j["id"], {}).get("result", "pending") if r else "pending"
        if j["role"] != cur:
            cur = j["role"]
            print(f"\n=== {cur} ===")
        b = " [B]" if j.get("severity") == "blocker" else ""
        print(f"{MARK[v]} {j['id']:<8}{b:<4} {j['title']}")
    print(f"\n({len(js)} رحلة)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
