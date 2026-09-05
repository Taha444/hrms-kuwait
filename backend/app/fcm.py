# -*- coding: utf-8 -*-
"""مزوّد Firebase Cloud Messaging — **نقل وحده، بلا منطق عمل**.

مَن يستحقّ الإشعار وبأي نصّ يظهر: ذلك في ``push_policy``. وهذه الوحدة
تعرف شيًئا واحًدا: كيف تُسلَّم حمولة جاهزة إلى رمز جهاز.

**والفصل ليس ترتيًبا**: خلطُهما يجعل قرار «هل يُدفَع؟» رهينة توفّر
Firebase — فلا يُختبَر إلا بشبكة واعتماد، ويصير أول ما يُعطَّل عند
الضيق.

**المصادقة**: FCM HTTP v1 لا يقبل «مفتاح خادم» ثابًتا. يُوقَّع رمز
JWT بمفتاح حساب الخدمة (RS256)، ويُبادَل برمز وصول قصير العمر من
Google، ثم يُرسَل به. والرمز يُخزَّن ويُعاد استعماله حتى يقارب
الانتهاء — طلب رمز جديد مع كل إشعار يضاعف زمن التسليم ويستنفد الحصّة.

**والفشل لا يكسر شيًئا**: الإشعار الداخلي مكتوب في القاعدة قبل أن
تُستدعى هذه الوحدة. فسقوط Firebase يعني أن الموظف يرى الإشعار حين
يفتح النظام — لا أن الإشعار ضاع.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time

from .config import settings

logger = logging.getLogger("hrms.fcm")

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_SEND_URL = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"

#: هامش قبل انتهاء رمز الوصول — يُجدَّد قبله لا بعده.
_RENEW_MARGIN_SECONDS = 120

#: ردود Firebase التي تعني «هذا الرمز لم يعد صالًحا لجهاز موجود».
#: يُوسَم الجهاز عندها ولا يُعاد إليه — وإلا بقي كل إرسال يفشل صامًتا.
DEAD_TOKEN_ERRORS = frozenset({"UNREGISTERED", "INVALID_ARGUMENT",
                               "NOT_FOUND", "SENDER_ID_MISMATCH"})

_lock = threading.Lock()
_access_token: str | None = None
_access_expiry: float = 0.0


def _credentials() -> dict | None:
    """بيانات حساب الخدمة — من ملف أو من الإعدادات مباشرة.

    والملف مقدَّم: مفتاح خاص في متغيّر بيئة يظهر في كل لقطة سجلّ وكل
    نسخة احتياطية للإعدادات.
    """
    path = (settings.fcm_credentials_file or "").strip()
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return {"project_id": data.get("project_id"),
                    "client_email": data.get("client_email"),
                    "private_key": data.get("private_key")}
        except (OSError, ValueError):
            logger.exception("تعذّرت قراءة ملف اعتماد FCM: %s", path)
            return None

    if not (settings.fcm_project_id and settings.fcm_client_email
            and settings.fcm_private_key):
        return None
    return {
        "project_id": settings.fcm_project_id,
        "client_email": settings.fcm_client_email,
        # مفاتيح .env تُكتب بـ\\n حرفًيا — تُعاد إلى أسطر حقيقية وإلا
        # رفض التوقيع المفتاح بلا سبب ظاهر.
        "private_key": settings.fcm_private_key.replace("\\n", "\n"),
    }


def is_configured() -> bool:
    """هل يمكن الإرسال فعًلا؟ — يقرؤها كتالوج القنوات."""
    return _credentials() is not None


def _mint_access_token(creds: dict) -> str | None:
    """يبادل رمز خدمة موقًَّعا برمز وصول من Google."""
    import httpx
    import jwt

    now = int(time.time())
    claim = {
        "iss": creds["client_email"],
        "scope": _SCOPE,
        "aud": _TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }
    try:
        assertion = jwt.encode(claim, creds["private_key"], algorithm="RS256")
        r = httpx.post(_TOKEN_URL, timeout=15, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        })
        if r.status_code != 200:
            logger.error("رفض Google رمز الخدمة: %s %s",
                         r.status_code, r.text[:200])
            return None
        body = r.json()
        global _access_expiry
        _access_expiry = time.time() + int(body.get("expires_in", 3600))
        return body.get("access_token")
    except Exception:                       # noqa: BLE001
        logger.exception("تعذّر استخراج رمز وصول FCM")
        return None


def _access() -> str | None:
    """رمز وصول صالح — يُعاد استعماله حتى يقارب الانتهاء."""
    global _access_token
    creds = _credentials()
    if not creds:
        return None
    with _lock:
        if _access_token and time.time() < _access_expiry - _RENEW_MARGIN_SECONDS:
            return _access_token
        _access_token = _mint_access_token(creds)
        return _access_token


def reset_cache() -> None:
    """يُسقط الرمز المخزَّن — للاختبارات وعند تغيير الاعتماد."""
    global _access_token, _access_expiry
    with _lock:
        _access_token, _access_expiry = None, 0.0


def send(token: str, payload: dict) -> tuple[bool, str | None]:
    """يسلّم حمولة جاهزة إلى جهاز واحد.

    يعيد ``(نجح، سبب_الفشل)``. والسبب يُعاد نًصا لأن المستدعي يقرّر به
    هل يَسِم الجهاز ميًتا — والقرار هناك لا هنا.
    """
    import httpx

    creds = _credentials()
    if not creds:
        return False, "NOT_CONFIGURED"
    access = _access()
    if not access:
        return False, "AUTH_FAILED"

    message = {
        "message": {
            "token": token,
            # ``notification`` يُظهرها النظام حتى والتطبيق مغلق.
            "notification": {"title": payload.get("title", ""),
                             "body": payload.get("body", "")},
            # و``data`` يقرؤها التطبيق عند الضغط — الرابط هنا لا في
            # النصّ، فلا يظهر مسار داخلي على شاشة القفل.
            "data": {"link": str(payload.get("link", "/tasks")),
                     "kind": str(payload.get("kind", ""))},
            "webpush": {
                "fcm_options": {"link": str(payload.get("link", "/tasks"))},
            },
        }
    }
    url = _SEND_URL.format(project=creds["project_id"])
    try:
        r = httpx.post(url, timeout=15, json=message,
                       headers={"Authorization": f"Bearer {access}"})
    except Exception as exc:                # noqa: BLE001
        logger.warning("تعذّر الاتصال بـFCM: %s", exc)
        return False, "NETWORK"

    if r.status_code == 200:
        return True, None

    # 401 قد تعني رمز وصول انتهى قبل هامشه — تُجرَّب مرة واحدة برمز جديد.
    if r.status_code == 401:
        reset_cache()
        if _access():
            return send(token, payload)

    reason = "HTTP_%s" % r.status_code
    try:
        err = (r.json().get("error") or {})
        details = err.get("details") or []
        for d in details:
            code = d.get("errorCode")
            if code:
                reason = code
                break
        else:
            reason = err.get("status") or reason
    except ValueError:
        pass
    logger.warning("رفض FCM الإرسال: %s — %s", reason, r.text[:200])
    return False, reason
