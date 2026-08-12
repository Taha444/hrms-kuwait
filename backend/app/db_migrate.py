# -*- coding: utf-8 -*-
"""تشغيل ترحيلات قاعدة البيانات عند الإقلاع — بصوت مسموع عند الفشل.

سبب وجود هذا الملف: أمر الإقلاع كان

    alembic upgrade head || alembic stamp head

و`stamp head` يكتب رقم أحدث إصدار في alembic_version **بلا تطبيق أي ترحيل**.
فأي فشل مرة واحدة — عطل شبكة، قفل، خطأ في ترحيل — يختم القاعدة عند الرأس،
وكل نشر بعدها يراها محدَّثة فلا يطبّق شيًئا. صامتًا وإلى الأبد. هذا ما جعل
جدول قوالب الإشعارات فارًغا ونص العقد قديًما والأعمدة الجديدة غائبة في الإنتاج
بينما الخدمة تعمل بلا شكوى.

القاعدة هنا: الختم لحالة واحدة معرَّفة فقط — قاعدة أُنشئت قديمًا بـcreate_all
فلها جداول بلا alembic_version — ويُختم عندها إصدار **الأساس** لا الرأس، ثم
تُطبَّق الترحيلات التالية فعلًا. وأي فشل آخر يوقف الإقلاع برمز خروج غير صفري
بدل أن يُخفى.
"""
from __future__ import annotations

import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from .database import engine

# أول ترحيل في السلسلة (down_revision = None) — يمثّل المخطط الذي كان
# create_all ينتجه.
BASELINE_REVISION = "68862c46506d"


def run() -> None:
    cfg = Config("alembic.ini")
    insp = inspect(engine)
    tables = set(insp.get_table_names())

    if "alembic_version" not in tables and tables:
        # قاعدة قديمة أُنشئت بـcreate_all: نختمها عند الأساس لا الرأس، فتُطبَّق
        # كل الترحيلات اللاحقة عليها بدل تخطّيها.
        print(f"[migrate] قاعدة قائمة بلا alembic_version — ختم الأساس "
              f"{BASELINE_REVISION} ثم الترقية", flush=True)
        command.stamp(cfg, BASELINE_REVISION)

    print("[migrate] alembic upgrade head", flush=True)
    command.upgrade(cfg, "head")
    print("[migrate] تمّت الترقية", flush=True)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:  # noqa: BLE001 — نريد رسالة واضحة ثم فشل الإقلاع
        print(f"[migrate] فشل تطبيق الترحيلات: {type(exc).__name__}: {exc}",
              file=sys.stderr, flush=True)
        # الخروج بخطأ يوقف النشر بدل أن يقلع بمخطط قديم بصمت
        sys.exit(1)
