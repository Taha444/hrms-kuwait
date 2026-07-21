# -*- coding: utf-8 -*-
"""SIG-01 — إدارة التوقيع الرقمي للمستخدم.

كل مستخدم (خاصة الموظفين) يرفع صورة توقيعه (PNG/JPG) عبر بروفايله. يخزّنها النظام
داخل uploads/signatures/ ويحقنها في كل PDF رسمي منسوب إليه (شهادات، إنذارات،
إخلاء طرف...). الموظف يقدر يستبدل توقيعه في أي وقت — النسخة الجديدة تُستخدم
لأي مستند يُولَّد بعدها، بينما المستندات القديمة تحتفظ بالتوقيع الأصلي كما هو.

الحدود الأمنية:
- المستخدم يرفع/يعرض/يحذف توقيع نفسه فقط (لا يمس توقيع مستخدم آخر)
- HR/super_admin يستطيعون العرض للتحقق، لكن ليس الاستبدال
- حجم أقصى 500KB، امتدادات: png/jpg/jpeg فقط
- الملف يُخزّن باسم عشوائي غير قابل للتخمين، ولا يُكشف مساره في الاستجابة
"""
import io
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from .. import models
from ..config import settings
from ..database import get_db
from ..deps import audit, get_current_user
from ..safe_files import read_limited, unique_path
from sqlalchemy.orm import Session

router = APIRouter(prefix="/me/signature", tags=["signature"])

_ALLOWED_MIME = {"image/png", "image/jpeg", "image/jpg"}
_ALLOWED_EXT = {".png", ".jpg", ".jpeg"}
_MAX_BYTES = 500 * 1024  # 500 KB — كافٍ لصورة توقيع بجودة عالية


def _signatures_folder() -> str:
    return os.path.join(settings.upload_dir, "signatures")


