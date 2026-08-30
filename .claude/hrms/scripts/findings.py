#!/usr/bin/env python3
r"""
HRMS Audit Findings Registry
سجل نتائج المراجعة + تحليل الجذور + توليد التقرير.

  python3 .claude/hrms/scripts/findings.py --init
  python3 .claude/hrms/scripts/findings.py --add --title "..." --sev critical --area authz \
      --endpoint "GET /api/employees/5" --role accountant \
      --expected "403" --actual "200 مع بيانات جواز" \
      --repro "curl -H 'Authorization: Bearer $T' \$B/api/employees/5" \
      --impact "المحاسب يرى جوازات كل الموظفين" --evidence "evidence/authz_x.json"
  python3 .claude/hrms/scripts/findings.py --import-probe    # استيراد نتائج probe_matrix
  python3 .claude/hrms/scripts/findings.py                   # القائمة
  python3 .claude/hrms/scripts/findings.py --sev critical
  python3 .claude/hrms/scripts/findings.py --area authz
  python3 .claude/hrms/scripts/findings.py --roots            # تحليل الجذور
  python3 .claude/hrms/scripts/findings.py --set F-003 fixed --note "commit abc"
  python3 .claude/hrms/scripts/findings.py --report > audit-report.md

يخرج بكود 1 لو بقيت نتيجة critical مفتوحة.
"""
import json, os, sys, argparse, datetime  # noqa

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = os.path.join(BASE, "audit")
DB = os.path.join(AUD, "findings.json")
PROBE = os.path.join(AUD, "probe-findings.json")

AREAS = ["surface", "authz", "validation", "data", "workflow", "files",
         "errors", "exposure", "stability", "other"]
SEVS = ["critical", "high", "medium", "low"]
SW = {s: i for i, s in enumerate(SEVS)}
STATES = {"open", "confirmed", "false_positive", "fixed", "wontfix"}
MARK = {"open": "[   ]", "confirmed": "[ ! ]", "false_positive": "[ FP]",
        "fixed": "[ X ]", "wontfix": "[SKIP]"}

ROOTS = {
    "authz": "مصدر صلاحيات غير موحّد بين Menu/Route/API/Button",
    "data": "قيود في الكود بلا مقابل على مستوى قاعدة البيانات",
    "workflow": "انتقالات بلا شروط دخول مفحوصة على الخادم · الحالة تتقدم والأثر لا يقع",
    "validation": "الاعتماد على تحقق الواجهة بلا مقابل على الخادم",
    "files": "التحقق بالامتداد لا بالمحتوى · تخزين بلا حماية",
    "errors": "معالجة أخطاء تسرّب التفاصيل · تدقيق ناقص",
    "exposure": "مسارات وملفات مكشوفة بلا مصادقة",
    "stability": "أخطاء خادم مخفية أو غير معالجة",
    "surface": "مسارات غير مجرودة أو مهجورة بلا حراسة",
}


def db():
    if not os.path.exists(DB):
        return {"seq": 0, "items": []}
    return json.load(open(DB, encoding="utf-8"))


