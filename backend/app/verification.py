# -*- coding: utf-8 -*-
"""رمز تحقق (QR verification, P2-01) للمستندات الموجّهة لجهات خارجية (شهادات/خطابات) —
يتيح لطرف خارجي (بنك/سفارة) التأكد من صحة مستند مطبوع دون حساب في النظام، عبر رمز قصير
مطبوع أسفل المستند بدل الاكتفاء بالثقة العمياء بالورقة. لا يحتاج عمودًا جديدًا في قاعدة
البيانات — الرمز مُشتق (HMAC) من document_id/request_id فيُعاد حسابه وقت التحقق ويُقارَن،
بدل تخزينه (فيصبح صالًحا تلقائًيا لكل مستند موجود سلًفا أيًضا دون الحاجة لأي migration).
"""
import hashlib
import hmac as hmac_lib

from .config import settings

_SEP = "-"


def _sign(document_id: int, request_id: int) -> str:
    return hmac_lib.new(
        settings.secret_key.encode("utf-8"),
        f"docverify:{document_id}:{request_id}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:10]


def generate_code(document_id: int, request_id: int) -> str:
    return f"{document_id}{_SEP}{_sign(document_id, request_id)}"


def parse_document_id(code: str) -> int | None:
    """يستخرج document_id من الرمز (بلا تحقق توقيع بعد — الطلب الحقيقي غير معروف قبل جلب السجل)."""
    try:
        doc_id_s, _sig = code.split(_SEP, 1)
        return int(doc_id_s)
    except (ValueError, AttributeError):
        return None


def is_valid(code: str, document_id: int, request_id: int) -> bool:
    try:
        _doc_id_s, sig = code.split(_SEP, 1)
    except (ValueError, AttributeError):
        return False
    return hmac_lib.compare_digest(sig, _sign(document_id, request_id))
