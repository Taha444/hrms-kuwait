# -*- coding: utf-8 -*-
"""خيارات الحقول المرجعية — يُعبّئها الخادم لا المستخدم.

**العطل (V-F)**: سبعة حقول في نماذج الطلبات من نوع ``*_ref`` — الفرع
الهدف، والوردية المطلوبة، والترخيص التابع — كانت تُعرض **حقل رقم**.
فيُطلب من الموظف أن يكتب معرّف قاعدة البيانات: «الوردية المطلوبة: 2».

وهو رقم لا يعرفه ولا سبيل له إلى معرفته، ولا تعرضه أي شاشة. فالنموذج
غير صالح للاستعمال — لا لأن الورديات غير معرَّفة، بل لأن الحقل يسأل عمّا
لا يُسأل عنه إنسان.

وقُرئ هذا في المراجعة على أنه «إعداد ناقص» (``REQSHIFT`` لا يعمل).
والتحقيق أظهر أن الإعداد قائم: ورديتان في البذرة، ومخطّط كامل، وأثر
تشغيلي يكتب الوردية عند الاعتماد. الناقص كان أن يعرف المستخدم ما يكتب.

**والخيارات تُبنى داخل نطاق الشركة**: قائمة تحمل فروع شركة أخرى تسريب،
وقائمة تحمل الكلّ تُربك.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models

#: نوع الحقل ← كيف تُجلب خياراته.
#: يُقرأ من هنا لا من اسم الحقل: حقل يُسمّى ``to_branch_id`` وآخر
#: ``target_branch_id`` كلاهما ``branch_ref``، والنوع هو ما يحدّد المصدر.
_SOURCES = {
    "branch_ref": (models.Branch, "name"),
    "shift_ref": (models.Shift, "name"),
    "license_ref": (models.License, "name"),
}


def options_for(db: Session, field_type: str, company_id: int | None) -> list[dict]:
    """خيارات حقل مرجعي واحد، مقصورة على شركة المستخدم."""
    src = _SOURCES.get(field_type)
    if not src:
        return []
    model, label_attr = src
    q = select(model)
    if company_id is not None and hasattr(model, "company_id"):
        q = q.where(model.company_id == company_id)
    rows = db.scalars(q).all()
    out = []
    for r in rows:
        label = getattr(r, label_attr, None) or getattr(r, "code", None) or f"#{r.id}"
        out.append({"value": r.id, "label": str(label)})
    return sorted(out, key=lambda o: o["label"])


def fill_schema_options(db: Session, schema: dict, company_id: int | None) -> dict:
    """نسخة من المخطّط بخيارات جاهزة لكل حقل مرجعي.

    **نسخة لا تعديل في مكانه**: ``SCHEMAS`` قاموس على مستوى الوحدة
    مشترك بين كل الطلبات. حقنُ خيارات شركة فيه يجعل الطلب التالي — من
    شركة أخرى — يقرأ فروع الأولى. تسريب من حيث لا يظهر في أي استعلام.
    """
    fields = schema.get("fields") or []
    if not any(str(f.get("type", "")).endswith("_ref") for f in fields):
        return schema

    new_fields = []
    for f in fields:
        ftype = str(f.get("type", ""))
        if ftype.endswith("_ref") and ftype in _SOURCES:
            opts = options_for(db, ftype, company_id)
            f = {**f, "options": opts}
            if not opts:
                # الحماية §3 — «إعداد مطلوب» مفهوم بدل نموذج مكسور.
                f["setup_required"] = {
                    "branch_ref": "لا فروع معرَّفة — يُعرّفها مدير الشركة أولًا",
                    "shift_ref": "لا ورديات معرَّفة — تُعرّف الورديات أولًا",
                    "license_ref": "لا تراخيص معرَّفة — تُضاف التراخيص أولًا",
                }.get(ftype, "لا خيارات معرَّفة بعد")
        new_fields.append(f)
    return {**schema, "fields": new_fields}
