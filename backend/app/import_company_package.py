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
from .arabic import contains_ar
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
        # **المطابقة على الصورة المجرَّدة**: الاسم يُكتب «الأزرق» و«الازرق»
        # في مستندات الشركة نفسها، فالمطابقة الحرفية ترى اسمين حيث يرى
        # القارئ اسًما واحًدا — وتقول «أنشئ الشركة» وهي قائمة.
        hits = [c for c in db.scalars(select(models.Company)).all()
                if contains_ar(c.name, needle)]
        # **واسٌم يطابق شركتين لا يُختار منه الأول صمتًا** — فروٌع ومستنداٌت
        # تذهب إلى شركٍة غير المقصودة. ووضُع الموقع يوقف بهذا من قبل؛
        # فالوضعان قاعدٌة واحدة.
        if len(hits) > 1:
            raise SystemExit(
                "أكثر من شركة تطابق الاسم: " + "، ".join(f"#{c.id} {c.name}" for c in hits)
                + " — حدِّدها بـmatch_by.id في ملف البيانات.")
        return hits[0] if hits else None
    return None


def _geo(b: dict) -> dict:
    """إحداثياُت الفرع ونصُف قطره من ملف البيانات — إن وُجدت.

    **لا تأتي من المستندات** (الترخيص لا يحمل إحداثيًّا)، بل من كويت فايندر
    بالرقم الآلي للوحدة، ويُذكر مصدرها في ملف البيانات (``_geo_source``).
    فلا تُخمَّن: ما لم يُذكر يبقى فارًغا ويُقال في التقرير.
    """
    out = {}
    if b.get("latitude") is not None and b.get("longitude") is not None:
        out["latitude"] = float(b["latitude"])
        out["longitude"] = float(b["longitude"])
        if b.get("geofence_radius_m"):
            out["geofence_radius_m"] = int(b["geofence_radius_m"])
    return out


def _same_shop(address: str | None, b: dict) -> bool:
    """هل عنواُن فرٍع قائم يحمل الرقَم الآلي لهذا المحل؟"""
    paci = (b.get("paci_address_no") or "").strip()
    return bool(paci and address and paci in address)


