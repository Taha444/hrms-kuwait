#!/usr/bin/env python3
"""
HRMS Backend Probe Matrix
يسجّل دخول بكل دور ويفحص كل endpoint، ويبني مصفوفة دور × مسار × كود الحالة.

  source .claude/hrms/scripts/env.sh
  python3 .claude/hrms/scripts/probe_matrix.py --read-only        # المصفوفة الأساسية
  python3 .claude/hrms/scripts/probe_matrix.py --idor             # فحص IDOR
  python3 .claude/hrms/scripts/probe_matrix.py --fields           # تسريب الحقول
  python3 .claude/hrms/scripts/probe_matrix.py --errors           # تسريب رسائل الخطأ
  python3 .claude/hrms/scripts/probe_matrix.py --exposed          # مسارات مكشوفة
  python3 .claude/hrms/scripts/probe_matrix.py --all              # كل ما سبق

قراءة فقط بالكامل — لا يرسل POST/PUT/PATCH/DELETE إطلاقا.
الأدلة تُحفظ في .claude/hrms/audit/evidence/
"""
import os, sys, json, argparse, urllib.request, urllib.error, datetime, ssl

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUD = os.path.join(BASE, "audit")
EV = os.path.join(AUD, "evidence")
EP_FILE = os.path.join(AUD, "endpoints.json")

ROLES = ["EMPLOYEE", "SUPERVISOR", "MANAGER", "HR", "ACCOUNTANT", "PRO", "OWNER", "SUPERADMIN"]

# مسارات افتراضية — عدّلها في endpoints.json بعد الجرد
DEFAULT_EPS = [
    "/api/employees", "/api/requests", "/api/tasks", "/api/notifications",
    "/api/renewals", "/api/payroll", "/api/eos", "/api/documents",
    "/api/signatures", "/api/audit", "/api/users", "/api/permissions",
    "/api/companies", "/api/templates", "/api/warnings", "/api/grievances",
    "/api/leaves", "/api/attendance", "/api/me/signature/history",
]

# دور: قائمة أنماط ممنوعة عليه (تُطابق بالاحتواء)
FORBIDDEN = {
    "EMPLOYEE":   ["/users", "/permissions", "/templates", "/audit", "/payroll",
                   "/eos", "/warnings", "/grievances", "/companies"],
    "SUPERVISOR": ["/payroll", "/eos", "/users", "/permissions", "/templates", "/audit"],
    "ACCOUNTANT": ["/passport", "/civil-id", "/contract", "/warnings", "/eos",
                   "/leaves", "/documents", "/grievances"],
    "PRO":        ["/payroll", "/eos", "/grievances", "/warnings"],
    "MANAGER":    ["/grievances", "/permissions"],
}

SENSITIVE_FIELDS = ["basic_salary", "gross_salary", "salary", "iban", "passport_no",
                    "civil_id", "passport", "bank_account", "start_date", "end_date"]

EXPOSED = ["/.env", "/.git/config", "/api/config", "/actuator", "/debug",
           "/swagger", "/api-docs", "/backup", "/phpinfo.php", "/admin",
           "/.git/HEAD", "/config.json", "/server-status"]

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

findings = []


def env(k, d=""):
    return os.environ.get(k, d)


def req(url, token=None, timeout=20):
    r = urllib.request.Request(url, method="GET")
    r.add_header("Accept", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=timeout, context=CTX) as resp:
            return resp.status, resp.read(200000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(200000).decode("utf-8", "replace")
    except Exception as e:
        return 0, f"__ERR__ {e}"


def login(role):
    b = env("HRMS_BASE_URL")
    path = env("HRMS_LOGIN_PATH", "/api/auth/login")
    field = env("HRMS_TOKEN_FIELD", "token")
    u, p = env(f"HRMS_{role}_USER"), env(f"HRMS_{role}_PASS")
    if not u:
        return None
    # اسم حقل المستخدم يختلف بين الأنظمة: هذا النظام يستعمل civil_id.
    # يُقرأ من البيئة بدل تثبيته، فلا تُعدَّل الأداة لكل مشروع.
    user_field = env("HRMS_USER_FIELD", "username")
    data = json.dumps({user_field: u, "password": p}).encode()
    r = urllib.request.Request(b + path, data=data, method="POST")
    r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=20, context=CTX) as resp:
            body = json.loads(resp.read().decode("utf-8", "replace"))
        tok = body.get(field)
        if not tok and isinstance(body.get("data"), dict):
            tok = body["data"].get(field)
        return tok
    except Exception as e:
        print(f"  !! {role}: فشل الدخول — {e}")
        return None


def load_eps():
    if os.path.exists(EP_FILE):
        d = json.load(open(EP_FILE, encoding="utf-8"))
        return d.get("read_endpoints", DEFAULT_EPS)
    print(f"  (لا يوجد {EP_FILE} — استخدام القائمة الافتراضية. شغّل discover.sh أولا)")
    return DEFAULT_EPS


