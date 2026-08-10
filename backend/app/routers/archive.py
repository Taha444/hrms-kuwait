# -*- coding: utf-8 -*-
"""أرشيف الشركة والفرع: المستندات الرسمية (عقد التأسيس، السجل التجاري، رخص…)
مع أرشيف مستقل لكل فرع. الرفع/التنزيل عبر نقاط المستندات الموثّقة.

R8 §2 — مستندات مخصّصة (Dynamic Custom Documents):
عوض type ثابت واحد ("مستندات أخرى") يستبدل السابق، نستخدم prefix "custom:"
لكل مستند مخصّص بحيث يبقى كل واحد بصفّه المستقل، وله metadata كاملة
(name_ar, name_en, doc_number, issuing_authority, notes, notify_on_expiry).
"""
import json
import os
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..database import get_db
from ..deps import assert_same_company, audit, get_current_user, require_perm, scope_company_id
from ..safe_files import read_limited, unique_path

router = APIRouter(prefix="/archive", tags=["archive"])

# أنواع المستندات الرسمية للشركة
COMPANY_DOC_TYPES = [
    ("incorporation_contract", "عقد التأسيس"),
    ("commercial_reg", "السجل التجاري"),
    ("municipality_license", "رخصة البلدية"),
    ("fire_license", "رخصة المطافي"),
    ("company_license", "ترخيص الشركة"),
    ("manpower_file", "ملف القوى العاملة"),
    ("import_license", "رخصة الاستيراد"),
    ("signature_authorization", "تفويض التوقيع"),
    # ملاحظة: مستندات "أخرى" الديناميكية تُخزَّن بـtype يبدأ بـ"custom:" مع title مخصّص
    # حتى يظهر كل مستند كعنصر مستقل بدلاً من type ثابت واحد يستبدل السابق.
]
BRANCH_DOC_TYPES = [
    ("branch_license", "ترخيص الفرع"),
    ("branch_municipality", "رخصة بلدية الفرع"),
    ("branch_fire", "رخصة مطافي الفرع"),
    ("branch_lease", "عقد إيجار الفرع"),
    ("branch_import_license", "رخصة استيراد الفرع"),
]


def _docs_for(db: Session, entity_type: str, entity_id: int) -> list[dict]:
    """يُعيد كل المستندات الحالية (is_current=True) مع metadata كاملة.

    R8 §2 — للمستندات المخصّصة (type يبدأ بـ"custom:") نُعيد بيانات إضافية
    من extracted_data_json (name_en, doc_number, issuing_authority, notes,
    assigned_pro_id/name — R9).
    """
    rows = db.scalars(select(models.Document).where(
        models.Document.entity_type == entity_type,
        models.Document.entity_id == entity_id,
        models.Document.is_current == True,  # noqa: E712
    )).all()
    # cache للأسماء لتجنّب استعلام لكل مستند
    pro_id_to_name: dict[int, str] = {}
    out = []
    for d in rows:
        item = {
            "id": d.id, "type": d.document_type_code, "title": d.title,
            "expiry_date": d.expiry_date, "issue_date": d.issue_date,
            "version": d.version, "created_at": d.created_at,
            "notify_on_expiry": bool(d.notify_on_expiry),
            "is_custom": (d.document_type_code or "").startswith("custom:"),
        }
        # metadata مضافة للمستندات المخصّصة
        if item["is_custom"] and d.extracted_data_json:
            meta = d.extracted_data_json if isinstance(d.extracted_data_json, dict) else {}
            item["name_en"] = meta.get("name_en")
            item["doc_number"] = meta.get("doc_number")
            item["issuing_authority"] = meta.get("issuing_authority")
            item["notes"] = meta.get("notes")
            # R9 — PRO المسؤول عن متابعة تجديد المستند
            pro_id = meta.get("assigned_pro_id")
            if pro_id:
                item["assigned_pro_id"] = int(pro_id) if str(pro_id).isdigit() else None
                if item["assigned_pro_id"] and item["assigned_pro_id"] not in pro_id_to_name:
                    u = db.get(models.User, item["assigned_pro_id"])
                    pro_id_to_name[item["assigned_pro_id"]] = u.full_name if u else "—"
                item["assigned_pro_name"] = pro_id_to_name.get(item["assigned_pro_id"])
        out.append(item)
    return out