def _branch(db: Session, company_id: int, b: dict) -> models.Branch | None:
    """الفرع بكوده — ثم **بالرقم الآلي في عنوانه**.

    الكود هويٌة ثابتة، لكنه هويُّة النظام لا المحل: شركٌة أُدخلت فروعها
    بأكواٍد أخرى (يدوًيا أو قبل ملف الاستيراد) يُنشئ لها الكوُد وحده فرًعا
    ثانيًا للمحل نفسه — فيتوزّع حضوره وموظفوه على صّفين. والرقُم الآلي
    للوحدة هويُّة المحل عند الدولة، فيُطابَق به قبل أن يُنشأ شيء.
    """
    by_code = db.scalar(select(models.Branch).where(
        models.Branch.company_id == company_id,
        models.Branch.code == b["code"]))
    if by_code is not None:
        return by_code
    for existing in db.scalars(select(models.Branch).where(
            models.Branch.company_id == company_id)).all():
        if _same_shop(existing.address, b):
            return existing
    return None


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
    if data.get("headquarters"):
        report["skipped"].append(
            "مقر الشركة والتراخيص والفروع المخالفة للملف: تُطابَق عبر الموقع (--api) وحده")

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
                    kiosk_key=secrets.token_hex(16),
                    **_geo(b))
                db.add(existing)
                db.flush()
        else:
            report["branches"].append(
                f"  = فرع قائم: {b['code']} — {existing.name}"
                + (f" (بالرقم الآلي — كوده في النظام «{existing.code}»)"
                   if existing.code != b["code"] else ""))
            for field in ("governorate", "governorate_en", "address"):
                new = b.get(field)
                if new and not getattr(existing, field, None):
                    report["branches"].append(f"      + {field} = {new}")
                    if apply:
                        setattr(existing, field, new)
        if existing is not None:
            by_no[b["no"]] = existing
        geo = _geo(b)
        if geo:
            report["branches"].append(
                f"      ⌖ {geo['latitude']}, {geo['longitude']}"
                + (f" · {geo['geofence_radius_m']}م" if geo.get("geofence_radius_m") else ""))
            # فرٌع قائٌم بلا إحداثيات يأخذها؛ وما له إحداثيٌّ لا يُكتب فوقه.
            if apply and existing is not None and getattr(existing, "latitude", None) is None:
                for k, v in geo.items():
                    setattr(existing, k, v)
        # الإحداثيات لا تأتي من المستندات — تُذكر ولا تُخمَّن.
        elif existing is None or not getattr(existing, "latitude", None):
            report["skipped"].append(
                f"الفرع {b['code']}: بلا إحداثيات — البصم بالموقع لا يعمل حتى تُضبَط")

    # ---- المستندات -------------------------------------------------------
    hashes = _manifest_hashes(source) if data["documents"] else {}
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
            token: str, archive_extras: bool = False, delete_extras: bool = False) -> dict:
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
        "licenses": [], "extras": [],
    }

    def _get(path, **kw):
        r = s.get(api + path, **kw)
        r.raise_for_status()
        return r.json()

    # ---- الشركة ----------------------------------------------------------
    needle = (data["company"].get("match_by") or {}).get("name_contains", "")
    companies = _get("/companies")
    match = [c for c in companies if contains_ar(c.get("name"), needle)]
    if not match:
        raise SystemExit(
            f"لا شركة يطابق اسمها «{needle}» في هذا الموقع. "
            "أنشئها من شاشة الشركات أوًلا — هويّتها قراٌر يُتَّخذ مرّة.")
    if len(match) > 1:
        raise SystemExit(
            "أكثر من شركة تطابق الاسم: " + "، ".join(c["name"] for c in match))
    company = match[0]
    report["company"].append(f"الشركة: #{company['id']} — {company['name']}")

    # **وحقول الشركة كانت تُتخطّى صمًتا في هذا الوضع**: رقم الملف والسجل
    # التجاري والكيان القانوني تُقرأ من المستندات ثم لا تُكتب — فتدخل
    # الفروع والمستندات وتبقى هويّة الشركة فارغة. كشفته المراجعة بعد
    # الإدخال، لا قبله.
    fields = {k: (data["company"].get(k) or "").strip()
              for k in ("name_en", "entity_type", "file_number", "commercial_reg")}
    fill = {k: v for k, v in fields.items() if v and not (company.get(k) or "").strip()}
    kept = {k: (company.get(k), v) for k, v in fields.items()
            if v and (company.get(k) or "").strip() and company.get(k) != v}
    for k, (cur, new) in kept.items():
        report["blocked"].append(
            f"الشركة.{k}: على الموقع «{cur}» وفي المستندات «{new}» — لم يُغيَّر")
    if fill:
        report["company"].extend(f"  + {k} = {v}" for k, v in fill.items())
        if apply:
            # تعديٌل جزئي: ما لا يُرسَل لا يُمسّ — ومعاملات نهاية الخدمة
            # تبقى كما ضبطها صاحبها.
            r = s.put(api + f"/companies/{company['id']}", json=fill)
            if r.status_code >= 400:
                report["blocked"].append(
                    f"تعذّر تحديث حقول الشركة: {r.status_code} {r.text[:160]}")

    # ---- الفروع ----------------------------------------------------------
    mine = [x for x in _get("/branches", params={"company_id": company["id"]})
            if x.get("company_id") == company["id"]]
    existing = {x.get("code"): x for x in mine if x.get("code")}
    by_no: dict[str, dict] = {}
    for b in data["branches"]:
        # بالكود، ثم بالرقم الآلي في العنوان — المحلُّ نفسه بكوٍد آخر ليس فرًعا جديًدا.
        found = existing.get(b["code"]) or next(
            (x for x in mine if _same_shop(x.get("address"), b)), None)
        if found:
            other = found.get("code") != b["code"]
            report["branches"].append(
                f"  = فرع قائم: {b['code']} — {found.get('name')}"
                + (f" (بالرقم الآلي — كوده في الموقع «{found.get('code')}»)" if other else ""))
            if _geo(b) and found.get("latitude") is None:
                report["skipped"].append(
                    f"الفرع {found.get('code')}: قائٌم بلا إحداثيات — تُضبَط من شاشة الفروع "
                    f"({b['latitude']}, {b['longitude']})")
            by_no[b["no"]] = found
            continue
        report["branches"].append(f"  + فرع جديد: {b['code']} — {b['name']}")
        geo = _geo(b)
        if geo:
            report["branches"].append(
                f"      ⌖ {geo['latitude']}, {geo['longitude']}"
                + (f" · {geo['geofence_radius_m']}م" if geo.get("geofence_radius_m") else ""))
        if apply:
            body = {"name": b["name"], "code": b["code"],
                    "governorate": b.get("governorate"),
                    "governorate_en": b.get("governorate_en"),
                    "address": b.get("address"),
                    **_geo(b)}
            # الشركة صريحة: صاحب الشركات والإدارة العليا لا شركة لهما،
            # ومن له شركته يتجاهلها الخادم ويستعمل نطاقه.
            r = s.post(api + "/branches", json=body,
                       params={"company_id": company["id"]})
            if r.status_code >= 400:
                report["blocked"].append(f"تعذّر إنشاء {b['code']}: {r.status_code} {r.text[:160]}")
                continue
            by_no[b["no"]] = r.json()

    _reconcile_api(data, company, s, api, _get, report, apply=apply,
                   archive_extras=archive_extras, delete_extras=delete_extras)

    # ---- المستندات -------------------------------------------------------
    #: أنواع المستندات السارية لكل كيان — تُقرأ من الأرشيف نفسه، مرّة.
    _seen: dict[tuple[str, int], set[str]] = {}

    def _current_types(entity_type: str, entity_id: int) -> set[str]:
        key = (entity_type, entity_id)
        if key not in _seen:
            # أرشيف الشركة يشترط تحديدها لمن يرى كل الشركات — وبلا
            # تحديد يردّ 400، فيسقط فحص «هل رُفع من قبل؟» بصمت
            # فتُرفع نسخٌ ثانية لمستندات لم تتغيّر.
            if entity_type == "company":
                path, params = "/archive/company", {"company_id": entity_id}
            else:
                path, params = f"/archive/branch/{entity_id}", None
            try:
                _seen[key] = {d["type"] for d in
                              _get(path, params=params).get("documents", [])}
            except Exception:
                _seen[key] = set()
        return _seen[key]

    hashes = _manifest_hashes(source) if data["documents"] else {}
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
                "issuing_authority": doc.get("issuing_authority") or "",
                # المستند المخصَّص لا يُنبَّه على انتهائه ما لم يُفعَّل.
                "notify_on_expiry": "true" if doc.get("expiry") else "false"}
        if doc.get("issued"):
            form["issue_date"] = doc["issued"]
        if doc.get("expiry"):
            form["expiry_date"] = doc["expiry"]
        r = s.post(api + "/documents/upload", data=form,
                   files={"file": (name, raw, "application/pdf")})
        if r.status_code >= 400:
            report["blocked"].append(f"تعذّر رفع {name}: {r.status_code} {r.text[:160]}")

    return report


