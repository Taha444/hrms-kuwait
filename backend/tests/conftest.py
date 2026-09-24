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


@pytest.fixture(autouse=True)
def _fresh_environment_report():
    """كان فحصُ بيئة العقد مُخزًَّنا لساعة (مولّد الـdocx). والمولّدُ الحالي
    يقرأ الملفَّ والخطَّ في كل نداء، فلا ذاكرة تُنظَّف — ويبقى التركيبُ
    ليُعلَم أن الشرط كان قائًما ولم يُنسَ.
    """
    yield


@pytest.fixture(autouse=True)
def _leave_state_isolation():
    """M12 — طلباتُ الإجازة وسجلّاتُها التي أنشأها الاختبار لا تبقى لما بعده.

    القاعدة واحدةٌ لكامل الجلسة (``_setup_db``)، وحارسُ تداخل الإجازات في ``create_request``
    يرفض فترةً تتداخل مع طلبٍ حيٍّ أو إجازةٍ معتمَدة لنفس الموظف — وهو صحيحٌ في الإنتاج. أما
    هنا فاختباراتٌ كثيرة تستعمل الإجازة **وسيلةً** لقياس شيءٍ آخر (اعتماد، تدقيق، سباق) بنفس
    الموظف المزروع وتواريخَ ثابتة، فكانت تتصادم بما تركه غيرُها (35 اختبارًا فشلت). فيُغلَق
    ما أنشأه كلُّ اختبار وحده: ما ``id`` أكبر من لقطة البداية، ولأنواع الإجازة فقط.
    """
    from sqlalchemy import func, select, update

    from app import models
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        base_req = db.scalar(select(func.max(models.Request.id))) or 0
        base_leave = db.scalar(select(func.max(models.Leave.id))) or 0
    finally:
        db.close()
    yield
    db = SessionLocal()
    try:
        # **إغلاقٌ لا حذف**: حذف الطلب يُعيد معرّفَه لاختبارٍ لاحق في SQLite، فتلتبس به
        # أسطرُ تدقيقٍ قديمة تشير إلى المعرّف نفسه (اختبارات التدقيق تقرؤها بالمعرّف).
        # والحارس يتجاهل ما ليس حيًّا (الملغى) وما ليس «معتمَدًا» (سجلّ الإجازة الملغى).
        from datetime import datetime, timezone

        from app import workflow

        for req in db.scalars(select(models.Request).where(
                models.Request.id > base_req,
                models.Request.request_type_code.in_(("REQLV", "leave")),
                models.Request.status.in_(("pending", "awaiting_signature",
                                           "awaiting_delegate", "ready_for_pickup",
                                           "apply_failed")))).all():
            req.status = "cancelled"
            req.closed_at = datetime.now(timezone.utc)
            req.dedup_fingerprint = None
            workflow._close_open_tasks(db, req)   # كما يفعل التطبيق: لا مهمة على طلبٍ منتهٍ
        db.execute(update(models.Leave).where(
            models.Leave.id > base_leave, models.Leave.status == "approved")
            .values(status="cancelled"))
        db.commit()
    except Exception:  # noqa: BLE001 — تنظيفٌ مساعد لا يُسقط اختبارًا
        db.rollback()
    finally:
        db.close()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def plain_employee_clause(models_module):
    """شرط SQLAlchemy: موظفٌ ليس صاحبَ حسابٍ بدورٍ إداريّ (لا يعلو HR ولا المحاسب)."""
    from sqlalchemy import select as _select

    return ~models_module.Employee.id.in_(
        _select(models_module.User.employee_id).where(
            models_module.User.role != "employee", models_module.User.employee_id.isnot(None)))


def attach_file(client, headers, req_id: int):
    """يرفع ملفًّا حقيقيًا بنوع ``attachment`` — كما يفعل صاحبُ الطلب من صفحته.

    المرفقُ المطلوب صار ملفًّا قبل الاعتماد لا اسمًا يُدّعى في الحمولة
    (``test_zzz_required_attachments``)؛ فالاختباراتُ التي تعتمد نوعًا يستوجبه
    ترفعه كما يرفعه المستخدم.
    """
    import io as _io

    r = client.post(f"/api/requests/{req_id}/documents", headers=headers,
                    data={"kind": "attachment"},
                    files={"file": ("attachment.pdf", _io.BytesIO(b"%PDF-1.4 test"),
                                    "application/pdf")})
    assert r.status_code in (200, 201), r.text[:200]
    return r


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
