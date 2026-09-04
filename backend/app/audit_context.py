# -*- coding: utf-8 -*-
"""QA-26 — سياق الفاعل للطلب الجاري (actor + IP).

ROOT CAUSE: سجلات مثل ``request_completed`` كانت تُكتب بـ``user_id=None`` وبلا
IP، فتظهر في سجل التدقيق "بدون منفذ". لم يكن ذلك إهمالًا في موضع الكتابة: هذه
السجلات تُكتب داخل ``_finalize`` التي تُستدعى عبر ``enter_stage`` ثم ``_advance``
ولا يصلها كائن ``user`` ولا ``Request`` أصلًا. تمرير الفاعل يدوًيا عبر السلسلة
كان يعني تعديل كل نداء في المسار — ومع أول مسار جديد يعود العطل نفسه.

الحل: سياق واحد يُضبط مرة عند مصادقة الطلب (``get_current_user``)، وتقرأ منه
أي كتابة تدقيق لا تعرف فاعلها. خارج سياق HTTP (المجدوِل، سكربتات الصيانة)
يبقى فارًغا فيُسجَّل الحدث باسم النظام مع سببه — لا "بدون منفذ".

ContextVar لا ينتشر بين الطلبات: كل طلب يبدأ بقيمته الخاصة، والقيمة تُعاد
لسابقتها بعد انتهائه.
"""
from contextvars import ContextVar

_actor: ContextVar[dict | None] = ContextVar("audit_actor", default=None)


def begin_request() -> None:
    """يُنشئ حامل الفاعل في سياق الطلب **الأب** — يُستدعى من الوسيط وحده.

    P11-36 — ولماذا هذا لازم: التابع ``get_current_user`` ونقطةُ النهاية
    كلاهما دالة متزامنة، فتُنفَّذان في خيطَي عمل مختلفين، ولكلٍّ نسخته من
    سياق ``ContextVar``. فما يضبطه التابع لا يبلغ نقطة النهاية أصًلا:
    قِسته فوجدت ``get_actor()`` فارًغا داخل محرّك المسار، وسطر
    ``request_completed`` يُكتب «بلا منفذ» رغم أنه صار يقرأ الفاعل.

    فآلية QA-26 كانت مكتوبة ولا تعمل، والصفر الذي تنتجه يبدو صحيًحا:
    «فعله النظام» جواب معقول لا يستوقف أحًدا.

    والحلّ حامل **قابل للتعديل** يُنشأ هنا قبل تفرّع الخيوط: النسخ تشترك
    في القاموس نفسه، فما يكتبه التابع تقرؤه نقطة النهاية.
    """
    _actor.set({})


def set_actor(user_id: int | None, ip: str | None, user_agent: str | None = None,
              original_user_id: int | None = None) -> None:
    """يضبط فاعل الطلب الجاري — يُستدعى من get_current_user وحده.

    و``original_user_id`` هو **من يجلس أمام الشاشة حًقا** عند الانتحال.
    بدونه تعرف طبقةُ القرار المُنتحَلَ وحده، فتفحص قواعد النزاهة على
    الشخص الخطأ: مَن انتحل شخصية معتمِد يستطيع اعتماد طلبٍ هو مقدّمه —
    والاعتماد الذاتي ممنوع لكل الأدوار.
    """
    values = {"user_id": user_id, "ip": ip, "user_agent": user_agent,
              "original_user_id": original_user_id}
    holder = _actor.get()
    if holder is None:
        _actor.set(values)      # خارج سياق HTTP (اختبار مباشر، سكربت)
    else:
        # تعديل في المكان: النسخ في الخيوط الأخرى تحمل مرجع القاموس نفسه.
        holder.clear()
        holder.update(values)


def get_actor() -> dict:
    """فاعل الطلب الجاري، أو قاموس فارغ خارج سياق HTTP."""
    return _actor.get() or {}


def actor_user_id() -> int | None:
    return get_actor().get("user_id")


def actor_ip() -> str | None:
    return get_actor().get("ip")


def original_actor_user_id() -> int | None:
    """الفاعل الحقيقي عند الانتحال، أو None في الجلسة العادية."""
    return get_actor().get("original_user_id")
