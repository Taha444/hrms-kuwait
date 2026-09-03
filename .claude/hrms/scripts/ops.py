#!/usr/bin/env python3
r"""
HRMS Ops Cleanup Tracker — 36 بندا · 7 تحقيقات · 12 سيناريو · 20 قاعدة حماية.

  python3 .claude/hrms/scripts/ops.py --init
  python3 .claude/hrms/scripts/ops.py                      # كل البنود
  python3 .claude/hrms/scripts/ops.py --pkg 2              # حزمة واحدة
  python3 .claude/hrms/scripts/ops.py --prio P0
  python3 .claude/hrms/scripts/ops.py --open
  python3 .claude/hrms/scripts/ops.py --next
  python3 .claude/hrms/scripts/ops.py --guards             # القواعد العشرون
  python3 .claude/hrms/scripts/ops.py --verify             # السبعة تحقيقات
  python3 .claude/hrms/scripts/ops.py --uncovered          # المناطق غير المغطاة
  python3 .claude/hrms/scripts/ops.py --dod                # السيناريوهات
  python3 .claude/hrms/scripts/ops.py --dod-show DOD-05
  python3 .claude/hrms/scripts/ops.py --set P1-01 done --note "commit / DOD-11"
  python3 .claude/hrms/scripts/ops.py --verify-set V-C confirmed --note "travel_required=true"
  python3 .claude/hrms/scripts/ops.py --dod-set DOD-11 pass --note "..."
  python3 .claude/hrms/scripts/ops.py --report

يخرج بكود 1 لو بقي أي P0 مفتوح أو أي سيناريو blocker لم ينجح.
"""
import json, os, sys, argparse, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(BASE, "ops", "registry.json")
ST = os.path.join(BASE, "ops", "status.json")

DONE = {"done", "verified", "na"}
ITEM_STATES = {"open", "in_progress", "done", "verified", "blocked", "na"}
VER_STATES = {"pending", "confirmed", "not_reproducible", "setup_only"}
DOD_STATES = {"pending", "pass", "fail", "blocked"}
MARK = {"open": "[   ]", "in_progress": "[ > ]", "done": "[ X ]", "verified": "[ OK]",
        "blocked": "[ ! ]", "na": "[N/A]", "pending": "[   ]", "confirmed": "[CONF]",
        "not_reproducible": "[ NR ]", "setup_only": "[SETUP]", "pass": "[PASS]", "fail": "[FAIL]"}
PW = {"P0": 0, "P1": 1, "P2": 2, "GUARD": 3}


def reg():
    return json.load(open(REG, encoding="utf-8"))


def st():
    return json.load(open(ST, encoding="utf-8")) if os.path.exists(ST) else {}