def save(d):
    os.makedirs(AUD, exist_ok=True)
    json.dump(d, open(DB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--init", action="store_true")
    p.add_argument("--add", action="store_true")
    p.add_argument("--import-probe", action="store_true")
    p.add_argument("--title"); p.add_argument("--sev", default="medium")
    p.add_argument("--area", default="other"); p.add_argument("--endpoint", default="")
    p.add_argument("--role", default=""); p.add_argument("--expected", default="")
    p.add_argument("--actual", default=""); p.add_argument("--repro", default="")
    p.add_argument("--impact", default=""); p.add_argument("--fix", default="")
    p.add_argument("--evidence", default=""); p.add_argument("--note", default="")
    p.add_argument("--set", nargs=2, metavar=("ID", "STATE"))
    p.add_argument("--roots", action="store_true"); p.add_argument("--report", action="store_true")
    a = p.parse_args()

    if a.init:
        save({"seq": 0, "items": []})
        print(f"تم إنشاء {DB}")
        return 0

    d = db()

    if a.add:
        if not a.title:
            print("!! --title مطلوب"); return 2
        if a.sev not in SEVS:
            print(f"!! --sev من: {', '.join(SEVS)}"); return 2
        if a.sev in ("critical", "high") and not a.repro:
            print("!! النتائج critical و high تحتاج --repro بخطوات قابلة للتكرار"); return 2
        d["seq"] += 1
        fid = f"F-{d['seq']:03d}"
        d["items"].append({
            "id": fid, "title": a.title, "sev": a.sev, "area": a.area,
            "endpoint": a.endpoint, "role": a.role, "expected": a.expected,
            "actual": a.actual, "repro": a.repro, "impact": a.impact,
            "fix": a.fix, "evidence": a.evidence, "state": "open", "note": "",
            "found": datetime.date.today().isoformat()})
        save(d)
        print(f"{fid}  [{a.sev}]  {a.title}")
        return 0

    if a.import_probe:
        if not os.path.exists(PROBE):
            print(f"!! لا يوجد {PROBE} — شغّل probe_matrix.py أولا"); return 2
        pf = json.load(open(PROBE, encoding="utf-8"))
        n = 0
        for f in pf:
            if any(i["title"] == f["title"] for i in d["items"]):
                continue
            d["seq"] += 1
            d["items"].append({
                "id": f"F-{d['seq']:03d}", "title": f["title"], "sev": f["sev"],
                "area": f["area"], "endpoint": f.get("endpoint", ""),
                "role": f.get("role", ""), "expected": "", "actual": f.get("detail", ""),
                "repro": "", "impact": "", "fix": "", "evidence": f.get("evidence", ""),
                "state": "open", "note": "تلقائي من probe — يحتاج تأكيدا يدويا",
                "found": datetime.date.today().isoformat()})
            n += 1
        save(d)
        print(f"استُوردت {n} نتيجة. **كلها تحتاج تأكيدا يدويا** — الأداة تشير ولا تحكم.")
        print("أكّد كل واحدة بـ --set <ID> confirmed أو استبعدها بـ false_positive")
        return 0

    if a.set:
        fid, stt = a.set[0].upper(), a.set[1].lower()
        if stt not in STATES:
            print(f"!! الحالة من: {', '.join(sorted(STATES))}"); return 2
        it = next((i for i in d["items"] if i["id"] == fid), None)
        if not it:
            print(f"!! غير موجود: {fid}"); return 2
        if stt == "fixed" and not a.note:
            print("!! الإغلاق يحتاج --note بالدليل"); return 2
        it["state"] = stt
        if a.note:
            it["note"] = a.note
        save(d)
        print(f"{MARK[stt]} {fid} → {stt}")
        return 0

    items = d["items"]
    if a.sev and (a.sev in SEVS) and not a.add:
        pass
    if a.area != "other" or "--area" in sys.argv:
        items = [i for i in items if i["area"] == a.area]
    if "--sev" in sys.argv:
        items = [i for i in items if i["sev"] == a.sev]

    if a.roots:
        print("=== تحليل الجذور ===\n")
        by = {}
        for i in items:
            if i["state"] in ("false_positive", "wontfix"):
                continue
            by.setdefault(i["area"], []).append(i)
        for area, lst in sorted(by.items(), key=lambda x: -len(x[1])):
            print(f"\n{ROOTS.get(area, area)}")
            print(f"  المنطقة: {area} · النتائج التابعة: {len(lst)}")
            for i in lst:
                print(f"    {i['id']}  [{i['sev']}]  {i['title']}")
            print(f"  → إصلاح الجذر قد يغلق {len(lst)} نتيجة")
        print("\nراجع القوائم — النتائج في منطقة واحدة قد تكون جذورا مختلفة. الحكم لك.")
        return 0

    if a.report:
        crit = [i for i in items if i["sev"] == "critical" and i["state"] not in ("fixed", "false_positive")]
        print("# تقرير مراجعة الـ Backend — Kuwait HRMS\n")
        print(f"التاريخ: {datetime.date.today().isoformat()}\n")
        print("املأ يدويا: الرابط · البيئة · Build · Commit · Migration Version · الأدوار المستخدمة\n")
        print("## الملخص التنفيذي\n")
        c = {s: sum(1 for i in items if i["sev"] == s and
                    i["state"] not in ("fixed", "false_positive")) for s in SEVS}
        print("| الخطورة | العدد |\n|---|---|")
        for s in SEVS:
            print(f"| {s} | {c[s]} |")
        print()
        if crit:
            print("**أخطر النتائج:**\n")
            for i in crit[:3]:
                print(f"- `{i['id']}` {i['title']}")
            print(f"\n**الحكم: غير صالح للتسليم** — {len(crit)} نتيجة critical مفتوحة.\n")
        else:
            print("**لا توجد نتائج critical مفتوحة.** راجع بقية النتائج قبل الحكم بالجاهزية.\n")
        print("## النتائج\n")
        for i in sorted(items, key=lambda i: (SW.get(i["sev"], 9), i["id"])):
            if i["state"] == "false_positive":
                continue
            print(f"### {i['id']} — {i['title']}\n")
            print(f"**الخطورة:** {i['sev']} · **المنطقة:** {i['area']} · **الحالة:** {i['state']}\n")
            if i["endpoint"]:
                print(f"**الـ endpoint:** `{i['endpoint']}`" + (f" · **الدور:** {i['role']}" if i["role"] else "") + "\n")
            if i["expected"]:
                print(f"**المتوقع:** {i['expected']}\n")
            if i["actual"]:
                print(f"**ما حدث:** {i['actual']}\n")
            if i["repro"]:
                print(f"**التكرار:**\n```bash\n{i['repro']}\n```\n")
            if i["impact"]:
                print(f"**الأثر:** {i['impact']}\n")
            if i["fix"]:
                print(f"**الإصلاح المقترح:** {i['fix']}\n")
            if i["evidence"]:
                print(f"**الدليل:** `{i['evidence']}`\n")
            print()
        print("## ما لم يُفحص\n")
        print("- اختبار حمل وأداء تحت ضغط\n- اختبار اختراق بأدوات متخصصة")
        print("- فحص المكتبات والاعتماديات\n- سباقات تزامن نادرة")
        print("- أخطاء منطق العمل التي تحتاج معرفة السياسة\n")
        print("أضف هنا أي اختبار لم يُنفَّذ لعدم توفر حساب أو بيانات.\n")
        print("## حدود المراجعة\n")
        print("> هذه مراجعة منهجية تكشف **فئات** من الأخطاء، وليست ضمانا بخلو النظام منها.")
        print("> نظام يحمل بيانات موظفين حقيقية يستحق **فحصا أمنيا مستقلا من طرف ثالث** قبل التسليم.")
        return 1 if crit else 0

    if not items:
        print("لا توجد نتائج بعد. شغّل probe_matrix.py ثم --import-probe، أو أضف بـ --add")
        return 0
    cur = None
    counts = {}
    for i in sorted(items, key=lambda i: (SW.get(i["sev"], 9), i["area"], i["id"])):
        counts[i["sev"]] = counts.get(i["sev"], 0) + 1
        if i["sev"] != cur:
            cur = i["sev"]
            print(f"\n=== {cur.upper()} ===")
        print(f"{MARK[i['state']]} {i['id']}  [{i['area']}] {i['title']}")
        if i["endpoint"]:
            print(f"        {i['endpoint']}  {i['role']}")
    openc = sum(1 for i in items if i["sev"] == "critical" and
                i["state"] not in ("fixed", "false_positive"))
    print(f"\n--- الإجمالي {len(items)} | " + " ".join(f"{k}={v}" for k, v in sorted(counts.items())) + " ---")
    if openc:
        print(f"!! {openc} نتيجة critical مفتوحة")
    return 1 if openc else 0


if __name__ == "__main__":
    sys.exit(main())
