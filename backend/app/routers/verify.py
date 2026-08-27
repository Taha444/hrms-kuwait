# -*- coding: utf-8 -*-
"""تحقق عمومي من صحة مستند مطبوع عبر رمزه (P2-01) — بلا حساب/رمز دخول، لأن الغرض تحديًدا
تمكين طرف خارجي (بنك/سفارة) لا حساب له في النظام من التأكد من صحة الورقة التي بين يديه.
لا يُعاد أي بيانات حساسة (لا راتب، لا رقم مدني كامل) — فقط تأكيد الصحة والحد الأدنى للتعريف.
"""
import hashlib
import os

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..storage import delete_key, file_response, key_exists, read_bytes
from .. import models, verification
from ..database import get_db

router = APIRouter(prefix="/verify", tags=["verify"])


@router.get("/{code}")
def verify_document(code: str, db: Session = Depends(get_db)):
    doc_id = verification.parse_document_id(code)
    if doc_id is None:
        return {"valid": False}
    doc = db.get(models.RequestDocument, doc_id)
    if not doc or not verification.is_valid(code, doc.id, doc.request_id):
        return {"valid": False}
    req = db.get(models.Request, doc.request_id)
    if not req:
        return {"valid": False}
    rt = db.scalar(
        select(models.RequestType).where(models.RequestType.code == req.request_type_code)
    )
    company = db.get(models.Company, req.company_id)

    # V2.2 §30 (DOC-08) — البصمة تُحسب من الملف على القرص وتُقارن بالمحفوظة
    # وقت الإصدار. التمييز مقصود: "لم نُصدرها" غير "أُصدرت ثم عُدِّلت"، وهو
    # فرق جوهري لمن يحقّق في ورقة بين يديه.
    integrity = "UNKNOWN"
    if doc.checksum_sha256:
        if doc.file_path and key_exists(doc.file_path):
            # AWS-01 — يُقرأ من المخزن لا من القرص: البصمة تُحسب على
            # المحتوى الفعلي أينما كان، وهذا هو معنى التحقّق.
            actual = hashlib.sha256(read_bytes(doc.file_path)).hexdigest()
            integrity = "VALID" if actual == doc.checksum_sha256 else "TAMPERED"
        else:
            integrity = "FILE_MISSING"

    # V2.2 §30 (DOC-10) — الملغى يُعلن إلغاءه ولا يُخفى: مستند مُلغى معروف
    # الحال خيرٌ من مستند مختٍف لا يُعرف مصيره.
    revoked = doc.revoked_at is not None

    return {
        "valid": not revoked and integrity in ("VALID", "UNKNOWN"),
        "state": "REVOKED" if revoked else integrity,
        "request_type": rt.name if rt else req.request_type_code,
        "company_name": company.name if company else None,
        "issued_at": doc.created_at,
        "status": req.status,
        "reference_no": doc.reference_no,
        # DOC-20 — بأي نسخة قالب صدرت
        "template_version": doc.template_version,
        "revoked": revoked,
        # السبب عام لا تفصيلي: من يتحقّق يحتاج أن يعرف أنها مُلغاة لا لماذا
        "revocation_note": "أُلغي هذا المستند من جهة إصداره" if revoked else None,
    }
