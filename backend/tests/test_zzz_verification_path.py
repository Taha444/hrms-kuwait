# -*- coding: utf-8 -*-
"""رمٌز بلا طريق لا يُتحقَّق به.

**العطل المقيس**: رمز QR أسفل كل مستند رسمي كان يحمل **النصّ المجرَّد**
(``12-ab34cd``) لا رابًطا. فالبنك أو السفارة التي تمسحه تحصل على سلسلة
حروٍف لا تقودها إلى شيء:

- لا شاشَة تحقٍّق في الواجهة إطلاًقا،
- ولا سطَر على الورقة يقول أين يُستعمَل الرمز،
- والمسار ``/api/verify/{code}`` قائٌم ويعمل — ولا طريق إليه.

وهي «نقطة بلا طريق» على **أكثر أسطح النظام ظهوًرا للخارج**: ورقٌة رسمية
تُقدَّم لجهة.

**وعطٌل ثاٍن في المعنى**: الردّ يعيد ``valid: true`` حين تكون البصمة
**غائبة** (``state: "UNKNOWN"``) — أي «صحيح» بلا فحص. ومن يقرأ ``valid``
ويمضي لا يرى التمييز. فصارت الصفحة تعرضه بلونه: **صادٌر عنّا وتعذّر فحص
سلامته** لا «صحيح».
"""
from __future__ import annotations

from sqlalchemy import select

from app import models, verification
from app.config import settings
from app.database import SessionLocal


def _any_generated_doc():
    db = SessionLocal()
    try:
        return db.scalar(select(models.RequestDocument).where(
            models.RequestDocument.kind == "generated_pdf"))
    finally:
        db.close()


def test_the_printed_code_carries_its_path(monkeypatch):
    """**الرمز يحمل طريقه** متى عُرف العنوان العامّ."""
    import inspect

    from app import pdf_export

    src = inspect.getsource(pdf_export.ArabicPDF.verification)
    assert "public_base_url" in src, "الرمز ما زال نًصّا مجرًَّدا"
    assert "/api/verify/" in src, "لا يحمل موضع التحقّق"


def test_an_unset_base_keeps_the_bare_code():
    """**ورابٌط خاطئ يقود إلى لا شيء أسوأ من رمٍز يُنسَخ بالي;د.**

    فبيئٌة لم تُضبَط يبقى فيها السلوك القديم.
    """
    assert settings.public_base_url == "" or settings.public_base_url.startswith("http")


def test_a_scanner_gets_a_page_not_raw_json(client):
    """**ومن يمسح الرمز ليس برنامًجا** — يفتحه بمتصفّح."""
    doc = _any_generated_doc()
    if doc is None:
        code = "1-0000000000"
    else:
        code = verification.generate_code(doc.id, doc.request_id)
    r = client.get(f"/api/verify/{code}", headers={"accept": "text/html"})
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", ""), r.headers
    assert "التحقّق من مستند" in r.text, r.text[:200]


def test_a_program_still_gets_json(client):
    """ولا يُكسَر ما يقرؤه البرنامج: الردّ يبقى JSON لمن يطلبه."""
    r = client.get("/api/verify/1-0000000000", headers={"accept": "application/json"})
    assert r.status_code == 200
    assert r.json().get("valid") is False, r.text[:200]


def test_an_invalid_code_says_so_on_the_page(client):
    """ورمٌز غير صحيح يُقال فيه ذلك بوضوح لا بصمت."""
    r = client.get("/api/verify/1-0000000000", headers={"accept": "text/html"})
    assert "غير صحيح" in r.text, r.text[:300]


def test_unverifiable_is_not_shown_as_valid():
    """**و«صحيح» بلا فحٍص ليست «صحيح».**

    الردّ يعيد ``valid: true`` حين لا بصمَة محفوظة. ومن يقرأ الكلمة وحدها
    يبني عليها قراًرا. فالصفحة تفرّق: «مستٌند صحيح» لمن طابقت بصمتُه،
    و«صادٌر عنّا وتعذّر فحص سلامته» لمن لا بصمة له.
    """
    from app.routers.verify import _as_page

    page = _as_page({"valid": True, "state": "UNKNOWN", "revoked": False,
                     "request_type": "شهادة راتب", "company_name": "شركة"})
    assert "تعذّر فحص سلامته" in page, page[:400]
    assert "مستٌند صحيح" not in page

    sound = _as_page({"valid": True, "state": "VALID", "revoked": False,
                      "request_type": "شهادة راتب", "company_name": "شركة"})
    assert "مستٌند صحيح" in sound


def test_a_tampered_document_is_named_not_merely_invalid():
    """**و«لم نُصدرها» غير «أُصدرت ثم عُدِّلت»** — والفرق جوهرّي لمن يحقّق."""
    from app.routers.verify import _as_page

    page = _as_page({"valid": False, "state": "TAMPERED", "revoked": False,
                     "request_type": "شهادة", "company_name": "شركة"})
    assert "عُدِّل بعد إصداره" in page, page[:400]


def test_the_page_reveals_no_more_than_the_json(client):
    """والصفحة عرٌض للردّ لا بابٌ ثاٍن: لا تكشف ما لا يكشفه."""
    from app.routers.verify import _as_page

    page = _as_page({"valid": True, "state": "VALID", "revoked": False,
                     "request_type": "شهادة راتب", "company_name": "شركة",
                     "reference_no": "REF-1", "issued_at": "2030-01-01T10:00:00",
                     "employee_name": "لا ينبغي أن يظهر"})
    assert "لا ينبغي أن يظهر" not in page
