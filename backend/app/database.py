# -*- coding: utf-8 -*-
"""تهيئة الاتصال بقاعدة البيانات عبر SQLAlchemy 2.0.

نعزل الوصول خلف جلسة (Session) ودالة get_db بحيث يسهل التبديل
بين SQLite (تطوير) و PostgreSQL (إنتاج) عبر DATABASE_URL فقط.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

# لـ SQLite نحتاج check_same_thread=False للسماح بالاستخدام عبر الخيوط
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """القاعدة المشتركة لكل النماذج (Models)."""


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