def add(sev, area, title, detail, ep="", role="", evidence=""):
    findings.append({"sev": sev, "area": area, "title": title, "detail": detail,
                     "endpoint": ep, "role": role, "evidence": evidence})


def save_ev(name, content):
    os.makedirs(EV, exist_ok=True)
    p = os.path.join(EV, name)
    open(p, "w", encoding="utf-8").write(content[:100000])
    return os.path.relpath(p, BASE)


def body_len(body):
    try:
        d = json.loads(body)
        d = d.get("data", d) if isinstance(d, dict) else d
        return len(d) if isinstance(d, (list, dict)) else "-"
    except Exception:
        return "-"


def matrix(tokens, eps):
    print("\n" + "=" * 78)
    print("مصفوفة الصلاحيات — دور × endpoint")
    print("الرمز: كود/عدد العناصر   ! = 200 لدور يُتوقع منعه   ? = خطأ خادم")
    print("=" * 78)
    active = [r for r in ROLES if tokens.get(r)]
    print(f"{'endpoint':<38}" + "".join(f"{r[:6]:<9}" for r in active))
    print("-" * 78)
    for ep in eps:
        line = f"{ep:<38}"
        for role in active:
            code, body = req(env("HRMS_BASE_URL") + ep, tokens[role])
            n = body_len(body)
            mark = ""
            if code == 200 and any(f in ep for f in FORBIDDEN.get(role, [])):
                if n not in ("-", 0):
                    mark = "!"
                    fn = save_ev(f"authz_{role}_{ep.strip('/').replace('/','_')}.json", body)
                    add("critical", "authz",
                        f"{role} يصل إلى {ep} ويحصل على بيانات",
                        f"كود 200 وعدد العناصر {n} — يُتوقع 403",
                        ep, role, fn)
            elif code >= 500:
                mark = "?"
                fn = save_ev(f"err5xx_{role}_{ep.strip('/').replace('/','_')}.txt", body)
                add("high", "stability", f"{ep} يرجع {code} للدور {role}",
                    "خطأ خادم — لا يجوز إخفاؤه من الواجهة", ep, role, fn)
            line += f"{code}/{n}{mark:<3}"[:9].ljust(9)
        print(line)
    print("-" * 78)
    print("راجع كل '!' يدويا: 200 بقائمة فارغة قد يكون سلوكا مقبولا، و200 ببيانات ثغرة.")


def idor(tokens, eps):
    print("\n" + "=" * 78)
    print("فحص IDOR — الوصول لسجل غير مملوك")
    print("=" * 78)
    ids = [int(x) for x in env("HRMS_PROBE_IDS", "1,2,5,10,11,99,999999").split(",")]
    targets = [e for e in eps if e.rstrip("/").count("/") <= 2 and
               any(k in e for k in ("employees", "requests", "documents", "renewals"))]
    if not targets:
        print("  لا توجد مسارات مرشحة. عدّل endpoints.json.")
        return
    for role in [r for r in ROLES if tokens.get(r)]:
        for ep in targets:
            hits = []
            for i in ids:
                code, body = req(f"{env('HRMS_BASE_URL')}{ep}/{i}", tokens[role])
                if code == 200 and len(body) > 40:
                    hits.append(i)
            if hits:
                print(f"  {role:<11} {ep}/{{id}}  →  200 على: {hits}")
                if len(hits) > 1 or (role == "EMPLOYEE" and hits):
                    fn = save_ev(f"idor_{role}_{ep.strip('/').replace('/','_')}.json",
                                 json.dumps({"ids_returning_200": hits}, ensure_ascii=False))
                    add("critical", "authz",
                        f"IDOR محتمل: {role} يقرأ {ep}/{{id}} لعدة معرّفات",
                        f"المعرّفات التي أرجعت 200: {hits}. تحقق يدويا أن السجلات مملوكة له فعلا.",
                        ep, role, fn)
    print("  ملاحظة: 200 على معرّف مملوك سليم. الخطر هو 200 على معرّف غير مملوك أو من شركة أخرى.")


def fields(tokens, eps):
    print("\n" + "=" * 78)
    print("فحص تسريب الحقول الحساسة")
    print("=" * 78)
    for role in [r for r in ROLES if tokens.get(r)]:
        if role in ("SUPERADMIN", "OWNER", "HR"):
            continue
        for ep in eps:
            code, body = req(env("HRMS_BASE_URL") + ep, tokens[role])
            if code != 200:
                continue
            leaked = [f for f in SENSITIVE_FIELDS if f'"{f}"' in body]
            if not leaked:
                continue
            bad = []
            if role in ("PRO", "SUPERVISOR") and any(
                    x in leaked for x in ("basic_salary", "gross_salary", "salary")):
                bad = [x for x in leaked if "salary" in x]
            if role == "ACCOUNTANT" and any(
                    x in leaked for x in ("passport_no", "passport", "civil_id")):
                bad = [x for x in leaked if x in ("passport_no", "passport", "civil_id")]
            if role == "EMPLOYEE" and any(x in leaked for x in ("start_date", "end_date")):
                bad = [x for x in leaked if x in ("start_date", "end_date")]
            if bad:
                print(f"  !! {role:<11} {ep}  →  {bad}")
                fn = save_ev(f"field_{role}_{ep.strip('/').replace('/','_')}.json", body)
                add("critical", "authz", f"{role} يرى حقولا محظورة في {ep}",
                    f"الحقول المسربة: {bad}", ep, role, fn)
            else:
                print(f"     {role:<11} {ep}  →  حقول حساسة موجودة: {leaked} (راجع يدويا)")