def _branch_no(code: str | None) -> str | None:
    m = re.search(r"(\d+)$", code or "")
    return str(int(m.group(1))) if m else None


def _complete_keeper(keep: dict, spec: dict, s, api: str, report: dict, *, apply: bool,
                     staffed: int = 0) -> None:
    """الفرع الباقي من المكرَّر يُكمَّل من ملف الشركة بما **ينقصه فقط**.

    الإحداثيات ونصف القطر والمحافظة: بلاها لا يعمل البصم بالموقع ولا يتولّد
    العقد الحكومي. ولا يُستبدَل ما عليه (اسمه وعنوانه يبقيان).

    **وكوده يُوحَّد مع ملف الشركة إن كان فارًغا** (لا موظفين): لا رقَم وظيفًيا
    يحمل كوده القديم، وإبقاُء ``MUT02`` مكان ``ML02`` يترك الشركة برموٍز
    لا تطابق ملفها. أمّا ذو الموظفين فكوده داخٌل في أرقامهم فلا يُمَسّ.
    """
    fill = {}
    if not staffed and keep.get("code") != spec.get("code"):
        fill["code"] = spec["code"]
    if keep.get("latitude") is None and spec.get("latitude") is not None:
        fill.update(_geo(spec))
    for k in ("governorate", "governorate_en"):
        if not keep.get(k) and spec.get(k):
            fill[k] = spec[k]
    tag = f"#{keep['id']} {keep.get('code')}"
    who = f"(عليه {staffed} موظف)" if staffed else "(فارغ)"
    if not fill:
        report["extras"].append(f"  ✓ يبقى {tag} {who} — لا ينقصه شيء من الملف")
        return
    label = {"code": "الكود", "governorate": "المحافظة", "governorate_en": "المحافظة"}
    what = "، ".join(sorted({label.get(k, "الإحداثيات") for k in fill}))
    if not apply:
        report["extras"].append(f"  ✓ يبقى {tag} {who} — يُكمَّل من الملف: {what} — مع --apply")
        return
    r = s.put(api + f"/branches/{keep['id']}", json=fill)
    report["extras"].append(
        f"  ✓ يبقى {tag} {who} — " + (f"كُمِّل من الملف: {what}" if r.status_code < 400
                                                else f"تعذّر إكماله: {r.status_code} {r.text[:120]}"))


