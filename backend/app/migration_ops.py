# -*- coding: utf-8 -*-
"""عمليات ترحيل تعمل على SQLite وPostgreSQL معًا.

سبب وجود هذا الملف: ``alembic upgrade head`` كان **يفشل على قاعدة SQLite
فارغة** — أي أن أي تنصيب جديد عند العميل يتوقّف في منتصف السلسلة. والاختبارات
لا تكشفه لأنها تبني الجداول بـ``Base.metadata.create_all`` لا بالترحيلات، فالعطل
عاش في المسار الوحيد الذي لا يمرّ عليه أحد حتى يوم التسليم.

عطلان متمايزان، كلاهما في ``op.add_column``:

1. **مفتاح أجنبي مضمَّن.** ``ALTER TABLE ... ADD COLUMN`` في SQLite لا يقبل
   قيد ``REFERENCES``، فيرفع alembic ``NotImplementedError`` ويقترح batch mode
   — وهو إعادة بناء الجدول بالنسخ، ثقيل ومخاطر فقد بيانات في غير موضعه.
   الحلّ هنا أخف وأدقّ: **تُسقَط علاقة المفتاح على SQLite وحدها**. لا خسارة
   فعلية — SQLite لا تفرض المفاتيح الأجنبية أصًلا ما لم يُفعَّل
   ``PRAGMA foreign_keys=ON``، والقيد يبقى كاملًا على PostgreSQL حيث يُفرَض.
   والنماذج في ``models.py`` تحمل العلاقة على أي حال، فقاعدة تُبنى بـ
   ``create_all`` تحصل عليها.

2. **عمود موجود مسبًقا.** قاعدة أُنشئت بـ``create_all`` ثم خُتمت عند الأساس
   تحمل أعمدة الترحيلات اللاحقة قبل تطبيقها، فيفشل الترحيل بـ
   "duplicate column". الفحص قبل الإضافة يجعل السلسلة **قابلة لإعادة التشغيل**
   على أي قاعدة مهما كان تاريخها — وهي الخاصية التي تجعل الترقية آمنة.

تُستعمل بدل ``op.add_column`` مباشرة في أي ترحيل يضيف عموًدا.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


def _existing_columns(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    try:
        return {c["name"] for c in insp.get_columns(table)}
    except Exception:
        # الجدول غير موجود بعد — الترحيل الذي ينشئه سيأتي لاحًقا في السلسلة
        return set()


def add_column(table: str, column: sa.Column) -> bool:
    """يضيف عموًدا إن لم يكن موجوًدا. يعيد True إن أُضيف فعلًا."""
    if column.name in _existing_columns(table):
        return False

    bind = op.get_bind()
    if bind.dialect.name == "sqlite" and column.foreign_keys:
        # نعيد بناء العمود بلا علاقة المفتاح — انظر السبب (1) أعلاه
        column = sa.Column(
            column.name, column.type,
            nullable=column.nullable,
            default=column.default,
            server_default=column.server_default,
            index=column.index,
            unique=column.unique,
        )
    op.add_column(table, column)
    return True


def drop_column(table: str, name: str) -> bool:
    """يحذف عموًدا إن وُجد — للتراجع الآمن. يعيد True إن حُذف."""
    if name not in _existing_columns(table):
        return False
    op.drop_column(table, name)
    return True


def create_unique(name: str, table: str, columns: list[str]) -> bool:
    """قيد فريد يعمل على الاثنين.

    SQLite لا تقبل ``ALTER TABLE ... ADD CONSTRAINT``، لكن **فهرًسا فريًدا**
    يعطي نفس الضمان تماًما: محاولة إدخال قيمة مكرّرة تفشل. الفرق في الاسم لا
    في الأثر. (الترحيل ذاته كان يستعمل هذه الحيلة لجدول الشركات ويغفل عنها
    لجدول الموظفين — فانكسرت السلسلة عند الثاني.)
    """
    insp = sa.inspect(op.get_bind())
    try:
        if any(i["name"] == name for i in insp.get_indexes(table)):
            return False
        if any(u.get("name") == name for u in insp.get_unique_constraints(table)):
            return False
    except Exception:
        pass

    if op.get_bind().dialect.name == "sqlite":
        op.create_index(name, table, columns, unique=True)
    else:
        op.create_unique_constraint(name, table, columns)
    return True


def create_fk(name: str, source: str, referent: str,
              local_cols: list[str], remote_cols: list[str]) -> bool:
    """مفتاح أجنبي على PostgreSQL، ويُتخطّى على SQLite.

    SQLite لا تضيف مفتاًحا أجنبًيا لجدول قائم إلا بإعادة بنائه كاملًا، ولا
    تفرض المفاتيح أصًلا ما لم يُفعَّل ``PRAGMA foreign_keys=ON``. فالتخطّي هنا
    لا يفقد ضماًنا قائًما، بينما الإصرار عليه يوقف التنصيب كلّه — وهذه مقايضة
    واضحة الطرفين. العلاقة تبقى معرَّفة في ``models.py`` وتُفرَض على الإنتاج.
    """
    if op.get_bind().dialect.name == "sqlite":
        return False
    op.create_foreign_key(name, source, referent, local_cols, remote_cols)
    return True
