# -*- coding: utf-8 -*-
"""P1-03 — المستند المولَّد يدخل أرشيف الموظف بمجرّد صدوره.

**ما ظهر بالقياس:**

سُقتُ طلب شهادة راتب إلى الاكتمال. المستند وُلّد فعًلا
(``lifecycle_status=GENERATED``، مرجع ``REQ-000001-GENERA-v1``) —
وأرشيف الموظف بقي على مستنداته الثلاثة القديمة، ليست الشهادة بينها.
الدخول إلى الأرشيف كان يقع **داخل ``mark-filed`` وحدها**، وهي ترفض
قبل ``mark-printed``. فمن ولّد شهادة وأرسلها PDF بلا طباعة، لم تدخل
ملف الموظف أبًدا.

**والعطل الثاني يفسّر لماذا لم يُلاحَظ الأول**: مهمة «جاهز للطباعة»
تُنشأ عند الاكتمال ثم يكنسها ``_close_open_tasks`` في اللحظة نفسها —
قرأتُها ``dismissed`` قبل أن يراها أحد. فالطريق الوحيد إلى الأرشيف
كان يُغلق قبل أن يُفتح.

**والقاعدة هنا في موضع واحد** يستدعيه التوليد والأرشفة اليدوية مًعا.
لو كُتبت مرّتين لانحرفت إحداهما: النسخة القديمة تُنزَّل في موضع ولا
تُنزَّل في الآخر، فيحمل الملف نسختين «حاليّتين» لمستند واحد.

**وهي idempotent بالمرجع**: التوليد يؤرشف، ومن يضغط «أرشفة» بعده لا
يُنشئ صًفا ثانًيا لنفس المستند.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from . import models


def archive_type_code(request_type_code: str) -> str:
    """نوع المستند في ملف الموظف — القاعدة نفسها للطرفين."""
    return f"request_{request_type_code}"


def archive_request_document(db, req, doc, *, title: str,
                             actor_id: int | None) -> models.Document | None:
    """يُدخل مستنًدا مولًَّدا أرشيف الموظف، مرّة واحدة.

    يعيد الصفّ المُنشأ، أو ``None`` إن كان مؤرشًفا سلًفا أو غير مكتمل.
    """
    if not (doc and doc.file_path):
        return None                     # لا يُؤرشَف ما لم يُكتب ملفه
    if not getattr(req, "employee_id", None):
        return None

    type_code = archive_type_code(req.request_type_code)

    # idempotent: المرجع هوية المستند. التوليد يؤرشف، ومن يضغط «أرشفة»
    # بعده لا يُنشئ صًفا ثانًيا لنفس الورقة.
    if doc.reference_no:
        existing = db.scalar(select(models.Document).where(
            models.Document.company_id == req.company_id,
            models.Document.reference_no == doc.reference_no))
        if existing:
            return None

    # النسخة السابقة تُنزَّل ولا تُحذف (القاعدة 15): المستند القديم سند
    # لما بُني عليه، وحذفه يترك ما استند إليه بلا أصل.
    prev = db.scalars(select(models.Document).where(
        models.Document.entity_type == "employee",
        models.Document.entity_id == req.employee_id,
        models.Document.document_type_code == type_code,
        models.Document.is_current == True,  # noqa: E712
    )).all()
    for d in prev:
        d.is_current = False

    row = models.Document(
        company_id=req.company_id, entity_type="employee",
        entity_id=req.employee_id, document_type_code=type_code,
        title=title, file_path=doc.file_path, mime="application/pdf",
        version=len(prev) + 1, is_current=True, uploaded_by=actor_id,
        is_issued=True,
        # السرّية من صنف المستند في السجلّ — لا من رأي الموضع.
        is_confidential=is_confidential_output(req, doc),
        source_request_id=req.id,
        reference_no=doc.reference_no,
        checksum_sha256=doc.checksum_sha256,
        signature_version=doc.signature_version,
        generated_at=datetime.utcnow(), generated_by=actor_id,
    )
    db.add(row)
    db.flush()
    return row



def is_confidential_output(req, doc) -> bool:
    """أسرٌّي هذا المستند؟ — **من السجلّ لا من رأي الموضع**.

    ``CANONICAL_DOCUMENTS[od]["confidential"]`` هو الحكم، ويُسنَد إليه نوُع
    الطلب إن كان سرًّيا (``REQGRV`` مثًلا). ولو كُتب الحكم هنا لصار
    تصنيًفا ثانًيا ينحرف عن السجلّ يوم يتغيّر.
    """
    from . import v15_registry as R

    od = getattr(doc, "od_code", None)
    if od and (R.CANONICAL_DOCUMENTS.get(od) or {}).get("confidential"):
        return True
    return bool(getattr(req, "is_confidential", False))


def may_view_document(db, user, doc) -> bool:
    """هل يرى هذا المستخدم هذه الورقة؟

    **وقاعدُة الرؤية هي قاعدُة الطلب نفسها** لا نسخٌة ثانية لها: من يرى
    الطلب يرى ورقته، ومن حُجب عنه الطلب تُحجَب عنه. ولو كُتبت هنا قاعدٌة
    مستقلّة لانحرفت عن ``_get_req`` يوم يتغيّر أحدهما — وهو نمُط «موضعان
    يصفان قاعدة واحدة» الذي أنتج نصف أعطال هذا النظام.
    """
    if not getattr(doc, "is_confidential", False):
        return True
    if user is None:
        return False
    if user.role == "super_admin":
        return True

    from . import models, workflow

    # صاحُب الملف يرى ورقته: الإنذار يُسلَّم له، والتظلّم تظلُّمه.
    if user.employee_id and doc.entity_type == "employee"             and doc.entity_id == user.employee_id:
        return True

    rid = getattr(doc, "source_request_id", None)
    if not rid:
        # **ورقٌة سرّية بلا مصدٍر تُحجَب**: لا تُقرأ قاعدُتها فلا تُخمَّن.
        return False
    req = db.get(models.Request, rid)
    if not req or req.company_id != user.company_id:
        return False
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    for stage in workflow._chain(rt, req):
        if any(u.id == user.id
               for u in workflow.resolve_stage_approvers(db, req, stage)):
            return True
    return False


def visible_documents(db, user, rows):
    """ترشيٌح واحٌد تمرّ به كل قائمة — فلا يبقى بابٌ يُنسى."""
    return [d for d in rows if may_view_document(db, user, d)]
