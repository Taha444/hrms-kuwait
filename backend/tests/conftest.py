# -*- coding: utf-8 -*-
"""تهيئة الاختبارات: قاعدة بيانات SQLite مؤقتة + عميل اختبار + بذور."""
import os
import tempfile

os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(tempfile.gettempdir(), 'hrms_test.db')}"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["UPLOAD_DIR"] = os.path.join(tempfile.gettempdir(), "hrms_test_uploads")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# حذف قاعدة الاختبار القديمة إن وُجدت
_db = os.environ["DATABASE_URL"].replace("sqlite:///", "")
if os.path.exists(_db):
    os.remove(_db)

from app.database import Base, engine  # noqa: E402
from app import seed as seed_module  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    Base.metadata.drop_all(bind=engine)
    seed_module.run()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def login(client, civil_id, password):
    r = client.post("/api/auth/login", json={"civil_id": civil_id, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def purge(db, table_name: str, ids) -> None:
    """يحذف صفوًفا **وكل ما يشير إليها**، بترتيب مشتقّ من المخطّط.

    F-003 — تنظيف الاختبارات كان يحذف الأب قبل أبنائه، فسقط سبعة عشر
    اختباًرا حين جُرّب فرض المفاتيح الأجنبية. وقُرئ ذلك على أنه «اثنان
    وستون مفتاًحا بلا سياسة ``ondelete``» فتُركت النتيجة مفتوحة.

    **والقياس يقول غير ذلك**: لا مسار في التطبيق يحذف مستخدًما — لا
    نقطة نهاية ولا ``db.delete``. المستخدم يُعطَّل ولا يُحذَف. فالسياسة
    الصحيحة للمراجع الاثنين والستين هي **الرفض** (افتراض SQL)، وهي
    القائمة فعًلا. ولم يكن الناقص سياسًة بل ترتيب حذف في الاختبارات.

    والترتيب يُشتقّ من ``metadata`` لا يُعدّ يدًوا: جدول يُضاف غًدا يشير
    إلى ``users`` يُنظَّف من تلقائه، ولا يُنسى حتى يسقط اختبار بعيد.
    """
    ids = [i for i in (ids or []) if i is not None]
    if not ids:
        return
    meta = Base.metadata
    parent = meta.tables[table_name]
    pk = list(parent.primary_key.columns)[0]

    # الأبناء أوًلا: كل عمود في أي جدول يشير إلى مفتاح هذا الجدول.
    for table in reversed(meta.sorted_tables):
        if table is parent:
            continue
        for col in table.columns:
            if any(fk.column is pk for fk in col.foreign_keys):
                db.execute(table.delete().where(col.in_(ids)))
    db.execute(parent.delete().where(pk.in_(ids)))
