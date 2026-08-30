# -*- coding: utf-8 -*-
"""تهيئة الاتصال بقاعدة البيانات عبر SQLAlchemy 2.0.

نعزل الوصول خلف جلسة (Session) ودالة get_db بحيث يسهل التبديل
بين SQLite (تطوير) و PostgreSQL (إنتاج) عبر DATABASE_URL فقط.
"""
from collections.abc import Generator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

# اصطلاح تسمية القيود — ضروري لعمل هجرات Alembic بنمط batch على SQLite
_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# لـ SQLite نحتاج check_same_thread=False للسماح بالاستخدام عبر الخيوط
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

# F-003 — SQLite تتجاهل المفاتيح الأجنبية ما لم تُطلَب لكل اتصال، بينما
# يفرضها PostgreSQL على الإنتاج. فصفٌّ يتيم يمرّ أخضر محلًّيا ويُرفض هناك.
#
# **ولماذا لم تُفعَّل بعد**: جُرّبت فسقط سبعة عشر اختبارًا — لا لأنها تُنشئ
# بيانات فاسدة، بل لأن تنظيفها يحذف الأب قبل الأبناء. والعلاج الصحيح ليس
# ترقيع التنظيف: اثنان وستون مفتاًحا أجنبًيا يشير إلى ``users`` بلا سياسة
# ``ondelete``، ومعها دورات مراجع يحذّر منها SQLAlchemy. فتفعيل الفرض
# بلا تلك السياسات ينقل العطل ولا يزيله.
#
# والقرار: تبقى النتيجة **مفتوحة وموثَّقة** في docs/qa/BACKEND_AUDIT.md
# بدل شحن تفعيل يكسر المجموعة. وترتيب العمل: تُراجَع سياسات الحذف
# للمراجع الاثنين والستين أوًلا، ثم يُفعَّل الفرض ويُثبَّت بحارس.
#
#     @event.listens_for(engine, "connect")
#     def _fk(dbapi_connection, _record):
#         dbapi_connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """القاعدة المشتركة لكل النماذج (Models)."""
    metadata = MetaData(naming_convention=_NAMING_CONVENTION)


def get_db() -> Generator[Session, None, None]:
    """تبعية FastAPI لإعطاء جلسة قاعدة بيانات وإغلاقها تلقائيًا."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """إنشاء الجداول (للتطوير). في الإنتاج تُدار عبر Alembic."""
    from . import models  # noqa: F401 — تسجيل النماذج

    Base.metadata.create_all(bind=engine)
