# -*- coding: utf-8 -*-
"""تحقق عمومي من صحة مستند مطبوع عبر رمزه (P2-01) — بلا حساب/رمز دخول، لأن الغرض تحديًدا
تمكين طرف خارجي (بنك/سفارة) لا حساب له في النظام من التأكد من صحة الورقة التي بين يديه.
لا يُعاد أي بيانات حساسة (لا راتب، لا رقم مدني كامل) — فقط تأكيد الصحة والحد الأدنى للتعريف.
"""
import hashlib
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..storage import delete_key, file_response, key_exists, read_bytes
from .. import models, verification
from ..database import get_db

router = APIRouter(prefix="/verify", tags=["verify"])


#: صفحٌة يقرؤها الإنسان — **ومن يمسح الرمز ليس برنامًجا.**
#:
#: المسار كان يعيد JSON وحده، ولا شاشَة تحقٍّق في الواجهة. فالبنك الذي
#: يمسح الرمز يرى نًصّا خاًما بمفاتيح إنجليزية — ويقرأ ``valid`` ويمضي،
#: ولا يرى ``state`` الذي يميّز «مطابقة» من «تعذّر الفحص».
#:
#: والصفحة لا تكشف أكثر ممّا يكشفه الردّ: هي عرٌض له لا بابٌ ثاٍن.
_PAGE = """<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>التحقّق من مستند</title>
<style>
 body{{font:16px/1.7 system-ui,'Segoe UI',sans-serif;margin:0;padding:24px;
      background:#f6f7f9;color:#111}}
 .card{{max-width:34rem;margin:6vh auto;background:#fff;border-radius:14px;
        padding:28px;box-shadow:0 1px 3px rgba(0,0,0,.12)}}
 .badge{{display:inline-block;padding:6px 14px;border-radius:999px;
         font-weight:700;font-size:15px}}
 .ok{{background:#e7f6ec;color:#11633a}} .no{{background:#fdeaea;color:#8c1c1c}}
 .warn{{background:#fff6e5;color:#8a5a00}}
 dl{{display:grid;grid-template-columns:auto 1fr;gap:8px 16px;margin:22px 0 0}}
 dt{{color:#667;font-size:14px}} dd{{margin:0;font-weight:600}}
 .note{{margin-top:18px;color:#667;font-size:14px}}
</style>
<div class="card">
  <span class="badge {cls}">{headline}</span>
  <dl>{rows}</dl>
  <p class="note">{note}</p>
</div></html>"""

_STATE_AR = {
    "VALID": "بصمُة الملف مطابقة لما صدر",
    "TAMPERED": "بصمُة الملف لا تطابق ما صدر — عُدِّل بعد إصداره",
    "FILE_MISSING": "الملف غير موجود في التخزين — لا يمكن فحص بصمته",
    "UNKNOWN": "لا بصمَة محفوظة لهذا المستند — تعذّر فحص سلامته",
    "REVOKED": "أُلغي هذا المستند من جهة إصداره",
}


def _wants_html(request) -> bool:
    """أيطلب المتصفُّح صفحًة؟ — ومن يمسح الرمز يفتحه بمتصفّح."""
    return "text/html" in (request.headers.get("accept") or "")


def _as_page(data: dict) -> str:
    state = data.get("state") or "UNKNOWN"
    if data.get("revoked"):
        cls, headline = "no", "مستٌند ملغى"
    elif data.get("valid") and state == "VALID":
        cls, headline = "ok", "مستٌند صحيح"
    elif data.get("valid"):
        # **«صحيح» بلا فحٍص ليست «صحيح»** — تُعرَض بلونها لا بلون اليقين.
        cls, headline = "warn", "صادٌر عنّا — وتعذّر فحص سلامته"
    else:
        cls, headline = "no", "مستٌند غير صحيح"

    fields = [("نوع المستند", data.get("request_type")),
              ("الجهة المُصدِرة", data.get("company_name")),
              ("الرقم المرجعي", data.get("reference_no")),
              ("تاريخ الإصدار", str(data.get("issued_at") or "")[:19].replace("T", " "))]
    rows = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in fields if v)
    return _PAGE.format(cls=cls, headline=headline, rows=rows,
                        note=_STATE_AR.get(state, state).replace("**", ""))


@router.get("/{code}")
def verify_document(code: str, request: Request, db: Session = Depends(get_db)):
    def _out(data: dict):
        if _wants_html(request):
            return HTMLResponse(_as_page(data))
        return data

    doc_id = verification.parse_document_id(code)
    if doc_id is None:
        return _out({"valid": False})
    doc = db.get(models.RequestDocument, doc_id)
    if not doc or not verification.is_valid(code, doc.id, doc.request_id):
        return _out({"valid": False})
    req = db.get(models.Request, doc.request_id)
    if not req:
        return _out({"valid": False})
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

    return _out({
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
    })
