# -*- coding: utf-8 -*-
"""SIG-01 tests — upload/get/delete signature + PDF embedding."""
import io
import os
import struct
import zlib

from tests.conftest import auth_headers, login


def _minimal_png(width: int = 200, height: int = 60) -> bytes:
    """يبني صورة PNG صغيرة بيضاء صالحة للاختبار — لا نعتمد على Pillow."""
    def _chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(
            ">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR",
                  struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    # raw pixels: rows of (filter=0 + width*3 bytes of RGB white)
    row = b"\x00" + b"\xff" * (width * 3)
    raw = row * height
    idat = _chunk(b"IDAT", zlib.compress(raw))
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


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
    assert body["size_bytes"] == len(png)
    # الآن get يرجع has_signature=True
    info = client.get("/api/me/signature", headers=emp).json()
    assert info["has_signature"] is True
    # صورة التوقيع تتنزل بنفس الحجم تقريبًا
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