def _reconcile_api(data: dict, company: dict, s, api: str, _get, report: dict, *,
                   apply: bool, archive_extras: bool, delete_extras: bool = False) -> None:
    """مقرُّ الشركة، وتراخيُصها، وفروعها المخالفة لملفها — طلب المالك (2026-09-19).

    **ملفُّ المالك هو المرجع** («محلات الشركات بالعناوين»): ما فيه يُنشأ، وما
    ليس فيه أو تكرّر يُعرَض ويُؤرشَف بطلبه (``--archive-extras``) — **لا يُحذف**،
    ولا يُؤرشَف فرٌع عليه موظفون: يُقال إلى أيّ فرٍع يُنقلون.
    والمطابقُة **بالأرقام لا بالأسماء**: الأسماء على الموقع قد تكون عربيًة أو
    إنجليزيًة أو بصيغٍة أخرى، والرقُم الآلي والرمُز ورقُم الترخيص ثابتة.
    """
    cid = company["id"]
    specs = list(data.get("branches") or [])
    hq_spec = data.get("headquarters")

    def _live():
        return [x for x in _get("/branches", params={"company_id": cid})
                if x.get("company_id") == cid]

    # ---- مقرُّ الشركة ------------------------------------------------------
    live = _live()
    hq = next((x for x in live if x.get("is_headquarters")), None)
    if hq_spec:
        if hq:
            report["branches"].append(f"  = مقر الشركة قائم: #{hq['id']} — {hq.get('name')}")
        else:
            geo = _geo(hq_spec)
            report["branches"].append(
                f"  + مقر الشركة (جديد) — {hq_spec.get('address')}"
                + (f"\n      ⌖ {geo['latitude']}, {geo['longitude']} · {geo.get('geofence_radius_m', 100)}م"
                   if geo else ""))
            if apply:
                body = {"name": "مقر الشركة", "code": hq_spec.get("code") or "HQ",
                        "governorate": hq_spec.get("governorate"),
                        "governorate_en": hq_spec.get("governorate_en"),
                        "address": hq_spec.get("address"), **geo}
                r = s.post(api + f"/companies/{cid}/headquarters", json=body)
                if r.status_code >= 400:
                    report["blocked"].append(f"تعذّر إنشاء مقر الشركة: {r.status_code} {r.text[:160]}")

    # ---- التراخيص --------------------------------------------------------
    try:
        existing_lic = {str(x.get("license_no") or "").strip(): x
                        for x in _get("/licenses", params={"company_id": cid})}
    except Exception as e:  # noqa: BLE001 — صلاحيٌة ناقصة تُقال ولا تُسقط الباقي
        existing_lic = None
        report["blocked"].append(f"تعذّرت قراءة التراخيص ({e}) — تحتاج صلاحية «إدارة التراخيص»")
    if existing_lic is not None:
        for spec in specs + ([{**hq_spec, "name": "مقر الشركة"}] if hq_spec else []):
            no = str(spec.get("license_no") or "").strip()
            if not no:
                continue
            cur = existing_lic.get(no)
            if cur is None:
                report["licenses"].append(
                    f"  + ترخيص {no} — {spec.get('name')} — ينتهي {spec.get('expiry') or '—'}")
                if apply:
                    params = {"name": spec.get("name"), "license_no": no, "company_id": cid,
                              "license_type": "commercial", "address": spec.get("address")}
                    if spec.get("expiry"):
                        params["expiry_date"] = spec["expiry"]
                    r = s.post(api + "/licenses", params=params)
                    if r.status_code >= 400:
                        report["blocked"].append(f"تعذّر تسجيل الترخيص {no}: {r.status_code} {r.text[:160]}")
            elif spec.get("expiry") and str(cur.get("expiry_date") or "")[:10] != spec["expiry"]:
                # **الملف هو المرجع** (قرار المالك 2026-09-23): يُضبَط الانتهاء عليه.
                report["licenses"].append(
                    f"  ≠ ترخيص {no}: انتهاؤه على الموقع «{cur.get('expiry_date')}» → "
                    f"«{spec['expiry']}» (من الملف)")
                if apply:
                    r = s.post(api + f"/pro/licenses/{cur['id']}/renew",
                               params={"expiry_date": spec["expiry"],
                                       "note": "مطابقة ملف الشركة 2026-09-23"})
                    if r.status_code >= 400:
                        report["blocked"].append(
                            f"تعذّر ضبط انتهاء الترخيص {no}: {r.status_code} {r.text[:160]}")
            else:
                report["licenses"].append(f"  = ترخيص قائم {no} — {spec.get('name')}")

    # ---- الفروع المخالفة للملف ------------------------------------------
    employees, offset = [], 0
    while True:
        page = _get("/employees", params={"company_id": cid, "limit": 500, "offset": offset})
        employees += page
        if len(page) < 500:
            break
        offset += 500
    staff = {}
    for e in employees:
        staff[e.get("branch_id")] = staff.get(e.get("branch_id"), 0) + 1

    live = [x for x in _live() if not x.get("is_headquarters") and x.get("status") != "archived"]
    by_spec: dict[str, list[dict]] = {}
    unmatched = []
    for x in live:
        spec = next((b for b in specs if b["code"] == x.get("code")), None) or next(
            (b for b in specs if _same_shop(x.get("address"), b)), None)
        if spec is None:
            unmatched.append(x)
        else:
            by_spec.setdefault(spec["code"], []).append(x)

    def _label(x):
        return f"#{x['id']} {x.get('code') or '—'} «{x.get('name')}» ({staff.get(x['id'], 0)} موظف)"

    extras: list[tuple[dict, str, dict | None]] = []
    spec_by_code = {b["code"]: b for b in specs}
    for code, members in by_spec.items():
        if len(members) > 1:
            # **يبقى الفرع الذي عليه الموظفون** لا صاحُب كود الملف: عليه سجلُّ
            # حضورهم ورواتبهم، وكوده داخٌل في أرقامهم الوظيفية (GUF-GUF6-00002)؛
            # وإبقاء الفارغ يعني نقل كل موظف بطلٍب ليبقى فرٌع بلا تاريخ.
            # وعند التساوي يبقى صاحب كود الملف.
            keep = max(members, key=lambda m: (staff.get(m["id"], 0), m.get("code") == code))
            for m in members:
                if m is not keep:
                    extras.append((m, f"مكرر لـ{code}", keep))
            if keep.get("code") != code:
                _complete_keeper(keep, spec_by_code[code], s, api, report, apply=apply,
                                 staffed=staff.get(keep["id"], 0))
    for x in unmatched:
        twin = next((b for b in specs if _branch_no(b["code"]) and
                     _branch_no(b["code"]) == _branch_no(x.get("code"))), None)
        keep = next((m for m in by_spec.get(twin["code"], [])), None) if twin else None
        why = (f"ليس في ملف الشركة — غالبًا المحلُّ نفسه {twin['code']} «{twin['name']}»"
               if twin else "ليس في ملف الشركة")
        extras.append((x, why, keep))
    for spec in specs:
        if spec["code"] not in by_spec:
            report["extras"].append(f"  ✗ ناقص على الموقع: {spec['code']} «{spec['name']}»"
                                    + ("" if apply else " — يُنشأ مع --apply"))

    for x, why, keep in extras:
        n = staff.get(x["id"], 0)
        line = f"  ⚠ {_label(x)} — {why}"
        if n:
            report["extras"].append(
                line + f"\n      عليه {n} موظف: انقلهم بطلب النقل"
                + (f" إلى {_label(keep)}" if keep else "") + " ثم أعد التشغيل")
            continue
        if delete_extras and apply:
            # حذٌف نهائي بطلب المالك؛ والخادم يرفض فرًعا يشير إليه أي سجلّ، فلا نُؤرشفه
            # بدلًا منه بصمت — يُقال ما عليه ويُترك لقراره.
            r = s.delete(api + f"/branches/{x['id']}",
                         params={"reason": f"مطابقة ملف الشركة 2026-09-23: {why}"})
            report["extras"].append(line + ("\n      → حُذف نهائيًا" if r.status_code < 400
                                            else f"\n      لم يُحذف: {r.status_code} {r.text[:200]}"))
        elif archive_extras and apply:
            r = s.post(api + f"/branches/{x['id']}/archive",
                       params={"reason": f"مطابقة ملف الشركة 2026-09-19: {why}"})
            report["extras"].append(line + ("\n      → أُرشف" if r.status_code < 400
                                            else f"\n      تعذّرت الأرشفة: {r.status_code} {r.text[:120]}"))
        else:
            report["extras"].append(line + ("\n      → يُحذف نهائيًا مع --apply --delete-extras"
                                            if delete_extras else
                                            "\n      → يُؤرشَف مع --apply --archive-extras"))


