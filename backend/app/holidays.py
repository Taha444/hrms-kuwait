# -*- coding: utf-8 -*-
"""تقويمُ العطل الرسمية — قرار المالك (2026-09-17).

كان النظامُ بلا تقويمٍ للعطل: يومُ العيد يوم عملٍ في الوردية، فيُعرض
«غير مسجَّل» لمن لم يحضر، ويُعدّ في تنبيه أيام الإجازة، ويُحسب العملُ فيه
إضافيًّا عاديًّا بعد الوردية وحدها.

**والقرار**: تقويمٌ يُدخله شؤونُ الموظفين لكل شركة؛ العطلةُ لا تُعدّ غيابًا
ولا «غير مسجَّل» ولا تُحتسب من الإجازة، والعملُ فيها إضافيٌّ كلُّه بنسبة
السياسة ``overtime.holiday_rate`` — وما زال معلَّقًا على اعتماد طلب
«عمل إضافي» كسائر الإضافي.

مصدرٌ واحد يقرؤه المسيّر وشاشةُ المراجعة وعدّادُ الإقفال وتنبيهُ الإجازة.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


def holiday_dates(db: Session, company_id: int, first: date, last: date) -> dict[date, str]:
    """العطلُ في ``[first, last]`` لهذه الشركة: {التاريخ: الاسم}."""
    rows = db.scalars(select(models.Holiday).where(
        models.Holiday.company_id == company_id,
        models.Holiday.date >= first,
        models.Holiday.date <= last)).all()
    return {r.date: r.name for r in rows}


def holiday_rate(db: Session, company_id: int, on_date: date | None = None) -> float:
    from . import policy
    pol = policy.get(db, company_id, "overtime.holiday_rate", on_date=on_date)
    return float((pol.get("value") or {}).get("rate") or 0)
