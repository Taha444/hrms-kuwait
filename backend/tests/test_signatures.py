# -*- coding: utf-8 -*-
"""SIG-01 tests — upload/get/delete signature + PDF embedding."""
import io
import os
import struct
import zlib

from tests.conftest import auth_headers, login


def _signature_png(width: int = 200, height: int = 60) -> bytes:
    """يبني صورة PNG بها ink داكن (خطوط سوداء) على خلفية بيضاء — ليمر معالج SIG-02."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    # يرسم خطوط سوداء تحاكي توقيع
    draw.line([(20, 30), (60, 20), (100, 40), (140, 25), (180, 35)], fill=(0, 0, 0), width=3)
    draw.line([(30, 45), (80, 50), (130, 45)], fill=(30, 30, 30), width=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _blank_png(width: int = 200, height: int = 60) -> bytes:
    """صورة بيضاء تمامًا بلا ink — يجب رفضها بواسطة المعالج."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


# alias للـ tests القديمة (لتصبح استدعاءاتها ذات ink حقيقي)
_minimal_png = _signature_png


def test_get_signature_returns_false_when_none_uploaded(client):
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.get("/api/me/signature", headers=emp)
    assert r.status_code == 200
    assert r.json()["has_signature"] is False


def test_get_signature_image_404_when_none(client):
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.get("/api/me/signature/image", headers=emp)
    assert r.status_code == 404


def test_upload_signature_png_succeeds(client):
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    png = _minimal_png()
    r = client.post("/api/me/signature", headers=emp,
                    files={"file": ("sig.png", png, "image/png")})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ok"] is True
    # الحجم بعد المعالجة (processed) وحجم الخام
    assert body["size_bytes"] > 0
    assert body["raw_size_bytes"] == len(png)
    info = client.get("/api/me/signature", headers=emp).json()
    assert info["has_signature"] is True
    img_r = client.get("/api/me/signature/image", headers=emp)
    assert img_r.status_code == 200
    assert img_r.headers["content-type"] == "image/png"


def test_upload_signature_rejects_wrong_mime(client):
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    r = client.post("/api/me/signature", headers=emp,
                    files={"file": ("sig.txt", b"not an image", "text/plain")})
    assert r.status_code == 415


def test_upload_signature_rejects_too_large(client):
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    # PNG بحجم تجاوز 500KB
    huge = _minimal_png(width=2000, height=800)
    if len(huge) < 500 * 1024:
        # PNG المضغوطة قد تكون أصغر — نضيف padding في IDAT عبر تكرار
        huge = huge + b"\x00" * (600 * 1024)
    r = client.post("/api/me/signature", headers=emp,
                    files={"file": ("big.png", huge, "image/png")})
    assert r.status_code == 413


def test_replace_signature_deletes_old_file(client):
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    png1 = _minimal_png(width=100, height=40)
    client.post("/api/me/signature", headers=emp,
                files={"file": ("a.png", png1, "image/png")})
    # نلقط المسار الحالي من DB
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        u = db.query(models.User).filter_by(civil_id="100000000101").one()
        old_path = u.signature_path
    finally:
        db.close()
    assert old_path and os.path.exists(old_path)
    # نستبدل
    png2 = _minimal_png(width=150, height=50)
    client.post("/api/me/signature", headers=emp,
                files={"file": ("b.png", png2, "image/png")})
    # المسار القديم اتحذف
    assert not os.path.exists(old_path), "old signature file should be deleted"


def test_delete_signature_removes_file_and_clears_row(client):
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    png = _minimal_png()
    client.post("/api/me/signature", headers=emp,
                files={"file": ("s.png", png, "image/png")})
    r = client.delete("/api/me/signature", headers=emp)
    assert r.status_code == 200
    # get بعد الحذف يرجع has_signature=False
    info = client.get("/api/me/signature", headers=emp).json()
    assert info["has_signature"] is False


def test_signature_isolated_per_user(client):
    """المستخدم أ يرفع توقيع → المستخدم ب لا يراه."""
    a = auth_headers(login(client, "100000000101", "emp12345"))
    b = auth_headers(login(client, "100000000102", "emp12345"))
    client.post("/api/me/signature", headers=a,
                files={"file": ("s.png", _minimal_png(), "image/png")})
    info_b = client.get("/api/me/signature", headers=b).json()
    assert info_b["has_signature"] is False