def main() -> None:
    p = argparse.ArgumentParser(description="إدخال حزمة مستندات شركة")
    p.add_argument("--data", required=True, help="ملف البيانات المراجَع (JSON)")
    p.add_argument("--source", help="مجلد حزمة المستندات (يلزم إن كان في الملف مستندات)")
    p.add_argument("--apply", action="store_true", help="يكتب فعًلا")
    p.add_argument("--api", help="عنوان الموقع المنشور — يمرّ كل شيء من واجهته")
    p.add_argument("--civil-id", help="الرقم المدني للدخول (مع --api)")
    p.add_argument("--delete-extras", action="store_true",
                   help="يحذف نهائيًا المكرر الفارغ (الإدارة العليا؛ يرفض ما عليه سجلّات)")
    p.add_argument("--archive-extras", action="store_true",
                   help="يؤرشف الفروع المكررة والخارجة عن ملف الشركة التي لا موظفين عليها")
    args = p.parse_args()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    # **ملفٌّ بلا مستندات لا يحتاج حزمة**: شركٌة تُدخَل بفروعها ومستنداتها
    # لم تُجمَع بعد — كان يُطلب مجلٌد وبياٌن فارغان ليمرّ.
    if data.get("documents") and not args.source:
        raise SystemExit("في الملف مستندات — مرِّر --source مجلد الحزمة.")
    source = Path(args.source) if args.source else Path(".")
    if data.get("documents") and not source.is_dir():
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
                         base=args.api, token=r.json()["access_token"],
                         archive_extras=args.archive_extras,
                         delete_extras=args.delete_extras)
    else:
        db = SessionLocal()
        try:
            report = run(data, source, apply=args.apply, db=db)
        finally:
            db.close()

    head = "نُفِّذ" if args.apply else "تقرير فقط — لم يُكتب شيء"
    print(f"=== {head} ===")
    for section, title in (("company", "الشركة"), ("branches", "الفروع"),
                           ("licenses", "التراخيص"),
                           ("extras", "فروعٌ تخالف ملف الشركة"),
                           ("documents", "المستندات")):
        if report.get(section):
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