@router.get("/company")
def company_archive(company_id: int | None = None,
                    user: models.User = Depends(require_perm("view_documents")),
                    db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    if cid is None:
        raise HTTPException(status_code=400, detail="اختر شركة لعرض أرشيفها")
    company = db.get(models.Company, cid)
    if not company:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")
    return {
        "company": {"id": company.id, "name": company.name,
                    "commercial_reg": company.commercial_reg, "file_number": company.file_number,
                    "entity_type": company.entity_type},
        "doc_types": [{"code": c, "name": n} for c, n in COMPANY_DOC_TYPES],
        "documents": _docs_for(db, "company", company.id),
    }


@router.put("/company/info")
def update_company_info(file_number: str | None = None, company_id: int | None = None,
                        user: models.User = Depends(require_perm("manage_company")),
                        db: Session = Depends(get_db)):
    cid = scope_company_id(user, company_id)
    if cid is None:
        raise HTTPException(status_code=400, detail="اختر شركة")
    company = db.get(models.Company, cid)
    if not company:
        raise HTTPException(status_code=404, detail="الشركة غير موجودة")
    if file_number is not None:
        company.file_number = file_number
    audit(db, user, "update_company_archive", "company", company.id)
    db.commit()
    return {"ok": True, "file_number": company.file_number}


@router.get("/branch/{branch_id}")
def branch_archive(branch_id: int,
                   user: models.User = Depends(require_perm("view_documents")),
                   db: Session = Depends(get_db)):
    branch = db.get(models.Branch, branch_id)
    if not branch:
        raise HTTPException(status_code=404, detail="الفرع غير موجود")
    assert_same_company(user, branch.company_id, db=db)
    return {
        "branch": {"id": branch.id, "name": branch.name, "name_en": branch.name_en,
                   "code": branch.code, "address": branch.address},
        "doc_types": [{"code": c, "name": n} for c, n in BRANCH_DOC_TYPES],
        "documents": _docs_for(db, "branch", branch.id),
    }


# =============================================================================
# R8 §2 — Dynamic Custom Documents
# =============================================================================

@router.post("/custom-doc", status_code=201)
async def add_custom_document(
    request: Request,
    entity_type: str = Form(...),   # 'company' | 'branch'
    entity_id: int = Form(...),
    name_ar: str = Form(...),
    name_en: str | None = Form(None),
    doc_number: str | None = Form(None),
    issue_date: date | None = Form(None),
    expiry_date: date | None = Form(None),
    issuing_authority: str | None = Form(None),
    notes: str | None = Form(None),
    notify_on_expiry: bool = Form(False),
    assigned_pro_id: int | None = Form(None),
    file: UploadFile = File(...),
    user: models.User = Depends(require_perm("upload_documents")),
    db: Session = Depends(get_db),
):
    """R8 §2 — يضيف مستندًا مخصّصًا يظهر كعنصر مستقل بلا استبدال أي مستند آخر.

    - type يُخزَّن كـ"custom:{slug}" حيث slug مشتقّ من name_ar (يحتفظ بالفريدية)
    - metadata (name_en, doc_number, authority, notes, assigned_pro_id) في extracted_data_json
    - نفس النظام يعمل لشركة (entity_type='company') وفرع (entity_type='branch')
    - يحترم Scope: assert_same_company على الكيان المطلوب
    - assigned_pro_id (R9): PRO محدد لمتابعة تجديد المستند — يستقبل تنبيه الانتهاء
      بدل الـfallback على كل مندوبي الشركة.
    """
    if entity_type not in ("company", "branch"):
        raise HTTPException(status_code=400, detail="entity_type must be 'company' or 'branch'")
    if not name_ar.strip():
        raise HTTPException(status_code=400, detail="اسم المستند بالعربية مطلوب")

    # حدّد شركة الكيان للتحقق من النطاق
    if entity_type == "company":
        entity = db.get(models.Company, entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="الشركة غير موجودة")
        company_id = entity.id
    else:
        entity = db.get(models.Branch, entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="الفرع غير موجود")
        company_id = entity.company_id
    assert_same_company(user, company_id, db=db)

    # اكتب الملف على القرص
    folder = os.path.join(settings.upload_dir, "custom_docs", entity_type)
    fpath = unique_path(folder, file.filename, prefix=f"custom_{entity_id}_")
    with open(fpath, "wb") as f:
        f.write(await read_limited(file))

    # slug فريد للـtype (nameid داخلي — العرض بيستخدم title)
    import re
    slug = re.sub(r"[^\w؀-ۿ]+", "_", name_ar.strip())[:40]
    doc_type = f"custom:{slug}_{int(__import__('time').time())}"

    # تحقق من صحة assigned_pro_id: يجب أن ينتمي لنفس الشركة ودوره delegate
    if assigned_pro_id is not None:
        pro = db.get(models.User, assigned_pro_id)
        if not pro or pro.company_id != company_id or pro.role != "delegate":
            raise HTTPException(status_code=400,
                              detail="assigned_pro_id: يجب أن يكون مندوبًا (delegate) في نفس الشركة")

    meta = {
        "name_ar": name_ar.strip(),
        "name_en": (name_en or "").strip() or None,
        "doc_number": (doc_number or "").strip() or None,
        "issuing_authority": (issuing_authority or "").strip() or None,
        "notes": (notes or "").strip() or None,
        "assigned_pro_id": assigned_pro_id,
    }
    doc = models.Document(
        company_id=company_id,
        entity_type=entity_type, entity_id=entity_id,
        document_type_code=doc_type,
        title=name_ar.strip(),
        file_path=fpath,
        mime=file.content_type or "application/octet-stream",
        issue_date=issue_date,
        expiry_date=expiry_date,
        extracted_data_json=meta,
        version=1,
        is_current=True,
        uploaded_by=user.id,
        notify_on_expiry=notify_on_expiry,
    )
    db.add(doc)
    db.flush()
    audit(db, user, "add_custom_document", entity_type, entity_id,
          detail=f"custom doc: {name_ar}", request=request, company_id=company_id)
    db.commit()
    return {"ok": True, "id": doc.id, "type": doc_type, "title": doc.title}


@router.post("/custom-doc/{doc_id}/replace", status_code=200)
async def replace_custom_document(
    doc_id: int, request: Request,
    file: UploadFile = File(...),
    expiry_date: date | None = Form(None),
    notes: str | None = Form(None),
    user: models.User = Depends(require_perm("upload_documents")),
    db: Session = Depends(get_db),
):
    """R8 §2 — استبدال ملف مستند مخصّص مع الاحتفاظ بالنسخة القديمة History.
    القديم يُصبح is_current=False، الجديد يأخذ version+1 ويصبح Current."""
    old = db.get(models.Document, doc_id)
    if not old:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    if not (old.document_type_code or "").startswith("custom:"):
        raise HTTPException(status_code=400,
                          detail="هذا المسار للمستندات المخصّصة فقط — استخدم /documents/upload للثابتة")
    assert_same_company(user, old.company_id, db=db)

    # القديم → history
    old.is_current = False
    # P0-#10 — اقفل any open expiry tasks لهذا المستند القديم
    from .documents import _close_expiry_tasks_for
    _close_expiry_tasks_for(db, old.id)

    # اكتب الملف الجديد
    folder = os.path.join(settings.upload_dir, "custom_docs", old.entity_type)
    fpath = unique_path(folder, file.filename, prefix=f"custom_{old.entity_id}_v{old.version+1}_")
    with open(fpath, "wb") as f:
        f.write(await read_limited(file))

    meta = old.extracted_data_json if isinstance(old.extracted_data_json, dict) else {}
    if notes:
        meta = {**meta, "notes": notes.strip()}

    new_doc = models.Document(
        company_id=old.company_id,
        entity_type=old.entity_type, entity_id=old.entity_id,
        document_type_code=old.document_type_code,
        title=old.title,
        file_path=fpath,
        mime=file.content_type or "application/octet-stream",
        issue_date=old.issue_date,
        expiry_date=expiry_date or old.expiry_date,
        extracted_data_json=meta,
        version=old.version + 1,
        is_current=True,
        uploaded_by=user.id,
        notify_on_expiry=old.notify_on_expiry,
    )
    db.add(new_doc)
    db.flush()
    audit(db, user, "replace_custom_document", old.entity_type, old.entity_id,
          detail=f"v{old.version} → v{new_doc.version}: {old.title}",
          request=request, company_id=old.company_id)
    db.commit()
    return {"ok": True, "id": new_doc.id, "version": new_doc.version}


@router.get("/custom-doc/{doc_id}/history")
def custom_document_history(doc_id: int,
                            user: models.User = Depends(require_perm("view_documents")),
                            db: Session = Depends(get_db)):
    """R8 §2 — كل نسخ المستند المخصّص (Current + History)."""
    ref = db.get(models.Document, doc_id)
    if not ref:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    assert_same_company(user, ref.company_id, db=db)
    rows = db.scalars(select(models.Document).where(
        models.Document.entity_type == ref.entity_type,
        models.Document.entity_id == ref.entity_id,
        models.Document.document_type_code == ref.document_type_code,
    ).order_by(models.Document.version.desc())).all()
    return [{
        "id": d.id, "version": d.version, "is_current": d.is_current,
        "issue_date": d.issue_date, "expiry_date": d.expiry_date,
        "created_at": d.created_at, "uploaded_by": d.uploaded_by,
    } for d in rows]


# =============================================================================
# R9 §3 — Custom doc Edit metadata + Delete
# =============================================================================

@router.put("/custom-doc/{doc_id}")
async def update_custom_document(
    doc_id: int, request: Request,
    name_ar: str | None = Form(None),
    name_en: str | None = Form(None),
    doc_number: str | None = Form(None),
    issue_date: date | None = Form(None),
    expiry_date: date | None = Form(None),
    issuing_authority: str | None = Form(None),
    notes: str | None = Form(None),
    notify_on_expiry: bool | None = Form(None),
    assigned_pro_id: int | None = Form(None),
    clear_assigned_pro: bool = Form(False),
    user: models.User = Depends(require_perm("upload_documents")),
    db: Session = Depends(get_db),
):
    """R9 §3 — تعديل metadata لمستند مخصّص بدون تغيير الملف.
    الحقول المرسلة تُعدَّل فقط؛ ما لم يُرسل يبقى كما هو.
    لإزالة PRO المسند: أرسل clear_assigned_pro=true (بديل عن قيمة null).
    """
    doc = db.get(models.Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    if not (doc.document_type_code or "").startswith("custom:"):
        raise HTTPException(status_code=400,
                          detail="هذا المسار للمستندات المخصّصة فقط")
    assert_same_company(user, doc.company_id, db=db)

    meta = dict(doc.extracted_data_json) if isinstance(doc.extracted_data_json, dict) else {}
    changed = []
    if name_ar is not None and name_ar.strip():
        meta["name_ar"] = name_ar.strip()
        doc.title = name_ar.strip()
        changed.append("name_ar")
    if name_en is not None:
        meta["name_en"] = name_en.strip() or None
        changed.append("name_en")
    if doc_number is not None:
        meta["doc_number"] = doc_number.strip() or None
        changed.append("doc_number")
    if issuing_authority is not None:
        meta["issuing_authority"] = issuing_authority.strip() or None
        changed.append("issuing_authority")
    if notes is not None:
        meta["notes"] = notes.strip() or None
        changed.append("notes")
    if issue_date is not None:
        doc.issue_date = issue_date
        changed.append("issue_date")
    if expiry_date is not None:
        doc.expiry_date = expiry_date
        changed.append("expiry_date")
    if notify_on_expiry is not None:
        doc.notify_on_expiry = notify_on_expiry
        changed.append("notify_on_expiry")

    # PRO المسند: تحقق من الشركة والدور قبل الحفظ
    if clear_assigned_pro:
        meta["assigned_pro_id"] = None
        changed.append("assigned_pro_cleared")
    elif assigned_pro_id is not None:
        pro = db.get(models.User, assigned_pro_id)
        if not pro or pro.company_id != doc.company_id or pro.role != "delegate":
            raise HTTPException(status_code=400,
                              detail="assigned_pro_id: يجب أن يكون مندوبًا (delegate) في نفس الشركة")
        meta["assigned_pro_id"] = assigned_pro_id
        changed.append("assigned_pro_id")

    doc.extracted_data_json = meta
    audit(db, user, "update_custom_document", doc.entity_type, doc.entity_id,
          detail=f"{doc.title}: {', '.join(changed) or 'no-op'}",
          request=request, company_id=doc.company_id)
    db.commit()
    return {"ok": True, "id": doc.id, "changed": changed}


@router.delete("/custom-doc/{doc_id}")
def delete_custom_document(doc_id: int, request: Request,
                          user: models.User = Depends(require_perm("upload_documents")),
                          db: Session = Depends(get_db)):
    """R9 §3 — حذف نهائي لمستند مخصّص وكل نُسخه (Current + History).
    يمسح الملفات من القرص أيضًا للحفاظ على المساحة.
    """
    ref = db.get(models.Document, doc_id)
    if not ref:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    if not (ref.document_type_code or "").startswith("custom:"):
        raise HTTPException(status_code=400,
                          detail="هذا المسار للمستندات المخصّصة فقط")
    assert_same_company(user, ref.company_id, db=db)

    # كل النُسخ التي تشترك في نفس المعرّف (type + entity)
    versions = db.scalars(select(models.Document).where(
        models.Document.entity_type == ref.entity_type,
        models.Document.entity_id == ref.entity_id,
        models.Document.document_type_code == ref.document_type_code,
    )).all()
    deleted_count = 0
    from .documents import _close_expiry_tasks_for
    for v in versions:
        # P0-#10 — اقفل expiry tasks قبل الحذف
        _close_expiry_tasks_for(db, v.id)
        # امسح الملف الفعلي (لو موجود)
        if v.file_path and os.path.exists(v.file_path):
            try:
                os.remove(v.file_path)
            except OSError:
                pass  # نستمر حتى لو فشل مسح ملف واحد
        db.delete(v)
        deleted_count += 1

    audit(db, user, "delete_custom_document", ref.entity_type, ref.entity_id,
          detail=f"deleted {deleted_count} versions of: {ref.title}",
          request=request, company_id=ref.company_id)
    db.commit()
    return {"ok": True, "deleted_versions": deleted_count}
