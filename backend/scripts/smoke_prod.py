# -*- coding: utf-8 -*-
"""فحُص ما بعد النشر (DLV-27) — بلا كلمة مرور.

ما يُقاس بلا دخول يُقاس بعد كل نشرة، فلا يُكتفى بـ«البناء نجح»:

1. النظام حيّ: الواجهة تُحمَّل، و``/api/health`` يقول ok.
2. **النسخُة المنشورة هي المُختبَرة** (DLV-05): ``/api/version`` يحمل الالتزام
   المتوقَّع إن مُرِّر ``--expect``، وبيئتُه production لا development (DLV-07).
3. **النقاط المحروسة تردّ 401 لا 500**: 500 بلا دخول يعني أن الحارس لم
   يُبلَغ — عطٌل في الإقلاع أو في التوجيه.
4. **لا تسريب**: ملفات الأسرار والمستودع لا تُخدَم.
5. صفحُة التحقّق العامة تقول عن رمٍز مجهول ``valid: false`` — لا 500 ولا «صالح».

وفحُص الأدوار بكلمات مرورها في ``.claude/hrms/scripts/smoke.sh`` — يشغّله
صاحبُ الحسابات، لا يُكتب هنا ما لا يُرسَل.

يُشغَّل::

    backend/.venv/Scripts/python.exe backend/scripts/smoke_prod.py \\
        --base https://hrms-kuwait-production.up.railway.app --expect <commit>
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

PROTECTED = ("/api/employees", "/api/requests/mine", "/api/requests/inbox", "/api/tasks/my",
             "/api/payroll/runs",
             "/api/users", "/api/templates", "/api/renewals", "/api/dashboard")
SECRETS = {"/.env": ("DATABASE_URL", "SECRET_KEY"), "/.git/config": ("[core]",),
           "/backend/.env": ("DATABASE_URL",)}


def _get(url: str, method: str = "GET") -> tuple[int, str]:
    req = urllib.request.Request(url, method=method, headers={"User-Agent": "hrms-smoke"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read(200_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(20_000).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — الشبكة: يُسجَّل ولا يُسقط الفحص كلَّه
        return 0, str(e)


def _alembic_head() -> str | None:
    """آخر ترحيٍل في الشيفرة — ``None`` إن تعذّرت قراءته (فلا يُحكم بلا دليل)."""
    try:
        from pathlib import Path

        from alembic.config import Config
        from alembic.script import ScriptDirectory

        root = Path(__file__).resolve().parents[1]
        cfg = Config(str(root / "alembic.ini"))
        cfg.set_main_option("script_location", str(root / "alembic"))
        heads = ScriptDirectory.from_config(cfg).get_heads()
        return heads[0] if len(heads) == 1 else None
    except Exception:  # noqa: BLE001
        return None


def run(base: str, expect: str | None) -> list[tuple[bool, str]]:
    base = base.rstrip("/")
    out: list[tuple[bool, str]] = []

    code, body = _get(base + "/")
    out.append((code == 200 and "<html" in body.lower(), f"الواجهة / → {code}"))

    code, body = _get(base + "/api/health")
    ok = code == 200 and '"ok"' in body
    out.append((ok, f"/api/health → {code} {body[:60]}"))

    code, body = _get(base + "/api/version")
    try:
        v = json.loads(body)
    except ValueError:
        v = {}
    commit = str(v.get("commit_full") or v.get("commit") or "")
    out.append((code == 200 and bool(commit), f"/api/version → {code} commit={commit[:12]}"))
    out.append((v.get("environment") == "production",
                f"البيئة = {v.get('environment')!r} (يجب production)"))
    if expect:
        out.append((commit.startswith(expect[:7]),
                    f"النسخة المنشورة {commit[:12]} ← المتوقَّعة {expect[:12]}"))

    # والترحيل الفاعل في القاعدة هو آخر ترحيٍل في الشيفرة (DLV-06 · DLV-08).
    code, body = _get(base + "/api/manifest")
    try:
        mf = json.loads(body)
    except ValueError:
        mf = {}
    head = _alembic_head()
    live = mf.get("migration_version")
    out.append((bool(live) and (head is None or live == head),
                f"الترحيل في القاعدة {live} ← آخر ترحيل في الشيفرة {head}"))
    out.append((bool(mf.get("deploy_time")), f"وقت النشر {mf.get('deploy_time')}"))

    for p in PROTECTED:
        code, _ = _get(base + p)
        out.append((code == 401, f"{p} بلا دخول → {code} (يجب 401)"))

    for p, marks in SECRETS.items():
        code, body = _get(base + p)
        leaked = code == 200 and any(m in body for m in marks)
        out.append((not leaked, f"{p} → {code}" + (" !! مكشوف" if leaked else "")))

    # توثيق الـAPI مطفأ في الإنتاج — لا خريطَة نقاٍط لزائر.
    code, body = _get(base + "/openapi.json")
    out.append(('"openapi"' not in body, f"/openapi.json → {code} (يجب ألّا يُخدَم المخطط)"))
    code, body = _get(base + "/docs")
    out.append(("swagger-ui" not in body, f"/docs → {code} (يجب ألّا يُخدَم Swagger)"))

    code, body = _get(base + "/api/verify/NO-SUCH-CODE-000")
    out.append((code in (200, 404) and '"valid":true' not in body.replace(" ", ""),
                f"/api/verify رمز مجهول → {code} {body[:40]} (يجب ألّا يُقال صالح)"))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://hrms-kuwait-production.up.railway.app")
    ap.add_argument("--expect", default=None, help="الالتزام المتوقَّع (أول 7 أحرف تكفي)")
    a = ap.parse_args(argv)
    results = run(a.base, a.expect)
    for ok, line in results:
        print(("PASS " if ok else "FAIL ") + line)
    failed = sum(1 for ok, _ in results if not ok)
    print(f"\n{len(results) - failed}/{len(results)} PASS")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