def _find_signature_bbox(alpha):
    """SIG-03: يعزل التوقيع عن ضوضاء الخلفية (رنجات نوت-بوك، ثقوب، نص جانبي).

    الفكرة: التوقيع الحقيقي يشكّل "شريط ink كثيف" مستمر رأسيًا، بينما الرنجات
    والثقوب تشكّل أشرطة منفصلة. نقسّم الصورة إلى أشرطة أفقية بحسب صفوف الحبر،
    ونختار الشريط الأكثر كثافة (أعلى total ink) — لأنه الأرجح أنه التوقيع.
    ثم نعمل نفس التحليل عموديًا داخل ذلك الشريط لإيجاد يمين/يسار التوقيع بالضبط.

    القياسات تعتمد على PIL.Image.reduce (C-implemented) → سريعة حتى لصور 4K.
    """
    w, h = alpha.size
    if w == 0 or h == 0:
        return None

    # 1. متوسط الحبر لكل صف: نقلّص عرض الصورة إلى 1 → صورة 1×h بها متوسط ألفا لكل صف
    row_col = alpha.reduce((max(w, 1), 1))  # حجم الخرج: (1, h)
    row_avgs = list(row_col.getdata())

    # 2. شريط = صفوف متتالية بها ink؛ نسمح بفجوات صغيرة داخل التوقيع نفسه
    MIN_ROW = 4  # صف بمتوسط < 4/255 يعتبر فارغًا
    GAP = max(6, h // 25)  # فجوة أكبر من هذا تفصل بين شريطين مختلفين

    bands: list[tuple[int, int, int]] = []  # (start_y, end_y, total_ink)
    start = None
    ink_sum = 0
    gap_count = 0
    for y, v in enumerate(row_avgs):
        if v > MIN_ROW:
            if start is None:
                start = y
            ink_sum += v
            gap_count = 0
        else:
            if start is not None:
                gap_count += 1
                if gap_count >= GAP:
                    bands.append((start, y - gap_count, ink_sum))
                    start = None
                    ink_sum = 0
                    gap_count = 0
    if start is not None:
        bands.append((start, h - 1, ink_sum))

    if not bands:
        return None

    # 3. الشريط الأكثر total ink = التوقيع. لو فيه شريط أكبر بكثير من الباقي
    # (مثل الرنجات لو كانت كثيفة) لكن قصير جدًا رأسيًا، نتجاهله لصالح شريط
    # أطول رأسيًا. نستخدم مقياس مركّب: total_ink مضروب في ارتفاع الشريط.
    def score(b):
        top, bot, total = b
        height = bot - top + 1
        # نفضّل الأشرطة الأطول (توقيع فعلي) على الأشرطة القصيرة العالية الكثافة (رنجات)
        return total * (height ** 0.5)

    band_top, band_bottom, _ = max(bands, key=score)

    # 4. داخل الشريط، نجد أقصى يمين وأقصى يسار عبر تحليل عمودي
    strip = alpha.crop((0, band_top, w, band_bottom + 1))
    strip_h = max(strip.height, 1)
    col_row = strip.reduce((1, strip_h))  # حجم الخرج: (w, 1)
    col_avgs = list(col_row.getdata())

    left = None
    right = 0
    for x, v in enumerate(col_avgs):
        if v > MIN_ROW:
            if left is None:
                left = x
            right = x
    if left is None:
        return None
    return (left, band_top, right + 1, band_bottom + 1)


def _process_signature(input_bytes: bytes) -> bytes:
    """يستخرج التوقيع من صورة ورقة/شاشة ويحوّله لـ PNG أسود شفاف الخلفية.

    الخطوات:
    1. Auto-rotate حسب EXIF (في حالة صور الموبايل)
    2. تحويل لـ grayscale
    3. Auto-contrast لتوحيد الإضاءة (نور شمس vs نور غرفة)
    4. Threshold تدريجي (0..THRESHOLD → alpha 255..0) لحفظ حواف ناعمة للـ ink
    5. RGBA بـ ink أسود + alpha channel + خلفية شفافة
    6. SIG-03: قص ذكي يعزل التوقيع عن رنجات النوت-بوك والثقوب والحدود
    """
    from PIL import Image, ImageOps
    img = Image.open(io.BytesIO(input_bytes))
    img = ImageOps.exif_transpose(img)  # يحترم توجيه صور الموبايل
    gray = img.convert("L")
    gray = ImageOps.autocontrast(gray, cutoff=2)  # يوحّد الإضاءة بين صور مختلفة

    THRESHOLD = 140  # بيكسل أغمق من ده = ink
    # Lookup table للـ alpha: كلما زاد الغمق (v أقل) زادت الشفافية
    lut = bytes(
        max(0, min(255, int((THRESHOLD - v) * 255 / THRESHOLD))) if v < THRESHOLD else 0
        for v in range(256)
    )
    alpha = gray.point(lut)

    # RGBA: كل البيكسلات سوداء، والـ alpha بيحدد وين يظهر ink
    black = Image.new("L", gray.size, 0)
    out = Image.merge("RGBA", (black, black, black, alpha))

    # SIG-03: نستخدم "شريط ink الأكثر كثافة" بدل bounding box الكامل — يشيل الرنجات
    # والثقوب اللي كانت تظهر فوق التوقيع في الـ PDF. لو تعذّر (مثلاً صورة نظيفة
    # بشريط واحد فقط) نرجع للـ bbox العادي كـ fallback.
    smart_bbox = _find_signature_bbox(alpha)
    if smart_bbox is None:
        smart_bbox = alpha.getbbox()
    if smart_bbox is None:
        raise HTTPException(status_code=400,
                            detail="لم يتم اكتشاف توقيع في الصورة — استخدم قلم أغمق أو صورة أوضح")

    left, top, right, bottom = smart_bbox
    pad = 12  # padding أقل بعد التحسن في الدقة
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(alpha.width, right + pad)
    bottom = min(alpha.height, bottom + pad)
    out = out.crop((left, top, right, bottom))

    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@router.get("")
def get_my_signature_info(user: models.User = Depends(get_current_user)):
    """يعرض بيانات التوقيع الحالي (بدون الصورة نفسها) — تُنزَّل عبر /image."""
    return {
        "has_signature": bool(user.signature_path and os.path.exists(user.signature_path)),
        "updated_at": user.signature_updated_at,
    }


@router.get("/image")
def get_my_signature_image(user: models.User = Depends(get_current_user)):
    """ينزّل صورة التوقيع الحالية للمستخدم — للعرض في بروفايله كمعاينة."""
    if not user.signature_path or not os.path.exists(user.signature_path):
        raise HTTPException(status_code=404, detail="لا يوجد توقيع محفوظ")
    # المعالجة تحفظ دائمًا PNG (لدعم الشفافية)
    return FileResponse(user.signature_path, media_type="image/png")


@router.post("", status_code=201)
async def upload_my_signature(request: Request, file: UploadFile = File(...),
                              user: models.User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    """يرفع أو يستبدل توقيع المستخدم — يمر بمعالجة "سكان" تلقائيًا:
    - يستخرج ink من صورة الورقة
    - يحوّل اللون لأسود موحّد
    - يشيل خلفية الورقة والحواف
    - يحفظ كـ PNG شفاف الخلفية
    القبول: PNG/JPG ≤500KB. الإخراج دائمًا PNG بغض النظر عن الإدخال."""
    if file.content_type not in _ALLOWED_MIME:
        raise HTTPException(status_code=415, detail="نوع الملف يجب أن يكون PNG أو JPG فقط")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status_code=415, detail="امتداد الملف يجب أن يكون .png أو .jpg")
    data = await read_limited(file, max_bytes=_MAX_BYTES)
    if not data:
        raise HTTPException(status_code=400, detail="الملف فارغ")

    # معالجة الصورة: استخراج ink + شفافية + قص للحدود
    try:
        processed = _process_signature(data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400,
                            detail=f"تعذّرت معالجة الصورة: {exc}")

    folder = _signatures_folder()
    # النتيجة دائمًا PNG (بغض النظر عن الإدخال) لدعم الشفافية
    path = unique_path(folder, f"user_{user.id}.png", prefix=f"sig_u{user.id}_")
    with open(path, "wb") as f:
        f.write(processed)

    # حذف التوقيع القديم (لو موجود) — نحتفظ بالجديد فقط لتقليل تراكم الملفات
    old = user.signature_path
    user.signature_path = path
    user.signature_updated_at = datetime.now(timezone.utc)
    audit(db, user, "signature_upload", "user", user.id,
          detail=f"raw={len(data)}B processed={len(processed)}B", request=request)
    db.commit()
    if old and os.path.exists(old) and old != path:
        try:
            os.remove(old)
        except OSError:
            pass  # ملف قديم فُقد — لا يوقف العملية
    return {"ok": True, "updated_at": user.signature_updated_at,
            "size_bytes": len(processed),
            "raw_size_bytes": len(data)}


@router.delete("")
def delete_my_signature(request: Request,
                        user: models.User = Depends(get_current_user),
                        db: Session = Depends(get_db)):
    """يحذف التوقيع الحالي — المستندات المستقبلية تعود لسطر توقيع فارغ."""
    if not user.signature_path:
        raise HTTPException(status_code=404, detail="لا يوجد توقيع محفوظ")
    old = user.signature_path
    user.signature_path = None
    user.signature_updated_at = datetime.now(timezone.utc)
    audit(db, user, "signature_delete", "user", user.id, request=request)
    db.commit()
    if old and os.path.exists(old):
        try:
            os.remove(old)
        except OSError:
            pass
    return {"ok": True}