def save(s):
    json.dump(s, open(ST, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--init", action="store_true")
    p.add_argument("--pkg"); p.add_argument("--prio"); p.add_argument("--skill")
    p.add_argument("--open", action="store_true"); p.add_argument("--next", action="store_true")
    p.add_argument("--guards", action="store_true"); p.add_argument("--verify", action="store_true")
    p.add_argument("--uncovered", action="store_true"); p.add_argument("--dod", action="store_true")
    p.add_argument("--dod-show"); p.add_argument("--report", action="store_true")
    p.add_argument("--set", nargs=2, metavar=("ID", "STATE"))
    p.add_argument("--verify-set", nargs=2, metavar=("ID", "STATE"))
    p.add_argument("--dod-set", nargs=2, metavar=("ID", "STATE"))
    p.add_argument("--note", default="")
    a = p.parse_args()
    r = reg()

    if a.init:
        save({"items": {i["id"]: {"state": "open", "note": "", "at": ""} for i in r["items"]},
              "verify": {v["id"]: {"state": "pending", "note": "", "at": ""} for v in r["verify"]},
              "dod": {d["id"]: {"state": "pending", "note": "", "at": ""} for d in r["dod"]}})
        print(f"تم الإنشاء: {len(r['items'])} بند · {len(r['verify'])} تحقيق · {len(r['dod'])} سيناريو")
        return 0

    s = st()
    if not s:
        print("!! شغّل --init أولا"); return 2
    today = datetime.date.today().isoformat()

    if a.guards:
        print("=== قواعد لا تُكسر — Package 12 ===\n")
        for n, g in enumerate(r["guardrails"], 1):
            print(f"{n:2}. {g}")
        print("\nأي تعديل يمس واحدة منها: توقّف واطلب موافقة صريحة.")
        return 0

    if a.uncovered:
        print("=== مناطق لم تُغطَّ — لا تُعتبر سليمة ===\n")
        for m in r["uncovered_modules"]:
            print(f"  · {m}")
        print("\nالإصلاحات الحالية ليست إثباتا أن هذه المناطق سليمة.")
        print("Retest منفصل إلزامي بعد توفير حسابات QA.")
        print("\n!! Impersonation: Finding سابق high بلا دليل إصلاح — لا يُعتبر ناجحا.")
        return 0

    if a.verify:
        print("=== تحقيقات قبل الإصلاح — Package 13 ===\n")
        for v in r["verify"]:
            cur = s["verify"].get(v["id"], {})
            stt = cur.get("state", "pending")
            print(f"{MARK.get(stt,'[?]')} {v['id']}  {v['title']}")
            print(f"        {v['note']}")
            print(f"        السكيل: {v['skill']}")
            if cur.get("note"):
                print(f"        النتيجة: {cur['note']}")
            print()
        openv = sum(1 for v in r["verify"] if s["verify"].get(v["id"], {}).get("state", "pending") == "pending")
        print(f"--- {len(r['verify'])-openv}/{len(r['verify'])} محسوم ---")
        if openv:
            print("!! لا تصلح البنود المرتبطة قبل حسم تحقيقها.")
        return 0

    if a.dod_show:
        d = next((x for x in r["dod"] if x["id"] == a.dod_show.upper()), None)
        if not d:
            print(f"غير موجود: {a.dod_show}"); return 2
        cur = s["dod"].get(d["id"], {})
        print(f"\n{d['id']} — {d['title']}\n{'='*60}")
        for step in d["flow"].split(" → "):
            print(f"  → {step}")
        print(f"\nالحالة: {cur.get('state','pending')}  {cur.get('note','')}")
        return 0

    if a.dod:
        print("=== تعريف الإنجاز — 12 سيناريو ===\n")
        for d in r["dod"]:
            cur = s["dod"].get(d["id"], {})
            stt = cur.get("state", "pending")
            print(f"{MARK.get(stt,'[?]')} {d['id']}  {d['title']}")
            if cur.get("note"):
                print(f"        {cur['note']}")
        pas = sum(1 for d in r["dod"] if s["dod"].get(d["id"], {}).get("state") == "pass")
        print(f"\n--- {pas}/{len(r['dod'])} نجح ---")
        print("endpoint=200 أو button works أو record saved ليست إثباتا.")
        return pas != len(r["dod"])

    for flag, key, states, label in ((a.set, "items", ITEM_STATES, "بند"),
                                     (a.verify_set, "verify", VER_STATES, "تحقيق"),
                                     (a.dod_set, "dod", DOD_STATES, "سيناريو")):
        if not flag:
            continue
        iid, v = flag[0].upper(), flag[1].lower()
        if v not in states:
            print(f"!! الحالة من: {', '.join(sorted(states))}"); return 2
        if iid not in s[key]:
            print(f"!! {label} غير موجود: {iid}"); return 2
        if v in ("done", "verified", "pass", "confirmed") and not a.note:
            print("!! يحتاج --note بالدليل (commit · سيناريو DOD · مخرَج فعلي)"); return 2
        s[key][iid] = {"state": v, "note": a.note, "at": today}
        save(s)
        print(f"{MARK.get(v,'[?]')} {iid} → {v}  {a.note}")
        return 0

    items = r["items"]
    if a.pkg:
        items = [i for i in items if i["pkg"] == str(a.pkg)]
    if a.prio:
        items = [i for i in items if i["prio"] == a.prio.upper()]
    if a.skill:
        items = [i for i in items if a.skill in i["skill"]]

    if a.next:
        cand = [i for i in items if s["items"].get(i["id"], {}).get("state", "open") not in DONE]
        cand.sort(key=lambda i: PW.get(i["prio"], 9))
        if not cand:
            print("لا يوجد بند مفتوح في هذا النطاق."); return 0
        i = cand[0]
        print(f"\n{i['id']}  [{i['prio']}]  Package {i['pkg']} — {r['packages'][i['pkg']]}")
        print(f"{i['title']}\n\nالسكيل: {i['skill']}")
        vlink = [v for v in r["verify"] if v["skill"] == i["skill"]
                 and s["verify"].get(v["id"], {}).get("state", "pending") == "pending"]
        if vlink:
            print(f"\n!! تحقيق غير محسوم في نفس المنطقة: {', '.join(v['id'] for v in vlink)}")
            print("   احسمه قبل الإصلاح.")
        print(f"\n(متبقٍ {len(cand)})")
        return 0

    cur, counts, open_p0 = None, {}, []
    for i in sorted(items, key=lambda i: (int(i["pkg"]), PW.get(i["prio"], 9))):
        v = s["items"].get(i["id"], {}).get("state", "open")
        counts[v] = counts.get(v, 0) + 1
        if i["prio"] == "P0" and v not in DONE:
            open_p0.append(i)
        if a.open and v in DONE:
            continue
        if i["pkg"] != cur:
            cur = i["pkg"]
            print(f"\n=== Package {cur} — {r['packages'][cur]} ===")
        print(f"{MARK.get(v,'[?]')} {i['id']:<8} [{i['prio']:<5}] {i['title']}")
        n = s["items"].get(i["id"], {}).get("note", "")
        if n:
            print(f"          {n}")

    tot = len(items)
    done = sum(counts.get(k, 0) for k in DONE)
    print(f"\n--- {done}/{tot} ({round(100*done/tot) if tot else 0}%) | " +
          " ".join(f"{k}={v}" for k, v in sorted(counts.items())) + " ---")

    if a.report:
        pas = sum(1 for d in r["dod"] if s["dod"].get(d["id"], {}).get("state") == "pass")
        vdone = sum(1 for v in r["verify"] if s["verify"].get(v["id"], {}).get("state", "pending") != "pending")
        print(f"\nالسيناريوهات: {pas}/{len(r['dod'])} · التحقيقات: {vdone}/{len(r['verify'])}")
        print(f"المناطق غير المغطاة: {len(r['uncovered_modules'])} — تُذكر صراحة كـ«لم تُختبر»")

    if open_p0:
        print(f"\n!! {len(open_p0)} بند P0 مفتوح:")
        for i in open_p0:
            print(f"   {i['id']}  {i['title']}")
        return 1
    print("\nكل بنود P0 مغلقة.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
