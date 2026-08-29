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


def set_actor(user_id: int | None, ip: str | None, user_agent: str | None = None,
              original_user_id: int | None = None) -> None:
    """يضبط فاعل الطلب الجاري — يُستدعى من get_current_user وحده.

    و``original_user_id`` هو **من يجلس أمام الشاشة حًقا** عند الانتحال.
    بدونه تعرف طبقةُ القرار المُنتحَلَ وحده، فتفحص قواعد النزاهة على
    الشخص الخطأ: مَن انتحل شخصية معتمِد يستطيع اعتماد طلبٍ هو مقدّمه —
    والاعتماد الذاتي ممنوع لكل الأدوار.
    """
    _actor.set({"user_id": user_id, "ip": ip, "user_agent": user_agent,
                "original_user_id": original_user_id})


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