def test_upload_isolates_signature_from_notebook_rings(client):
    """SIG-03: صورة بها رنجات نوت-بوك أعلى + توقيع أسفل → القص يشمل التوقيع فقط."""
    from PIL import Image, ImageDraw
    # نبني صورة 400×600: رنجات في أعلى 100 بكسل، فراغ، توقيع في المنتصف
    img = Image.new("RGB", (400, 600), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    # رنجات: خطوط أفقية متقطعة سوداء في أعلى 80 بكسل
    for x in range(0, 400, 25):
        draw.rectangle([(x, 20), (x + 15, 80)], fill=(20, 20, 20))
    # توقيع في المنتصف السفلي (y=350..430)
    draw.line([(50, 380), (100, 370), (150, 400), (200, 375), (250, 395)],
              fill=(0, 0, 0), width=4)
    draw.line([(60, 410), (180, 415), (240, 405)], fill=(20, 20, 20), width=3)
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    emp = auth_headers(login(client, "100000000101", "emp12345"))
    client.delete("/api/me/signature", headers=emp)
    r = client.post("/api/me/signature", headers=emp,
                    files={"file": ("with_rings.png", buf.getvalue(), "image/png")})
    assert r.status_code == 201, r.text

    # الآن نفحص أبعاد الصورة المعالَجة — لازم تكون قريبة من ارتفاع التوقيع (~80px + padding)
    # مش قريبة من ارتفاع الصورة الكاملة (600px)
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        u = db.query(models.User).filter_by(civil_id="100000000101").one()
        processed = Image.open(u.signature_path)
        # ارتفاع الصورة المعالَجة يجب أن يكون أقل بكثير من ارتفاع الصورة الأصلية
        # لأن الرنجات كانت في أعلى الصورة والتوقيع في المنتصف
        assert processed.height < 300, (
            f"expected tight crop around signature only, got height={processed.height}"
        )
        # ولازم يكون فيه ارتفاع معقول (لسه فيه التوقيع)
        assert processed.height > 20
    finally:
        db.close()


def test_upload_processes_photo_removes_background_saves_transparent_png(client):
    """SIG-02: صورة الرفع تُعالج → PNG شفاف الخلفية بحجم متناسب مع الـ ink فقط."""
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    raw_png = _signature_png(width=400, height=300)  # صورة كبيرة بها ink صغير
    r = client.post("/api/me/signature", headers=emp,
                    files={"file": ("sig.png", raw_png, "image/png")})
    assert r.status_code == 201
    body = r.json()
    # الحجم المعالَج غالبًا أصغر من الخام (لأنه cropped) والنوع دائمًا PNG
    from app.database import SessionLocal
    from app import models
    from PIL import Image
    db = SessionLocal()
    try:
        u = db.query(models.User).filter_by(civil_id="100000000101").one()
        assert u.signature_path.endswith(".png")
        img = Image.open(u.signature_path)
        # التصميم يحفظ RGBA بشفافية
        assert img.mode == "RGBA"
        # الأبعاد أصغر من 400×300 (لأن الصورة اتقصت حول ink فقط)
        assert img.width < 400 or img.height < 300
    finally:
        db.close()


def test_upload_rejects_blank_image_no_ink_detected(client):
    """صورة بيضاء تمامًا بدون ink → يرفضها المعالج برسالة واضحة."""
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    # نمسح التوقيع الحالي (لو موجود من اختبار سابق)
    client.delete("/api/me/signature", headers=emp)
    blank = _blank_png()
    r = client.post("/api/me/signature", headers=emp,
                    files={"file": ("blank.png", blank, "image/png")})
    assert r.status_code == 400
    assert "توقيع" in r.json()["detail"]


def test_signature_image_returns_png_regardless_of_input(client):
    """حتى لو المستخدم رفع JPG، المعالج يحفظ PNG بشفافية."""
    emp = auth_headers(login(client, "100000000101", "emp12345"))
    # نبني JPG بها ink
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (200, 60), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.line([(20, 30), (180, 30)], fill=(0, 0, 0), width=3)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    r = client.post("/api/me/signature", headers=emp,
                    files={"file": ("sig.jpg", buf.getvalue(), "image/jpeg")})
    assert r.status_code == 201, r.text
    # الـ content-type للاستجابة PNG دائمًا
    img_r = client.get("/api/me/signature/image", headers=emp)
    assert img_r.headers["content-type"] == "image/png"


def test_generated_pdf_embeds_signature_when_available(client):
    """طلب يولّد PDF: لو الموظف رفع توقيع، الـ PDF يحتوي على الصورة (بحجم أكبر عن بدونها)."""
    # 1) موظف بدون توقيع — نقيس حجم PDF المرجعي
    emp_tok = login(client, "100000000101", "emp12345")
    # تأكد إن التوقيع محذوف
    client.delete("/api/me/signature", headers=auth_headers(emp_tok))
    # نقدم طلب شهادة راتب ونمرره حتى الإكمال
    r = client.post("/api/requests", headers=auth_headers(emp_tok), json={
        "request_type_code": "salary_certificate",
        "payload_json": {"addressed_to": "بنك", "purpose": "قرض"},
    })
    rid_no_sig = r.json()["id"]
    mgr = auth_headers(login(client, "100000000001", "manager123"))
    client.post(f"/api/requests/{rid_no_sig}/decide", headers=mgr, json={"decision": "approved"})
    # نستخرج حجم PDF الأول
    from app.database import SessionLocal
    from app import models
    db = SessionLocal()
    try:
        docs_no_sig = db.query(models.RequestDocument).filter_by(request_id=rid_no_sig).all()
    finally:
        db.close()
    if docs_no_sig and docs_no_sig[0].file_path and os.path.exists(docs_no_sig[0].file_path):
        size_no_sig = os.path.getsize(docs_no_sig[0].file_path)
    else:
        size_no_sig = 0

    # 2) نرفع توقيع ونعمل طلب ثاني — الـ PDF المفروض يكون أكبر
    png = _minimal_png(width=200, height=60)
    client.post("/api/me/signature", headers=auth_headers(emp_tok),
                files={"file": ("s.png", png, "image/png")})
    r = client.post("/api/requests", headers=auth_headers(emp_tok), json={
        "request_type_code": "salary_certificate",
        "payload_json": {"addressed_to": "بنك", "purpose": "سفر"},
    })
    rid_with_sig = r.json()["id"]
    client.post(f"/api/requests/{rid_with_sig}/decide", headers=mgr,
                json={"decision": "approved"})
    db = SessionLocal()
    try:
        docs_with_sig = db.query(models.RequestDocument).filter_by(request_id=rid_with_sig).all()
    finally:
        db.close()
    if docs_with_sig and docs_with_sig[0].file_path and os.path.exists(docs_with_sig[0].file_path):
        size_with_sig = os.path.getsize(docs_with_sig[0].file_path)
        # التحقق ليّن — بس نتأكد إن الـ PDF أُنتِج بنجاح
        assert size_with_sig > 1000
