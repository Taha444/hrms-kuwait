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
# **ولماذا تأخّر التفعيل، والتشخيص الذي أخّره**: جُرّب فسقط سبعة عشر
# اختباًرا، فقُرئ ذلك على أنه «اثنان وستون مفتاًحا يشير إلى ``users`` بلا
# سياسة ``ondelete``»، وكُتب أن التفعيل بلا سياسات «ينقل العطل من لا
# يُفرَض إلى يُفرَض فيمنع كل حذف».
#
# **والقياس نقض المقدّمة**: لا مسار في التطبيق يحذف مستخدًما — لا نقطة
# نهاية ``DELETE /users`` ولا ``db.delete(user)``. المستخدم يُعطَّل
# (``is_active=False``) ولا يُحذَف، لأن سجلّه دليل على ما فعله.
#
# فـ«يمنع كل حذف» هو المطلوب بعينه، وغياب ``ondelete`` يعني ``RESTRICT``
# وهو افتراض SQL — أي أن السياسات كانت صحيحة من البداية. ولم يكن الناقص
# سياسًة بل **ترتيب حذف في تنظيف الاختبارات**: تحذف الأب قبل أبنائه.
#
# فأُصلح المصدر: ``tests.conftest.purge`` يشتقّ ترتيب الحذف من
# ``metadata`` لا من قائمة تُكتب باليد وتتقادم. وسقطت التسعة الباقية
# كلها بذلك السبب وحده.
#
# ويحرسه ``test_no_code_path_deletes_a_user``: لو أُضيف غًدا مسار يحذف
# مستخدًما، صار غياب السياسات عيًبا حقيقًيا — ويسقط الاختبار عندئذٍ، وهو
# الوقت الصحيح للمراجعة.
#
from sqlalchemy import event as _event


@_event.listens_for(engine, "connect")
def _fk(dbapi_connection, _record):
    try:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")
    except Exception:
        pass


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
