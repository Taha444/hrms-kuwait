# -*- coding: utf-8 -*-
"""تحقق عمومي من صحة مستند مطبوع عبر رمزه (P2-01) — بلا حساب/رمز دخول، لأن الغرض تحديًدا
تمكين طرف خارجي (بنك/سفارة) لا حساب له في النظام من التأكد من صحة الورقة التي بين يديه.
لا يُعاد أي بيانات حساسة (لا راتب، لا رقم مدني كامل) — فقط تأكيد الصحة والحد الأدنى للتعريف.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

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
    return {
        "valid": True,
        "request_type": rt.name if rt else req.request_type_code,
        "company_name": company.name if company else None,
        "issued_at": doc.created_at,
        "status": req.status,
    }
