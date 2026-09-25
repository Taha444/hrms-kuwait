# -*- coding: utf-8 -*-
"""المصدر الواحد لنوافذ الانتهاء (M16): متى يصير التصريح «قريب الانتهاء» ومتى «عاجلًا».

كانت العتبتان 90 و30 مكتوبتين يدويًا في اللوحة ومركز العمليات وشاشة المندوب وأرقام الفرع
وقائمة التجديدات ومحرّك التجديد — و``_urgency`` منسوخةً حرفيًا في ملفين. فتغيير إحداها يُفرّق
الشاشات: تقول اللوحةُ «عاجل» والقائمةُ «تحذير» عن التصريح نفسه.
"""
from datetime import timedelta

#: أبعد من هذا: لا تنبيه ولا يصحّ فتح تجديد.
WINDOW_DAYS = 90
#: ضمن هذا: عاجل، والتجديدُ «عادي» لا «مبكر».
URGENT_DAYS = 30

WINDOW = timedelta(days=WINDOW_DAYS)
URGENT = timedelta(days=URGENT_DAYS)


def urgency(days_left: int | None) -> str:
    """expired / critical / warning / ok — وغياب التاريخ ``ok`` (لكلٍّ أن يعرض ما يناسبه له)."""
    if days_left is None:
        return "ok"
    if days_left < 0:
        return "expired"
    if days_left <= URGENT_DAYS:
        return "critical"
    if days_left <= WINDOW_DAYS:
        return "warning"
    return "ok"
