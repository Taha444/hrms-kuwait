# -*- coding: utf-8 -*-
"""حارس بيئة التشغيل — كل صورة تشغّل الخادم تحمل ما يحتاجه.

**العطل الذي أنتج هذا الحارس**: في المستودع ملفّا Dockerfile — واحد في
الجذر تبنيه المنصّة، وآخر في ``backend/`` يستعمله docker-compose محليًّا.
أُضيفت حزم العقد الحكومي إلى الثاني وحده، فمرّ النشر ولم يتغيّر شيء على
الإنتاج: ``/api/health/deep`` بقي يقول ``libreoffice: null``.

ولم يظهر العطل في أي اختبار لأن الاختبارات لا تبني صورة. وكشفه فحص
الجاهزية الذي بُني للغرض نفسه — لكنه كشفه **بعد** النشر.

والقاعدة هنا: ملفّان يصفان بيئة واحدة ينحرفان. فيُربطان بفحص واحد يقرأ
الاثنين، لا بذاكرة من يعدّل.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

#: الحزم التي يحتاجها الخادم وقت التشغيل، وسببُ كلٍّ منها.
REQUIRED_PACKAGES = {
    "tesseract-ocr": "قراءة MRZ للجواز والبطاقة المدنية",
    "tesseract-ocr-ara": "العربية في OCR",
    "libreoffice-writer": "تحويل نموذج الهيئة إلى PDF بتخطيطه الرسمي",
}

#: خطوط عربية — وجود واحدة يكفي. بدونها يخرج العقد بمربّعات فارغة
#: والتوليد يبدو ناجًحا.
ARABIC_FONT_PACKAGES = ("fonts-noto-core", "fonts-noto", "fonts-amiri",
                        "fonts-kacst", "fonts-hosny-amiri")



def _instructions(path: Path) -> str:
    """محتوى الملف بلا تعليقات.

    الفحص على النصّ الكامل كان يقبل ذكر الحزمة **في تعليق** يشرحها —
    فيمرّ الحارس على ملف لا يثبّتها. وحارس يكفيه تعليق لا يحرس شيًئا.
    """
    keep = [line for line in path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")]
    return chr(10).join(keep)


def _server_dockerfiles() -> list[Path]:
    """كل Dockerfile يشغّل الخادم — يُعرَف بتثبيته tesseract.

    الاكتشاف بالمحتوى لا بقائمة أسماء: ملف ثالث يُضاف غًدا يدخل الفحص
    من يوم إضافته، لا يوم يتذكّره أحد.
    """
    found = []
    for path in list(ROOT.glob("Dockerfile*")) + list(ROOT.glob("*/Dockerfile*")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if "tesseract-ocr" in text:
            found.append(path)
    return found


def test_at_least_two_server_images_are_checked():
    """توثيق الشرط: لو صار ملًفا واحًدا فلا انحراف — وهذا خبر جيّد."""
    files = _server_dockerfiles()
    assert files, "لم يُعثر على أي Dockerfile يشغّل الخادم"


@pytest.mark.parametrize("package,reason", sorted(REQUIRED_PACKAGES.items()))
def test_every_server_image_installs_the_package(package, reason):
    """حزمة ناقصة في صورة واحدة تعني بيئتين تتصرّفان تصرًُّفا مختلًفا."""
    missing = [str(p.relative_to(ROOT)) for p in _server_dockerfiles()
               if package not in _instructions(p)]
    assert not missing, (
        f"«{package}» ({reason}) غائبة عن: {missing}"
    )


def test_every_server_image_installs_an_arabic_font():
    """LibreOffice بلا خطوط عربية أسوأ من غيابه.

    يُنتج ملًفا يبدو سليًما وهو مربّعات فارغة — والتوليد يعود بنجاح وتُحسب
    بصمته ويصل الموظف ليوقّعه.
    """
    missing = []
    for path in _server_dockerfiles():
        text = _instructions(path)
        if not any(f in text for f in ARABIC_FONT_PACKAGES):
            missing.append(str(path.relative_to(ROOT)))
    assert not missing, (
        f"لا حزمة خطوط عربية في: {missing} — العقد سيخرج بمربّعات فارغة"
    )


def test_the_production_image_is_the_one_at_the_repo_root():
    """توثيق ما كلّفنا نشرة كاملة: الجذر هو ما تبنيه المنصّة.

    والفحص يمنع حذفه أو إفراغه بلا انتباه.
    """
    root_df = ROOT / "Dockerfile"
    assert root_df.exists(), "Dockerfile الجذر مفقود — لا صورة إنتاج"
    text = root_df.read_text(encoding="utf-8")
    assert re.search(r"COPY\s+backend/", text), (
        "Dockerfile الجذر لا ينسخ الخادم — ليس صورة الإنتاج"
    )
    assert "uvicorn" in text, "لا أمر تشغيل للخادم في صورة الإنتاج"