def errors(tokens):
    print("\n" + "=" * 78)
    print("فحص تسريب المعلومات في رسائل الخطأ")
    print("=" * 78)
    tok = next((t for t in tokens.values() if t), None)
    b = env("HRMS_BASE_URL")
    cases = [
        ("سجل غير موجود", f"{b}/api/employees/999999", tok),
        ("نوع خاطئ", f"{b}/api/employees/abc", tok),
        ("فرز خبيث", f"{b}/api/employees?sort=x'", tok),
        ("توكن غير صالح", f"{b}/api/employees", "invalid.token.here"),
        ("بلا توكن", f"{b}/api/employees", None),
    ]
    leaks = ["Traceback", "at java.", "SQLSTATE", "SELECT ", "stack", "/var/www",
             "/home/", "node_modules", "Exception", "Warning:", "syntax error",
             "PDOException", "ActiveRecord", "Laravel", "Django"]
    for name, url, t in cases:
        code, body = req(url, t)
        found = [k for k in leaks if k.lower() in body.lower()]
        status = "!! تسريب" if found else "سليم"
        print(f"  {name:<20} {code}  {status}  {found if found else ''}")
        if found:
            fn = save_ev(f"errleak_{name.replace(' ','_')}.txt", body)
            add("critical", "errors", f"تسريب معلومات في رسالة خطأ: {name}",
                f"العلامات: {found}", url, "", fn)


def exposed():
    print("\n" + "=" * 78)
    print("فحص المسارات المكشوفة")
    print("=" * 78)
    b = env("HRMS_BASE_URL")
    for p in EXPOSED:
        code, body = req(b + p)
        if code == 200 and len(body) > 20:
            print(f"  !! {p:<22} 200  ({len(body)} بايت) — مكشوف")
            fn = save_ev(f"exposed_{p.strip('/').replace('/','_').replace('.','')}.txt", body)
            add("critical", "exposure", f"مسار مكشوف للعامة: {p}",
                f"يرجع 200 بحجم {len(body)} بايت بلا مصادقة", p, "", fn)
        else:
            print(f"     {p:<22} {code}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--read-only", action="store_true")
    ap.add_argument("--idor", action="store_true")
    ap.add_argument("--fields", action="store_true")
    ap.add_argument("--errors", action="store_true")
    ap.add_argument("--exposed", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()

    if not env("HRMS_BASE_URL"):
        print("!! شغّل env.sh أولا: source .claude/hrms/scripts/env.sh")
        return 2

    os.makedirs(EV, exist_ok=True)
    print(f"الهدف: {env('HRMS_BASE_URL')}   البيئة: {env('HRMS_ENV','?')}")
    print(f"الوقت: {datetime.datetime.utcnow().isoformat(timespec='seconds')}Z\n")
    if env("HRMS_ENV") == "client":
        print("!! بيئة العميل — قراءة فقط. لا اختبار كتابة.\n")

    print("تسجيل الدخول:")
    tokens = {}
    for r in ROLES:
        t = login(r)
        tokens[r] = t
        print(f"  {r:<12} {'OK' if t else '—'}")
    if not any(tokens.values()):
        print("\n!! لم ينجح أي دخول. تحقق من env.sh ومن HRMS_LOGIN_PATH و HRMS_TOKEN_FIELD.")
        return 1

    eps = load_eps()
    run_all = a.all or not any([a.read_only, a.idor, a.fields, a.errors, a.exposed])
    if a.read_only or run_all:
        matrix(tokens, eps)
    if a.exposed or run_all:
        exposed()
    if a.errors or run_all:
        errors(tokens)
    if a.idor or run_all:
        idor(tokens, eps)
    if a.fields or run_all:
        fields(tokens, eps)

    out = os.path.join(AUD, "probe-findings.json")
    json.dump(findings, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    crit = sum(1 for f in findings if f["sev"] == "critical")
    print(f"\n{'='*78}\nالنتائج: {len(findings)}  منها critical: {crit}")
    print(f"محفوظة في: {os.path.relpath(out, BASE)}")
    print("استوردها بـ: python3 .claude/hrms/scripts/findings.py --import-probe")
    print("راجع كل نتيجة يدويا قبل اعتمادها — الأداة تشير ولا تحكم.")
    return 1 if crit else 0


if __name__ == "__main__":
    sys.exit(main())
