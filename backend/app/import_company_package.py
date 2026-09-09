# -*- coding: utf-8 -*-
"""إدخال حزمة مستندات شركة: فروعها وتراخيصها — بتقرير قبل الكتابة.

**لماذا أداة لا إدخال بيد**: أربعة عشر مستنًدا رسمًيا وأحد عشر فرًعا،
وكلٌّ له رقم ترخيص وتاريخا إصدار وانتهاء. والإدخال اليدوي على ذلك يخطئ
مرًة على الأقل، والخطأ في تاريخ انتهاء ترخيص يعني **تنبيه تجديد لا يأتي**
أو معاملة تُفتَح لترخيص ساري.

**والقواعد التي تحكم هذه الأداة**:

- **لا تكتب شيًئا بلا ``--apply``.** التقرير أوًلا، والقرار بعده.
- **تُعاد بلا ضرر.** كل صفّ يُطابَق على هويّته (رقم الفرع، ونوع المستند
  مع رقمه)، فتشغيٌل ثانٍ لا يُضاعف فرًعا ولا مستنًدا.
- **لا تخترع قيمة.** ما لم يكن في ملف البيانات يبقى فارًغا ويُذكر في
  التقرير. وملء الفراغ بتخمين في مستند رسمي أسوأ من تركه فارًغا.
- **البصمة قبل الرفع.** كل ملف يُوزَن مقابل ``SHA256`` المعلن في بيان
  الحزمة قبل أن يُحفَظ. ومستٌند رسميٌّ لا يطابق بصمته لا يدخل النظام:
  الفارق إمّا تلٌف وإمّا نسخٌة أخرى، وكلاهما يوقف الإدخال.
- **لا تمسّ ما ليس ناقًصا.** حقٌل له قيمة في القاعدة لا يُستبدَل؛ يُذكر
  الفارق في التقرير ويُترَك القرار لصاحبه.

الاستعمال::

    python -m app.import_company_package --data docs/data/blue_nile_import.json \\
                                         --source "<مجلد الحزمة>"
    # ... يقرأ ويقارن ويطبع، ولا يكتب.

    python -m app.import_company_package --data ... --source ... --apply
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .database import SessionLocal
from .storage import save_at_key

#: اسم ملف البيان داخل الحزمة — منه تُقرأ البصمات.
MANIFEST = "HRMS_Document_Upload_Mapping.txt"


# ---------------------------------------------------------------------------
# قراءة الحزمة
# ---------------------------------------------------------------------------

def _manifest_hashes(source: Path) -> dict[str, str]:
    """اسم الملف ← بصمته كما أعلنها منتج الحزمة."""
    hits = list(source.rglob(MANIFEST))
    if not hits:
        raise SystemExit(f"لا بيان في الحزمة ({MANIFEST}) — لا بصمات تُقارَن.")
    text = hits[0].read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for block in text.split("-" * 72):
        if not block.strip():
            continue
        d = dict(re.findall(r"^([A-Za-z0-9 /]+):\s*(.+)$", block, re.M))
        dest = (d.get("Destination") or "").strip()
        sha = (d.get("SHA256") or "").strip()
        if dest and sha:
            out[dest.split("/")[-1]] = sha
    return out


def _find(source: Path, name: str) -> Path | None:
    hits = list(source.rglob(name))
    return hits[0] if hits else None


def _d(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


# ---------------------------------------------------------------------------
# المطابقة
# ---------------------------------------------------------------------------

def _company(db: Session, spec: dict) -> models.Company | None:
    """الشركة كما هي في القاعدة — لا تُنشأ من هنا.

    **وإنشاء شركة ليس عمل مستورِد مستندات**: هويّتها ورقمها التجاري
    وممثّلها قرارات تُتَّخذ مرّة، وخطأ فيها يسري على كل ما تحتها.
    """
    m = spec.get("match_by") or {}
    if m.get("id"):
        return db.get(models.Company, int(m["id"]))
    if m.get("commercial_reg"):
        c = db.scalar(select(models.Company).where(
            models.Company.commercial_reg == m["commercial_reg"]))
        if c:
            return c
    needle = m.get("name_contains")
    if needle:
        for c in db.scalars(select(models.Company)).all():
            if needle in (c.name or ""):
                return c
    return None


def _branch(db: Session, company_id: int, b: dict) -> models.Branch | None:
    """الفرع بكوده — والكود هوية ثابتة لا تتغيّر بتغيّر الاسم."""
    return db.scalar(select(models.Branch).where(
        models.Branch.company_id == company_id,
        models.Branch.code == b["code"]))


def _document(db: Session, company_id: int, entity_type: str,
              entity_id: int, type_code: str) -> models.Document | None:
    return db.scalar(select(models.Document).where(
        models.Document.company_id == company_id,
        models.Document.entity_type == entity_type,
        models.Document.entity_id == entity_id,
        models.Document.document_type_code == type_code,
        models.Document.is_current == True,  # noqa: E712
    ))


# ---------------------------------------------------------------------------
# التشغيل
# ---------------------------------------------------------------------------

def run(data: dict, source: Path, *, apply: bool, db: Session) -> dict:
    report: dict[str, list[str]] = {
        "company": [], "branches": [], "documents": [], "skipped": [], "blocked": [],
    }

    company = _company(db, data["company"])
    if company is None:
        raise SystemExit(
            "الشركة غير موجودة في القاعدة. أنشئها من شاشة الشركات أوًلا — "
            "فهويّتها قراٌر يُتَّخذ مرّة، ولا يُتَّخذ من مستورِد مستندات."
        )
    report["company"].append(f"الشركة: #{company.id} — {company.name}")

    # ---- حقول الشركة: يُملأ الناقص، ولا يُستبدَل الموجود -------------------
    for field in ("name_en", "entity_type", "file_number", "commercial_reg"):
        new = (data["company"].get(field) or "").strip()
        if not new:
            continue
        cur = (getattr(company, field, None) or "").strip()
        if not cur:
            report["company"].append(f"  + {field} = {new}")
            if apply:
                setattr(company, field, new)
        elif cur != new:
            # **فارٌق يُعرَض ولا يُحسَم**: القيمة القائمة قد تكون الأصحّ.
            report["blocked"].append(
                f"الشركة.{field}: في القاعدة «{cur}» وفي المستندات «{new}» — لم يُغيَّر")

    # ---- الفروع ----------------------------------------------------------
    by_no: dict[str, models.Branch] = {}
    #: الفروع التي **ستُنشأ** — يحتاجها التقرير ليُري الخطة كاملة قبل
    #: التنفيذ. وبلا هذا كان التقرير الجافّ يخفي أحد عشر مستنًدا فرعًيا
    #: خلف «فرعه لم يُنشأ بعد»، فيُقرَأ نقًصا وهو ترتيٌب.
    planned: dict[str, dict] = {}
    for b in data["branches"]:
        existing = _branch(db, company.id, b)
        if existing is None:
            planned[b["no"]] = b
            report["branches"].append(f"  + فرع جديد: {b['code']} — {b['name']}")
            if apply:
                existing = models.Branch(
                    company_id=company.id, name=b["name"], code=b["code"],
                    governorate=b.get("governorate"),
                    governorate_en=b.get("governorate_en"),
                    address=b.get("address"),
                    # سرٌّ لكل فرع: مشترٌك بين فرعين يعني بصًما من مكان لآخر.
                    qr_secret=secrets.token_hex(16),
                    kiosk_key=secrets.token_hex(16))
                db.add(existing)
                db.flush()
        else:
            report["branches"].append(f"  = فرع قائم: {b['code']} — {existing.name}")
            for field in ("governorate", "governorate_en", "address"):
                new = b.get(field)
                if new and not getattr(existing, field, None):
                    report["branches"].append(f"      + {field} = {new}")
                    if apply:
                        setattr(existing, field, new)
        if existing is not None:
            by_no[b["no"]] = existing
        # الإحداثيات لا تأتي من المستندات — تُذكر ولا تُخمَّن.
        if existing is not None and not getattr(existing, "latitude", None):
            report["skipped"].append(
                f"الفرع {b['code']}: بلا إحداثيات — البصم بالموقع لا يعمل حتى تُضبَط")

    # ---- المستندات -------------------------------------------------------
    hashes = _manifest_hashes(source)
    for doc in data["documents"]:
        name = doc["file"]
        path = _find(source, name)
        if path is None:
            report["blocked"].append(f"مفقود من الحزمة: {name}")
            continue

        raw = path.read_bytes()
        got = hashlib.sha256(raw).hexdigest()
        want = hashes.get(name)
        if want and got != want:
            # **مستند رسمي لا يطابق بصمته لا يدخل** — تلٌف أو نسخٌة أخرى.
            report["blocked"].append(
                f"بصمة مخالفة: {name} ({got[:12]} ≠ {want[:12]}) — لم يُرفع")
            continue
        if not want:
            report["blocked"].append(f"لا بصمة معلنة لـ{name} — لم يُرفع")
            continue

        if doc["entity"] == "company":
            entity_type, entity = "company", company
        else:
            entity_type = "branch"
            entity = by_no.get(doc.get("branch_no"))
            if entity is None:
                plan = planned.get(doc.get("branch_no"))
                if plan is not None:
                    # تقريٌر لا نقص: الفرع سيُنشأ في التشغيل نفسه.
                    report["documents"].append(
                        f"  + {doc['type_code']} → الفرع الجديد {plan['code']} "
                        f"({doc.get('number')} · ينتهي {doc.get('expiry') or '—'})")
                else:
                    report["blocked"].append(
                        f"{name}: لا فرع بالرقم ({doc.get('branch_no')}) في ملف البيانات")
                continue

        found = _document(db, company.id, entity_type, entity.id, doc["type_code"])
        if found is not None:
            report["documents"].append(
                f"  = موجود: {doc['type_code']} على {entity_type}#{entity.id}")
            continue

        report["documents"].append(
            f"  + {doc['type_code']} → {entity_type}#{entity.id} "
            f"({doc.get('number')} · ينتهي {doc.get('expiry') or '—'})")
        if apply:
            key = f"archive/{company.id}/{entity_type}_{entity.id}/{name}"
            saved = save_at_key(raw, key)
            db.add(models.Document(
                company_id=company.id, entity_type=entity_type, entity_id=entity.id,
                document_type_code=doc["type_code"], title=doc.get("title"),
                file_path=saved, mime="application/pdf",
                issue_date=_d(doc.get("issued")), expiry_date=_d(doc.get("expiry")),
                version=1, is_current=True,
                notify_on_expiry=bool(doc.get("expiry")),
                checksum_sha256=got,
                # ورقم المستند وجهته يُحفظان حيث تقرؤهما شاشة الأرشيف:
                # «من أصدر هذه الورقة؟» سؤاٌل يُجاب من السجل لا من فتح الملف.
                extracted_data_json={"doc_number": doc.get("number"),
                                     "issuing_authority": doc.get("issuing_authority"),
                                     "source_file": name,
                                     "imported_at": datetime.utcnow().isoformat()},
            ))

    if apply:
        db.commit()
    return report


# ---------------------------------------------------------------------------
# وضع الواجهة البرمجية — للموقع المنشور
# ---------------------------------------------------------------------------

def run_api(data: dict, source: Path, *, apply: bool, base: str,
            token: str) -> dict:
    """يُدخل الحزمة **عبر واجهة الموقع** لا عبر قاعدة البيانات مباشرة.

    **ولماذا وضٌع ثانٍ**: الكتابة في القاعدة من جهاز بعيد تحفظ ملفات
    الـPDF **على الجهاز**، بينما صفوف الموقع تشير إلى مفاتيح لا يجدها
    خادمه — مستٌند مسجَّل وتنزيله يعطي «الملف غير موجود». وهو بالضبط
    العطل الذي أُصلح في البند 28، يعود من باب إجراٍء لا من باب كود.

    وهنا يمرّ كل شيء من الباب نفسه الذي تمرّ منه الواجهة: **الخادم هو
    من يكتب**، فيحفظ الملف في مخزنه ويقيّد في سجل التدقيق باسم من رفع.
    """
    # ``httpx`` لا ``requests``: الأول مثبَّت في المشروع أصًلا، وإضافة
    # اعتماد جديد إلى الخادم من أجل أداة سطر أوامر كلفٌة بلا مقابل.
    import httpx

    api = base.rstrip("/") + "/api"
    s = httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=180)
    report: dict[str, list[str]] = {
        "company": [], "branches": [], "documents": [], "skipped": [], "blocked": [],
    }

    def _get(path, **kw):
        r = s.get(api + path, **kw)
        r.raise_for_status()
        return r.json()

    # ---- الشركة ----------------------------------------------------------
    needle = (data["company"].get("match_by") or {}).get("name_contains", "")
    companies = _get("/companies")
    match = [c for c in companies if needle in (c.get("name") or "")]
    if not match:
        raise SystemExit(
            f"لا شركة يطابق اسمها «{needle}» في هذا الموقع. "
            "أنشئها من شاشة الشركات أوًلا — هويّتها قراٌر يُتَّخذ مرّة.")
    if len(match) > 1:
        raise SystemExit(
            "أكثر من شركة تطابق الاسم: " + "، ".join(c["name"] for c in match))
    company = match[0]
    report["company"].append(f"الشركة: #{company['id']} — {company['name']}")

    # ---- الفروع ----------------------------------------------------------
    existing = {b.get("code"): b for b in _get("/branches") if b.get("code")}
    by_no: dict[str, dict] = {}
    for b in data["branches"]:
        found = existing.get(b["code"])
        if found:
            report["branches"].append(f"  = فرع قائم: {b['code']} — {found.get('name')}")
            by_no[b["no"]] = found
            continue
        report["branches"].append(f"  + فرع جديد: {b['code']} — {b['name']}")
        if apply:
            body = {"name": b["name"], "code": b["code"],
                    "governorate": b.get("governorate"),
                    "governorate_en": b.get("governorate_en"),
                    "address": b.get("address")}
            r = s.post(api + "/branches", json=body)
            if r.status_code >= 400:
                report["blocked"].append(f"تعذّر إنشاء {b['code']}: {r.status_code} {r.text[:160]}")
                continue
            by_no[b["no"]] = r.json()

    # ---- المستندات -------------------------------------------------------
    #: أنواع المستندات السارية لكل كيان — تُقرأ من الأرشيف نفسه، مرّة.
    _seen: dict[tuple[str, int], set[str]] = {}

    def _current_types(entity_type: str, entity_id: int) -> set[str]:
        key = (entity_type, entity_id)
        if key not in _seen:
            path = ("/archive/company" if entity_type == "company"
                    else f"/archive/branch/{entity_id}")
            try:
                _seen[key] = {d["type"] for d in _get(path).get("documents", [])}
            except Exception:
                _seen[key] = set()
        return _seen[key]

    hashes = _manifest_hashes(source)
    for doc in data["documents"]:
        name = doc["file"]
        path = _find(source, name)
        if path is None:
            report["blocked"].append(f"مفقود من الحزمة: {name}")
            continue
        raw = path.read_bytes()
        got = hashlib.sha256(raw).hexdigest()
        want = hashes.get(name)
        if not want or got != want:
            report["blocked"].append(
                f"بصمة مخالفة أو غائبة: {name} — لم يُرفع")
            continue

        if doc["entity"] == "company":
            entity_type, entity_id = "company", company["id"]
        else:
            target = by_no.get(doc.get("branch_no"))
            if target is None:
                report["skipped"].append(f"{name}: فرعه لم يُنشأ بعد")
                continue
            entity_type, entity_id = "branch", target["id"]

        # **الموجود لا يُرفع ثانًيا**: الرفع يُنشئ نسخًة جديدة، فتشغيٌل
        # ثانٍ يُنتج إصدارات وهمية لمستند لم يتغيّر — والأداة يجب أن
        # تُعاد بلا ضرر كما في وضع القاعدة.
        if doc["type_code"] in _current_types(entity_type, entity_id):
            report["documents"].append(
                f"  = موجود: {doc['type_code']} على {entity_type}#{entity_id}")
            continue

        report["documents"].append(
            f"  + {doc['type_code']} → {entity_type}#{entity_id} "
            f"({doc.get('number')} · ينتهي {doc.get('expiry') or '—'})")
        if not apply:
            continue

        form = {"entity_type": entity_type, "entity_id": str(entity_id),
                "document_type_code": doc["type_code"],
                "title": doc.get("title") or "",
                "doc_number": doc.get("number") or "",
                "issuing_authority": doc.get("issuing_authority") or ""}
        if doc.get("issued"):
            form["issue_date"] = doc["issued"]
        if doc.get("expiry"):
            form["expiry_date"] = doc["expiry"]
        r = s.post(api + "/documents/upload", data=form,
                   files={"file": (name, raw, "application/pdf")})
        if r.status_code >= 400:
            report["blocked"].append(f"تعذّر رفع {name}: {r.status_code} {r.text[:160]}")

    return report


def main() -> None:
    p = argparse.ArgumentParser(description="إدخال حزمة مستندات شركة")
    p.add_argument("--data", required=True, help="ملف البيانات المراجَع (JSON)")
    p.add_argument("--source", required=True, help="مجلد حزمة المستندات")
    p.add_argument("--apply", action="store_true", help="يكتب فعًلا")
    p.add_argument("--api", help="عنوان الموقع المنشور — يمرّ كل شيء من واجهته")
    p.add_argument("--civil-id", help="الرقم المدني للدخول (مع --api)")
    args = p.parse_args()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    source = Path(args.source)
    if not source.is_dir():
        raise SystemExit(f"مجلد الحزمة غير موجود: {source}")

    if args.api:
        import getpass

        import httpx

        civil = args.civil_id or input("الرقم المدني: ").strip()
        # **كلمة المرور لا تُمرَّر في سطر الأوامر ولا تُطبَع ولا تُحفَظ**:
        # سطر الأوامر يبقى في تاريخ الصدفة ويقرؤه غيرك.
        pw = getpass.getpass("كلمة المرور (لا تظهر): ")
        r = httpx.post(args.api.rstrip("/") + "/api/auth/login",
                       json={"civil_id": civil, "password": pw}, timeout=60)
        if r.status_code != 200:
            detail = r.json().get("detail") if r.headers.get(
                "content-type", "").startswith("application/json") else r.text[:200]
            raise SystemExit(f"تعذّر الدخول ({r.status_code}): {detail}")
        report = run_api(data, source, apply=args.apply,
                         base=args.api, token=r.json()["access_token"])
    else:
        db = SessionLocal()
        try:
            report = run(data, source, apply=args.apply, db=db)
        finally:
            db.close()

    head = "نُفِّذ" if args.apply else "تقرير فقط — لم يُكتب شيء"
    print(f"=== {head} ===")
    for section, title in (("company", "الشركة"), ("branches", "الفروع"),
                           ("documents", "المستندات")):
        if report[section]:
            print(f"\n{title}:")
            for line in report[section]:
                print(line)
    for section, title in (("skipped", "متروك — يحتاج بيانات ليست في المستندات"),
                           ("blocked", "موقوف — يحتاج قرارك")):
        if report[section]:
            print(f"\n{title}:")
            for line in report[section]:
                print(f"  · {line}")
    if not args.apply:
        print("\nلإجرائه فعًلا: أضف --apply")


if __name__ == "__main__":
    main()
