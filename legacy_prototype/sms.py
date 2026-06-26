# -*- coding: utf-8 -*-
"""
واجهة إرسال الرسائل النصية (SMS). مُجرّدة عن المزوّد ليسهل توصيل أي بوابة كويتية
(مثل بوابات الاتصالات أو مزوّدي SMS). مُعطّلة افتراضيًا.

للتفعيل: اضبط HRMS_SMS_ENABLED=true و HRMS_SMS_PROVIDER و HRMS_SMS_API_KEY،
ثم نفّذ منطق المزوّد في _send_via_provider.
"""
import logging

from config import config

log = logging.getLogger("hrms.sms")


def _send_via_provider(to_number, text):
    """نقطة التوصيل بمزوّد فعلي. تُنفّذ حسب المزوّد المختار.

    مثال (شبه كود): requests.post(provider_url, json={...}, headers={api_key}).
    تُركت كنقطة امتداد لأنها تتطلب حساب مزوّد.
    """
    log.info("[SMS provider=%s] to=%s text=%s", config.SMS_PROVIDER, to_number, text)
    return True


def send_sms(to_number, text):
    """يرسل رسالة نصية. يرجع True عند النجاح/أو التعطيل في التطوير."""
    if not config.SMS_ENABLED:
        log.info("[SMS disabled] to=%s text=%s", to_number, text)
        return False
    if not to_number:
        return False
    try:
        return _send_via_provider(to_number, text)
    except Exception as e:
        log.warning("فشل إرسال SMS إلى %s: %s", to_number, e)
        return False
