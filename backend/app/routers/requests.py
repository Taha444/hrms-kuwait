# -*- coding: utf-8 -*-
"""محرّك الطلبات والموافقات: تقديم، اعتماد/رفض، إلغاء المدير، مواعيد، رفع مستندات."""
import os
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy import or_ as sa_or
from sqlalchemy.orm import Session

from .. import request_actions
from .. import (doc_archive, form_schemas, models, module_owned, permissions,
                schemas, workflow)
from ..config import settings
from ..database import get_db
from ..deps import (assert_same_company, audit, get_current_user, require_any_perm,
                    require_perm, scope_company_id)
from ..safe_files import read_limited, unique_path
from ..storage import file_response, key_exists, save_bytes

router = APIRouter(prefix="/requests", tags=["requests"])

# تجاوزات صريحة لحقول إلزامية بأسماء تخص الواجهة لا الـschema.
#
# صارت فارغة بعد أن أصبحت الواجهة تبني كل النماذج من الـschema (SchemaForm):
# لم يعد هناك نوع تختلف مفرداته عن مفردات نموذجه. تُترك موجودة كمَنفَذ لأي نوع
# مستقبلي يحتاج نموذجًا مبرمجًا خاصًا، ويبقى ترتيب المصادر في
# _missing_required_fields كما هو (تجاوز صريح ← schema ← حمولة غير فارغة).
REQUIRED_PAYLOAD_FIELDS: dict[str, list[str]] = {}


def _missing_required_fields(code: str, payload: dict) -> list[str]:
    """الحقول الإلزامية الناقصة في الحمولة.

    ترتيب المصادر:
    1. REQUIRED_PAYLOAD_FIELDS — تجاوز صريح لنوع تستخدم واجهته أسماء حقول تختلف
       عن الـschema. فارغ اليوم: كانت فيه تسعة أنواع ذات نماذج مبرمجة (مثل
       salary_certificate الذي كانت واجهته ترسل addressed_to بينما يسمّيه
       REQCERT purpose) وقد صارت كلها تُبنى من الـschema.
    2. الحقول المعلَّمة required في schema يحمل meta.enforce_required — يُشتق
       تلقائيًا فلا يحتاج النوع تسجيلًا يدويًا هنا.
    3. لا هذا ولا ذاك: يكفي ألا تكون الحمولة فارغة تمامًا.

    لماذا الاشتقاق اختياري (enforce_required) لا شامل: أعلام required في نماذج
    V1.3 القديمة لم تُفرَض على الخادم يومًا، فلم تُختبر مقابل الاستخدام الفعلي
    وبعضها لا يطابقه — REQEOS مثلاً يعلن reason/used_leave_days إلزاميين بينما
    تدفق HR الحقيقي يرسل hire_date/last_day/salary_basis. تعميم الفرض يكسر
    تدفقات عاملة بقيود غير محقَّقة. العلامة تُضاف لكل نوع بعد التحقق من نموذجه
    مقابل استخدامه.

    ملاحظة: قواعد conditional.require يفرضها validate_payload وهي مشروطة
    بـmeta.strict_validation، وهي مقفولة لكل أنواع V1.3 حاليًا.
    """
    def _blank(v):
        return v is None or (isinstance(v, str) and not v.strip())

    required = REQUIRED_PAYLOAD_FIELDS.get(code)
    if required is None:
        schema = form_schemas.get_schema(code)
        if schema and (schema.get("meta") or {}).get("enforce_required"):
            static = [f["code"] for f in schema.get("fields") or []
                      if f.get("required")]
            # القواعد الشرطية: حقل يصير إلزاميًا حسب قيمة حقل آخر — مثل
            # "تصحيح دخول" يستلزم الدخول الصحيح، و"نقل بين فروع" يستلزم الفرع
            # الجديد. تُطبَّق هنا لا في validate_payload لأن الأخير مشروط
            # بـstrict_validation الذي يشغّل معه فحوص أنواع وحدود لم تُفرَض يومًا
            # على أنواع V1.3 ولم تُختبر مقابل حمولاتها الفعلية.
            extra, hidden = form_schemas.conditional_requirements(schema, payload)
            wanted = {*static, *extra} - hidden
            # نرتّبها بترتيب ظهور الحقول في النموذج ليطابق ما يراه المستخدم
            # (extra مجموعة، فبدون ذلك يختلف ترتيب الرسالة بين استدعاء وآخر)
            required = [f["code"] for f in schema.get("fields") or []
                        if f["code"] in wanted]
    if required:
        return [k for k in required if _blank(payload.get(k))]
    # لا حقول إلزامية معلَنة: يكفي ألا تكون الحمولة فارغة تمامًا
    if not payload or all(_blank(v) for v in payload.values()):
        return ["details"]
    return []


# ----------------------------- أنواع الطلبات -----------------------------

@router.get("/status-map")
def status_map(user: models.User = Depends(get_current_user)):
    """ربط الحالات الداخلية بحالات V1.3/V1.4/V1.5 الرسمية (FIX-009 + V1.5)."""
    return workflow.STATUS_MAP


@router.get("/status-model")
def status_model(user: models.User = Depends(get_current_user)):
    """V1.5 Phase 2 — الـ canonical status taxonomy الكامل:
    - request_lifecycle: DRAFT/SUBMITTED/IN_REVIEW/NEEDS_INFO/APPROVED/IN_EXECUTION/COMPLETED
    - document_lifecycle: NOT_REQUIRED/QUEUED/GENERATING/GENERATED/SIGNED/DELIVERED/ARCHIVED
    - step_types: DECISION/VALIDATION/EXECUTION/ACKNOWLEDGEMENT/NOTIFICATION/AUTOMATION
    - internal_to_v15: خريطة الحالات الداخلية القديمة → V1.5 canonical
    """
    from .. import v15_status
    return v15_status.as_dict()


@router.get("/registry")
def registry(user: models.User = Depends(get_current_user)):
    """V1.5 Migration Registry: canonical workflows/documents + legacy aliases.
    يمكن للفرونت-إند استخدامه ليعرض الاسم الجديد الرسمي (WF-XXX) بجانب الكود القديم في
    الطلبات المحفوظة قبل الترحيل."""
    from .. import v15_registry
    return {
        "canonical_workflows": v15_registry.CANONICAL_WORKFLOWS,
        "layouts": v15_registry.LAYOUTS,
        "reports": v15_registry.REPORTS,
        "system_records": v15_registry.SYSTEM_RECORDS,
        "legacy_request_aliases": v15_registry.LEGACY_REQUEST_ALIASES,
        "legacy_template_aliases": v15_registry.LEGACY_PRN_ALIASES,
        "summary": v15_registry.summary(),
    }


def superseded_by(db: Session, company_id: int | None, code: str) -> str | None:
    """المرجع الوحيد لسؤال: هل هذا الكود مُستبدَل بنوع طلب أحدث؟

    يعيد كود البديل إن وُجد فعلًا، أو None.

    القاعدة: الاستبدال حقيقي فقط لو كان هناك RequestType آخر **نشط ومتاح** يمثّل
    نفس الـcanonical workflow. مجرد وجود canonical id في خريطة الـaliases لا يكفي:
    أكواد WF-* هي معرّفات workflow لا أكواد أنواع طلبات، ولا يوجد صف RequestType
    يحملها. منع الإنشاء بناءً على وجودها يعني تعطيل الميزة نهائيًا لا ترحيلها.

    هذه الدالة يستدعيها كلٌّ من كتالوج الإنشاء و submit_request، فيستحيل أن
    يعرض الكتالوج نوعًا يرفضه الخادم — وهو بالضبط ما حدث سابقًا حين حسب كلٌّ
    منهما القاعدة بنفسه.
    """
    from .. import v15_registry
    canonical = v15_registry.resolve_request(code).get("canonical")
    if not canonical or canonical == code:
        return None
    # هل يوجد نوع طلب نشط كوده هو الـcanonical نفسه؟
    replacement = db.scalar(select(models.RequestType).where(
        models.RequestType.code == canonical,
        models.RequestType.is_active == True,  # noqa: E712
        # BKL-05 — ‏IN (NULL, x)‎ لا يطابق صًفا فيه NULL أبًدا في SQL:
        # المقارنة بـNULL تعطي UNKNOWN لا TRUE. والأنواع العامة كلها
        # company_id = NULL، فكان هذا الشرط يستبعد كل بديل عامّ —
        # فتُرجع الدالة None دائًما، ومنع الأنواع المهجورة لا يعمل
        # إطلاًقا وهو يبدو مكتوًبا وصحيًحا.
        sa_or(models.RequestType.company_id.is_(None),
              models.RequestType.company_id == company_id),
    ))
    return canonical if replacement else None


@router.get("/types")
def list_request_types(category: str | None = None, creatable_only: bool = False,
                       grouped: bool = False,
                       user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """كتالوج أنواع الطلبات.

    creatable_only=true → يعيد فقط الأنواع التي يقبلها POST /requests فعليًا.
    نفس المنطق الذي يطبّقه submit_request للرفض (LEGACY_ALIAS_BLOCKED)، حتى لا
    تعرض شاشة "طلب جديد" نوعًا يرفضه الخادم عند الإرسال. الأنواع القديمة تظل
    متاحة بلا الفلتر لأغراض القراءة/الترحيل وعرض الطلبات التاريخية.
    """
    cid = user.company_id
    q = select(models.RequestType).where(models.RequestType.is_active == True)  # noqa: E712
    rows = db.scalars(q).all()

    # V1.5 Phase 5 dual-read: كل نوع طلب يحمل الكود القديم والـ canonical معًا. الفلاجز
    # يقرر أيّهما "الأساسي" (primary):
    # - v15_canonical_display=on: الكود canonical أساسي، والقديم legacy_code
    # - افتراضيًا (default): الكود القديم أساسي، والـ canonical معلومة إضافية
    # - v15_legacy_catalog_hidden=on: يخفي الأنواع التي canonical لها = None (غير مصنّفة)
    from .. import feature_flags as ff
    from .. import v15_registry
    canonical_display = ff.is_enabled(db, cid, ff.V15_CANONICAL_DISPLAY)
    hide_legacy = ff.is_enabled(db, cid, ff.V15_LEGACY_CATALOG_HIDDEN)

    # QA-08 — التكرار في شاشة "طلب جديد" مصدره صفوف قديمة في القاعدة لا التعريفات
    # (54 كوًدا فريًدا بلا أسماء مكرّرة). فبدل تنظيف بيانات لا نراها، نُلغي التكرار
    # على مستوى الهوية: نوعان يحملان نفس canonical أو نفس الاسم هما نوع واحد
    # للمستخدم. يقتصر ذلك على كتالوج الإنشاء؛ الكتالوج الكامل يبقى كما هو
    # للقراءة وعرض الطلبات التاريخية.
    seen, seen_identity, out = set(), set(), []
    for rt in sorted(rows, key=lambda r: (r.code, r.company_id is None)):
        if rt.company_id not in (None, cid):
            continue
        if rt.code in seen:
            continue
        # الموظف (خدمة ذاتية) يرى فقط الأنواع الموسومة له — لا نماذج ADM* الداخلية ولا ما
        # يبدأ من HR/الإدارة بشأنه (P0-06: تنظيم كتالوج الطلبات حسب الدور)
        if user.role == "employee" and not rt.visible_to_employee:
            continue
        # P3-13 — كتالوج الموظف من السجلّ القانوني وحده.
        #
        # ``salary_certificate`` موسوم في السجلّ «Alias retired — استخدم
        # OD-001» ومع ذلك كان يظهر بجانب ``REQCERTSAL`` بالاسم نفسه:
        # «طلب شهادة راتب» مرّتين في قائمة واحدة. فيقف الموظف أمام خيارين
        # لا فرق بينهما، وأيّهما اختار فالنصف الآخر بقيّة ميّتة.
        #
        # والقاعدة تُشتقّ من السجلّ لا تُكتب استثناًء بكود بعينه: كل alias
        # يُتقاعد غًدا يختفي من القائمة يوم يُوسَم، لا يوم يتذكّره أحد.
        _entry = v15_registry.LEGACY_REQUEST_ALIASES.get(rt.code) or {}
        if user.role == "employee" and isinstance(_entry, dict) and                 "retired" in str(_entry.get("note", "")).lower():
            continue
        seen.add(rt.code)
        canonical_info = v15_registry.resolve_request(rt.code)
        canonical_code = canonical_info.get("canonical")
        # كتالوج الإنشاء = ما يقبله POST /requests بالضبط، عبر نفس الدالة
        # (superseded_by) التي يستخدمها submit_request للرفض.
        replacement = superseded_by(db, cid, rt.code)
        if creatable_only and replacement:
            continue
        # P3-15 — موضوع تملكه وحدة مستقلة لا يُعرض كطلب يُنشأ.
        #
        # والقراءة من الإعلان نفسه الذي يمنعه ``create_request``: كتالوج
        # يَعرض ما يرفضه الخادم هو ما وقع حرًفا قبل توحيد ``superseded_by``.
        # ويبقى في الكتالوج الكامل فتُقرأ الطلبات التاريخية المبنية عليه.
        if creatable_only and module_owned.owning_module(rt.code):
            continue
        # V2.2 §12 — الإجراءات الإدارية الداخلية ليست طلبات: إضافة موظف تُنفَّذ
        # من شاشة التعيين، وإشعار نقص المستندات إشعار لا طلب، وتجديد ترخيص
        # الشركة كيانه الشركة لا الموظف. وجودها في "طلب جديد" نصف الفارق بين
        # 54 و29. تبقى في الكتالوج الكامل فتُقرأ الطلبات التاريخية المبنية عليها.
        if creatable_only and canonical_info.get("internal_action"):
            continue
        if creatable_only:
            # الهوية مفتاحان لا واحد، والتكرار يُلغى بأيّهما:
            #   (المسار، النوع الفرعي) — يجمع كودين مختلفين لنفس الخدمة
            #   الاسم — يمسك صًفا قديًما في القاعدة بلا ربط canonical
            # الاكتفاء بالأول يُعيد ظهور المكرر القديم (QA-08)، والاكتفاء
            # بالمسار وحده يُخفي خدمات مختلفة حًقا (استئذان مقابل مغادرة
            # مبكرة يشتركان في WF-003).
            keys = {(canonical_code, canonical_info.get("subtype"))} if canonical_code else set()
            if (rt.name or "").strip():
                keys.add(rt.name.strip())
            if keys & seen_identity:
                continue
            seen_identity |= keys
        # hide_legacy: يخفي الأنواع المُستبدَلة فعلًا فقط. سابقًا كان يخفي كل نوع
        # بلا canonical id — وهو 48 نوعًا من كتالوج V1.3 صالحة تمامًا — فيفرغ
        # القائمة من كل ما يمكن إنشاؤه ويترك المُستبدَل وحده معروضًا.
        if hide_legacy and replacement:
            continue
        entry: dict = {
            "code": rt.code, "name": rt.name, "category": rt.category,
            "chain": rt.approval_chain_json,
            "produces_document": rt.produces_document,
            "canonical_code": canonical_code,
            "canonical_subtype": canonical_info.get("subtype"),
        }
        if canonical_display and canonical_code:
            entry["primary_code"] = canonical_code
            entry["legacy_code"] = rt.code
        else:
            entry["primary_code"] = rt.code
            entry["legacy_code"] = None
        out.append(entry)
    if category:
        out = [x for x in out if x["category"] == category]
    if grouped:
        out = _group_by_canonical(out)
    return out


def _group_by_canonical(entries: list[dict]) -> list[dict]:
    """V2.2 §12 — خدمة واحدة لكل مسار canonical، والنوع الفرعي خيار داخلها.

    ROOT CAUSE للأرقام (47 بدل 29، و25 بدل 15-18): ستة أنواع تمثّل "تغيير
    وظيفي" واحد (وردية/موقع/نقل/ترخيص/عقد/راتب فعلي)، وستة أخرى تمثّل "طلب
    عام". المستخدم يراها اثني عشر خياًرا منفصًلا فيحتار أيّها يخصّه، ثم يختار
    الخطأ فيُرجَع طلبه. المواصفة تعتبرها مساًرا واحًدا بأنواع فرعية.

    لا تُحذف صفوف ولا تُدمج بيانات: التجميع في طبقة العرض وحدها. كل نوع فرعي
    يحتفظ بكوده ونموذجه وسلسلة موافقاته، فالطلبات التاريخية تبقى كما هي،
    والتراجع لا يكلّف إلا إسقاط هذا البارامتر.
    """
    from .. import v15_registry

    groups: dict[str, dict] = {}
    order: list[str] = []
    for e in entries:
        key = e.get("canonical_code") or f"~{e['code']}"
        if key not in groups:
            groups[key] = {**e, "subtypes": []}
            order.append(key)
        groups[key]["subtypes"].append({
            "code": e["code"],
            "label": e["name"],
            "subtype": e.get("canonical_subtype"),
            "produces_document": e.get("produces_document"),
        })

    out = []
    for key in order:
        g = groups[key]
        subs = g["subtypes"]
        if len(subs) > 1 and g.get("canonical_code"):
            # اسم المسار الرسمي أوضح من اسم أول نوع فرعي صادف الترتيب
            info = v15_registry.CANONICAL_WORKFLOWS.get(g["canonical_code"]) or {}
            g["name"] = info.get("name_ar") or g["name"]
            g["name_en"] = info.get("name_en")
        # code يبقى كوًدا صالًحا للإرسال: نوع فرعي واحد ⇒ هو هو
        g["code"] = subs[0]["code"]
        g["has_subtypes"] = len(subs) > 1
        out.append(g)
    return out


@router.get("/types/{code}/schema")
def get_type_schema(code: str,
                    user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """V2.2 §4 — يعيد form_schema_json لنوع الطلب (الواجهة تبني الفورم منه).
    يقبل الـ canonical والـ legacy alias معًا."""
    from .. import form_schemas
    from ..ref_options import fill_schema_options
    s = form_schemas.get_schema(code)
    if not s:
        raise HTTPException(status_code=404, detail="لا يوجد schema مُعرَّف لهذا النوع")
    # V-F — الحقول المرجعية تصل بخياراتها. كانت تُعرض حقل رقم، فيُطلب من
    # الموظف كتابة معرّف قاعدة بيانات لا يعرفه ولا تعرضه أي شاشة.
    return {"code": code, "schema": fill_schema_options(db, s, user.company_id)}


@router.get("/types-schemas")
def list_type_schemas(user: models.User = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """V2.2 §4 — كل schemas الأنواع الرسمية في نداء واحد (للـ SPA الواجهة)."""
    from .. import form_schemas
    from ..ref_options import fill_schema_options
    # الخيارات تُملأ لكل مخطّط، وداخل نطاق شركة السائل وحدها.
    return {code: fill_schema_options(db, s, user.company_id)
            for code, s in form_schemas.SCHEMAS.items()}


@router.post("/types", status_code=201)
def create_request_type(data: schemas.RequestTypeIn,
                        user: models.User = Depends(require_perm("manage_request_types")),
                        db: Session = Depends(get_db)):
    cid = None if user.role == "super_admin" else user.company_id
    rt = models.RequestType(company_id=cid, **data.model_dump())
    db.add(rt)
    db.commit()
    db.refresh(rt)
    return {"ok": True, "id": rt.id}


# ----------------------------- تقديم وعرض -----------------------------

@router.post("", status_code=201)
def submit_request(data: schemas.RequestIn, request: Request,
                   user: models.User = Depends(require_perm("submit_request")),
                   db: Session = Depends(get_db)):
    # تحديد الموظف: العامل يقدّم لنفسه، وذو الصلاحية قد يقدّم لموظف آخر.
    # V2.2 §3 — لو المستخدم الإداري (branch_supervisor مثلًا) بدون employee_id
    # حاول يقدّم "لنفسه" — نرفض برسالة واضحة تدله على السبب.
    emp_id = data.employee_id or user.employee_id
    if not emp_id:
        if not user.employee_id:
            raise HTTPException(
                status_code=400,
                detail=("حسابك غير مرتبط بملف موظف — لا يمكنك تقديم طلب لنفسك. "
                        "اختر موظفًا محددًا من قائمة 'تقديم نيابة عن'.")
            )
        raise HTTPException(status_code=400, detail="يجب تحديد الموظف")
    emp = db.get(models.Employee, emp_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    assert_same_company(user, emp.company_id, db=db)

    # التقديم باسم موظف آخر مقصور على HR والمندوب (permissions.ON_BEHALF_ROLES).
    # كان الفحص الوحيد هنا assert_same_company، فأي حساب يملك submit_request
    # يقدر يفتح طلبًا باسم أي موظف في شركته — بما فيهم من هم أعلى منه — عبر POST
    # مباشر، بلا حاجة حتى لصلاحية رؤية الموظفين.
    if emp_id != user.employee_id and not permissions.can_submit_on_behalf(user.role):
        raise HTTPException(
            status_code=403,
            detail="لا يمكنك تقديم طلب باسم موظف آخر — التقديم نيابةً عن الموظفين "
                   "مقصور على الشؤون القانونية/HR والمندوب. يمكنك تقديم طلباتك "
                   "الخاصة فقط."
        )

    # الإنذار طلب يُوجَّه لموظف بعينه — ونفس قاعدة الإعفاء تحكمه هنا وفي
    # تسجيل الحدث المباشر: permissions.may_receive_warning هو المصدر الواحد،
    # فلا يُسدّ باب ويُترك الآخر.
    if data.request_type_code in ("ADMWARN", "ADMVIO"):
        holder = db.scalar(select(models.User).where(models.User.employee_id == emp.id))
        if holder and not permissions.may_receive_warning(holder.role):
            raise HTTPException(
                status_code=403,
                detail="لا يجوز توجيه إنذار أو جزاء لصاحب هذا الدور")

    rt = workflow.get_request_type(db, emp.company_id, data.request_type_code)
    if not rt:
        raise HTTPException(status_code=404, detail="نوع الطلب غير معرّف")

    # R6-A §5 — Backend Allowlist: نرفض POST على كود مُستبدَل بنوع أحدث متاح،
    # لأن إخفاءه من الكتالوج وحده لا يكفي (واجهة قديمة أو API خارجي قد ينشئ مباشرة).
    #
    # الشرط الحاسم: البديل يجب أن يكون **موجودًا فعلًا** كنوع طلب نشط. الرفض بمجرد
    # وجود canonical id في خريطة الـaliases كان يمنع إنشاء leave/salary_certificate/
    # exit_permission/advance/loan نهائيًا — فأكواد WF-* معرّفات workflow لا أنواع
    # طلبات، ولا يوجد صف RequestType يحملها ليحلّ محلها. superseded_by يفرض هذا
    # الشرط، وهو نفسه ما يستخدمه كتالوج الإنشاء فلا يتباعد الاثنان.
    replacement = superseded_by(db, emp.company_id, data.request_type_code)
    if replacement:
        raise HTTPException(status_code=400, detail={
            "code": "LEGACY_ALIAS_BLOCKED",
            "message": f"الكود «{data.request_type_code}» قديم — استخدم «{replacement}» بدلاً منه.",
            "canonical": replacement,
            "legacy_code": data.request_type_code,
        })

    # V2.2 §4 Form Schema Engine: التحقق من الحقول والقيود الشرطية والحدود
    from .. import form_schemas
    # الإعفاء يبقى للأكواد ذات النموذج المبرمج (مفرداتها من الواجهة لا الـschema).
    # القائمة فارغة الآن لأن كل النماذج تُبنى من الـschema.
    ui_defined = data.request_type_code in REQUIRED_PAYLOAD_FIELDS
    schema_errors = form_schemas.validate_payload(
        data.request_type_code, data.payload_json or {},
        strict=False if ui_defined else None,
    )
    if schema_errors:
        raise HTTPException(status_code=400,
                            detail={"errors": schema_errors, "message": schema_errors[0]})

    # منع تقديم طلب فارغ يدخل مسار الاعتماد الفعلي (QA-P0-WF-01)
    missing = _missing_required_fields(data.request_type_code, data.payload_json or {})
    if missing:
        labels = [workflow.PAYLOAD_KEY_LABELS_AR.get(k, workflow._humanize_key(k)) for k in missing]
        # نفس شكل أخطاء المحرّك أعلاه: الحقل الناقص شرط واحد يُبلَّغ بشكلين كان
        # على الواجهة أن تفهمهما معًا. الأنواع ذات enforce_required يمسكها المحرّك
        # قبل الوصول هنا، فهذا المسار للأنواع بلا schema مفروض.
        raise HTTPException(status_code=400, detail={
            "errors": [f"{k}: {lbl} مطلوب" for k, lbl in zip(missing, labels)],
            "message": f"الحقول التالية مطلوبة: {'، '.join(labels)}",
        })

    # تحقّق منطق التواريخ لطلبات الإجازة
    if data.request_type_code == "leave":
        p = data.payload_json or {}
        sd, ed = p.get("start_date"), p.get("end_date")
        if sd and ed and str(ed) < str(sd):
            raise HTTPException(status_code=400, detail="تاريخ نهاية الإجازة قبل بدايتها")

    req = workflow.create_request(db, emp, user, rt, data.payload_json)
    audit(db, user, "submit_request", "request", req.id, detail=rt.code,
          request=request, company_id=emp.company_id,
          correlation_id=f"req:{req.id}",
          after={"status": req.status, "current_stage": req.current_stage,
                "type": rt.code})
    db.commit()
    st = workflow.status_info(req.status)
    return {"ok": True, "id": req.id, "status": req.status, "status_label": st["label"],
            "current_stage": req.current_stage}


@router.get("/mine")
def my_requests(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """طلباتي (للعامل) — الطلبات التي قدّمها أو الخاصة بملفه."""
    q = select(models.Request).where(
        (models.Request.requester_user_id == user.id)
        | (models.Request.employee_id == (user.employee_id or -1))
    )
    return [_serialize(db, r, viewer=user) for r in db.scalars(q.order_by(models.Request.created_at.desc())).all()]


@router.get("/inbox")
def approval_inbox(company_id: int | None = None,
                   user: models.User = Depends(
                       require_any_perm(*permissions.APPROVAL_PERMS, "process_delegate_tasks")),
                   db: Session = Depends(get_db)):
    """بانتظار موافقتي — طلبات مرحلتها الحالية موجّهة لهذا المستخدم."""
    cid = scope_company_id(user, company_id)
    q = select(models.Request).where(models.Request.status.in_(
        ["pending", "awaiting_signature", "awaiting_delegate", "ready_for_pickup"]))
    if cid is not None:
        q = q.where(models.Request.company_id == cid)
    out = []
    for req in db.scalars(q.order_by(models.Request.created_at.desc())).all():
        rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
        if not rt:
            continue
        chain = workflow._chain(rt, req)
        if req.current_stage >= len(chain):
            continue
        stage = chain[req.current_stage]
        if workflow.can_decide(db, req, user, stage, rt=rt):
            out.append(_serialize(db, req, viewer=user))
    return out


@router.get("/{req_id}")
def get_request(req_id: int, user: models.User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    req = _get_req(db, user, req_id)
    return _serialize(db, req, full=True, viewer=user)


# ----------------------------- قرارات -----------------------------

@router.post("/{req_id}/decide")
def decide(req_id: int, data: schemas.ApprovalDecisionIn, request: Request,
           user: models.User = Depends(
               require_any_perm(*permissions.APPROVAL_PERMS, "process_delegate_tasks")),
           db: Session = Depends(get_db)):
    req = _get_req(db, user, req_id)
    if req.status not in ("pending",):
        raise HTTPException(status_code=409, detail="لا يمكن اتخاذ قرار في هذه الحالة")
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    # V2.2 §4.5 (AP-01) — القرار يحتاج صلاحية مجاله لا صلاحية عامة.
    # حارس المسار يقبل approve_request أو process_delegate_tasks، وهو حارس
    # واحد لكل الأنواع: من يعتمد إجازة يصل لاعتماد خصم وتظلّم وإنهاء خدمة.
    # الفحص هنا لأن المجال لا يُعرف إلا بعد قراءة نوع الطلب.
    from ..deps import get_user_perms
    chain = workflow._chain(rt, req)
    _stage_now = chain[req.current_stage] if req.current_stage < len(chain) else {}
    # AC-03 — خطوة التحقق تُنجَز بـcomplete_validation؛ والقرار وحده يحتاج
    # صلاحية مجاله. الخلط بينهما يمنح من يتحقّق سلطة من يقرّر.
    if not permissions.can_complete_stage(user.role, get_user_perms(user, db),
                                          rt.category if rt else None,
                                          _stage_now.get("step_type")):
        raise HTTPException(status_code=403, detail=(
            "لا تملك صلاحية إتمام هذه الخطوة — "
            f"المطلوب: {permissions.decision_permission(rt.category if rt else None)}"
        ))
    # P0-#6 — منع stale action: current_stage غير صالح (بره النطاق) في حالة pending
    if req.current_stage < 0 or req.current_stage >= len(chain):
        raise HTTPException(status_code=409, detail=(
            f"حالة غير متناسقة: current_stage={req.current_stage} خارج نطاق السلسلة "
            f"(طول {len(chain)}). أعد فتح الطلب."
        ))
    stage = chain[req.current_stage]
    # P0-#6 + FIX — منع double action داخل نفس الدورة فقط.
    # بعد resubmit تُسجَّل علامة (stage_order=-1, decision='resubmitted')؛ أي قرار قديم
    # قبلها يخص دورة سابقة ولا يمنع اتخاذ قرار جديد. بدون هذا الفلتر كان الطلب المُعاد
    # تقديمه يرجع 409 "اتخذت قرارًا مسبقًا" فيتجمّد للأبد.
    from sqlalchemy import select
    last_resubmit = db.scalar(select(models.RequestApproval).where(
        models.RequestApproval.request_id == req.id,
        models.RequestApproval.decision == "resubmitted",
    ).order_by(models.RequestApproval.id.desc()))

    dup_q = select(models.RequestApproval).where(
        models.RequestApproval.request_id == req.id,
        models.RequestApproval.stage_order == req.current_stage,
        models.RequestApproval.approver_user_id == user.id,
        models.RequestApproval.decision.in_(("approved", "rejected", "returned")),
    )
    if last_resubmit:
        # الدورة الحالية = القرارات المُسجَّلة بعد آخر إعادة تقديم فقط
        dup_q = dup_q.where(models.RequestApproval.id > last_resubmit.id)

    already_decided = db.scalar(dup_q)
    if already_decided:
        raise HTTPException(status_code=409,
                          detail="اتخذت قرارًا في هذه المرحلة مسبقًا — لا يمكن التكرار")
    # QA-01 — نفرّق بين المعتمِد الفعلي والمتجاوِز إداريًا: الأول مسار عادي،
    # والثاني استثناء يُسجَّل باسمه في التدقيق لا يمر بصمت.
    is_real_approver = workflow.is_stage_approver(db, req, user, stage)
    if not is_real_approver:
        if not workflow.may_override(db, user, rt):
            raise HTTPException(status_code=403, detail="لست المعتمِد لهذه المرحلة")
        audit(db, user, "approval_override", "request", req.id,
              detail=(f"stage={req.current_stage} ({stage.get('label') or stage.get('role')}) "
                      f"decision={data.decision}"),
              request=request, correlation_id=f"req:{req.id}",
              before={"stage_role": stage.get("role")},
              after={"decided_by_override": True, "decision": data.decision})

    # QA-01 — منع الاعتماد المتسلسل بنفس الحساب: من اعتمد المرحلة السابقة لا
    # يعتمد التالية، وإلا صارت سلسلة الاعتماد توقيًعا واحًدا بأسماء متعددة.
    if data.decision == "approved" and req.current_stage > 0:
        prev = db.scalar(
            select(models.RequestApproval)
            .where(models.RequestApproval.request_id == req.id,
                   models.RequestApproval.stage_order == req.current_stage - 1,
                   models.RequestApproval.decision == "approved")
            .order_by(models.RequestApproval.id.desc())
        )
        if prev and prev.approver_user_id == user.id:
            raise HTTPException(
                status_code=409,
                detail="اعتمدت المرحلة السابقة بنفسك — لا يجوز اعتماد مرحلتين متتاليتين "
                       "بنفس الحساب")
    # V2.2 §5 — منع الاعتماد الذاتي فقط للطلبات التي تخصّ الموظف نفسه (ملفه الشخصي).
    # HR/الإدارة الذين يبدأون طلبات نيابة عن موظف آخر يبقون قادرين على اعتماد مرحلتهم
    # في السلسلة (لأنها ليست عن ملفهم). super_admin يمرّ للطوارئ.
    if data.decision == "approved" and stage.get("kind") not in ("employee_ack", "acknowledgment"):
        if user.role != "super_admin" and user.employee_id and req.employee_id == user.employee_id:
            raise HTTPException(status_code=403,
                                detail="لا يمكنك اعتماد طلب يخص ملفك الشخصي")
    if data.decision not in ("approved", "rejected", "returned"):
        raise HTTPException(status_code=400, detail="قرار غير صالح")
    if data.decision == "returned":
        # إرجاع للتصحيح متاح فقط بالمرحلتين الأولى والثانية، ويلزم توضيح السبب (QA-P2-WF-03)
        if req.current_stage >= 2:
            raise HTTPException(status_code=400, detail="الإرجاع للتصحيح متاح فقط في المرحلتين الأولى والثانية")
        if not (data.note and data.note.strip()):
            raise HTTPException(status_code=400, detail="يجب توضيح سبب الإرجاع في الملاحظة")
    if stage.get("kind") == "delegate_exit" and data.decision == "approved":
        raise HTTPException(
            status_code=400,
            detail="هذه المرحلة تكتمل برفع إذن المغادرة (documents) لا بالاعتماد المباشر",
        )
    # P0-#7 — capture before-state for audit trail
    before = {"status": req.status, "current_stage": req.current_stage}
    req = workflow.decide(db, req, user, data.decision, data.note, rt)
    audit(db, user, f"request_{data.decision}", "request", req.id,
          detail=data.note, request=request, company_id=req.company_id,
          correlation_id=f"req:{req.id}",
          # BKL-02 — السبب حقل مُهيكَل لا نصّ حرّ في detail: من يبحث عن
          # «لماذا رُفض» يحتاج أن يُصفّي عليه لا أن يقرأ ألف سطر.
          reason=data.note, result="success",
          before=before,
          after={"status": req.status, "current_stage": req.current_stage})
    # BKL-02 — سطر التدقيق يُضاف إلى الجلسة ولا يُلتزَم. و``workflow.decide``
    # يلتزم داخله **قبل** إضافته، فيُحفظ القرار ويُهمَل سجلّه: قرار نُفِّذ
    # بلا أثر يقول من اتّخذه ومتى ومن أي عنوان. وهو أخطر من غياب التدقيق
    # كلّه، لأن السجلّ يبدو كامًلا وفيه فجوة لا تُرى.
    db.commit()
    st = workflow.status_info(req.status)
    return {"ok": True, "status": req.status, "status_label": st["label"], "current_stage": req.current_stage}


@router.post("/{req_id}/cancel")
def cancel(req_id: int, request: Request, note: str | None = None,
           user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = _get_req(db, user, req_id)
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    before = {"status": req.status, "current_stage": req.current_stage}
    try:
        req = workflow.cancel(db, req, user, note, rt)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    audit(db, user, "request_cancel", "request", req.id,
          detail=note, request=request, company_id=req.company_id,
          correlation_id=f"req:{req.id}", before=before, reason=note,
          after={"status": req.status})
    db.commit()   # BKL-02 — بلا التزام يُهمَل سطر التدقيق ويبقى الإلغاء بلا أثر
    return {"ok": True, "status": req.status}


@router.post("/{req_id}/resubmit")
def resubmit_request(req_id: int, request: Request, data: dict | None = None,
                     user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """إعادة تقديم طلب بعد إرجاعه للتصحيح (V1.4 NEEDS_INFO): يقبل حمولة معدّلة اختيارية،
    ويعيد الطلب لمرحلة الاعتماد الأولى دون إنشاء طلب جديد."""
    req = _get_req(db, user, req_id)
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    before = {"status": req.status, "current_stage": req.current_stage}
    try:
        req = workflow.resubmit(db, req, user, (data or {}).get("payload_json"), rt)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit(db, user, "request_resubmit", "request", req.id,
          request=request, company_id=req.company_id,
          correlation_id=f"req:{req.id}", before=before,
          after={"status": req.status, "current_stage": req.current_stage})
    db.commit()   # BKL-02 — نفس السبب: إعادة التقديم تُحفَظ وسجلّها يُهمَل
    return {"ok": True, "status": req.status, "current_stage": req.current_stage}


# ----------------------------- مواعيد ومستندات -----------------------------

@router.post("/{req_id}/appointment")
def set_appointment(req_id: int, data: schemas.AppointmentIn, request: Request,
                    user: models.User = Depends(require_any_perm(*permissions.APPROVAL_PERMS)),
                    db: Session = Depends(get_db)):
    """يحدد HR موعد مراجعة العامل للتوقيع (الحالة awaiting_signature)."""
    req = _get_req(db, user, req_id)
    appt = models.Appointment(company_id=req.company_id, request_id=req.id,
                              employee_id=req.employee_id, scheduled_at=data.scheduled_at,
                              location=data.location, created_by=user.id)
    db.add(appt)
    from ..notifications import notify_employee_self
    notify_employee_self(
        db, req.employee_id, type="appointment",
        title="موعد مراجعة للتوقيع",
        detail=(f"برجاء مراجعة شؤون الموظفين يوم {data.scheduled_at:%Y-%m-%d} الساعة "
                f"{data.scheduled_at:%H:%M} في {data.location or 'مقر الشركة'} لإتمام طلبك."),
        related_entity_type="request", related_entity_id=req.id,
        dedup_key=f"appt:{appt.request_id}:{int(data.scheduled_at.timestamp())}",
    )
    audit(db, user, "set_appointment", "request", req.id, request=request, company_id=req.company_id)
    db.commit()
    return {"ok": True}


@router.post("/{req_id}/documents")
async def upload_request_document(req_id: int, request: Request, kind: str = Form(...),
                                  file: UploadFile = File(...),
                                  user: models.User = Depends(get_current_user),
                                  db: Session = Depends(get_db)):
    """رفع مستند الطلب (signed_scan من HR / exit_permit من المندوب) ويقدّم سير العمل."""
    req = _get_req(db, user, req_id)
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)

    if kind not in ("signed_scan", "exit_permit", "generated_pdf", "attachment"):
        raise HTTPException(status_code=400, detail="نوع مستند غير صالح")
    # AWS-01 — عبر طبقة التخزين لا على القرص مباشرة
    fpath = save_bytes(await read_limited(file), "requests", file.filename,
                       prefix=f"req{req.id}_{kind}_")
    existing = db.scalars(select(models.RequestDocument).where(
        models.RequestDocument.request_id == req.id, models.RequestDocument.kind == kind)).all()
    db.add(models.RequestDocument(request_id=req.id, kind=kind, file_path=fpath,
                                  version=len(existing) + 1, uploaded_by=user.id))
    db.flush()

    # تقديم سير العمل حسب نوع المستند
    if kind == "signed_scan" and req.status == "awaiting_signature":
        workflow.upload_signed_scan_done(db, req, rt)
    elif kind == "exit_permit" and req.status == "awaiting_delegate":
        if not (user.role == "delegate" or user.role in workflow.CANCEL_ROLES):
            raise HTTPException(status_code=403, detail="رفع إذن المغادرة من صلاحية المندوب")
        workflow.upload_exit_permit_done(db, req, rt)
    else:
        db.commit()

    audit(db, user, "upload_request_doc", "request", req.id, detail=kind, request=request, company_id=req.company_id)
    db.commit()
    return {"ok": True, "status": req.status}


@router.post("/{req_id}/received")
def mark_received(req_id: int, user: models.User = Depends(require_any_perm(*permissions.APPROVAL_PERMS)),
                  db: Session = Depends(get_db)):
    """تسجيل استلام العامل للمستند (يُغلق طلب شهادة الراتب)."""
    req = _get_req(db, user, req_id)
    if req.status != "ready_for_pickup":
        raise HTTPException(status_code=409, detail="الطلب ليس جاهزًا للاستلام")
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    workflow.mark_pickup_received(db, req, rt)
    return {"ok": True, "status": req.status}


@router.get("/{req_id}/document/{kind}")
def download_request_document(req_id: int, kind: str,
                              user: models.User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    req = _get_req(db, user, req_id)
    doc = db.scalar(select(models.RequestDocument).where(
        models.RequestDocument.request_id == req.id, models.RequestDocument.kind == kind
    ).order_by(models.RequestDocument.version.desc()))
    # ثلاث حالات كانت تُعطي الرسالة نفسها، والفرق بينها هو التشخيص:
    #  - لا صفّ:        المستند لم يُولَّد أصًلا
    #  - صفّ بلا مسار:  التوليد بدأ ولم يكتمل
    #  - مسار بلا ملف:  **الملف فُقد** — والسبب المعتاد قرص حاوية مؤقّت
    #                   يُمحى مع كل نشرة، والسجلّ يبقى في القاعدة
    # ومن يقرأ «غير موجود» يظنّ أنه لم يُطلب؛ ومن يقرأ «فُقد» يعرف أن
    # عليه إعادة التوليد لا إعادة المحاولة.
    if not doc:
        raise HTTPException(status_code=404,
                            detail="لم يُولَّد هذا المستند لهذا الطلب بعد")
    if not doc.file_path:
        raise HTTPException(status_code=404,
                            detail="سجلّ المستند موجود بلا ملف — لم يكتمل توليده")
    if not key_exists(doc.file_path):
        raise HTTPException(
            status_code=410,
            detail=("ملف المستند مفقود من التخزين رغم وجود سجلّه — "
                    "أعد توليد المستند. وإن تكرّر ذلك بعد كل نشرة فالتخزين "
                    "على قرص مؤقّت ويجب نقله إلى تخزين دائم."))
    if doc.file_path.endswith(".pdf"):
        media = "application/pdf"
    elif doc.file_path.endswith(".html"):
        media = "text/html"
    else:
        media = "application/octet-stream"
    return file_response(doc.file_path, media_type=media,
                        filename=os.path.basename(doc.file_path))


# ----------------------- دورة حياة الطباعة/الأرشفة (FIX-008) -----------------------

def _latest_doc(db: Session, req_id: int, kind: str) -> models.RequestDocument:
    doc = db.scalar(select(models.RequestDocument).where(
        models.RequestDocument.request_id == req_id, models.RequestDocument.kind == kind
    ).order_by(models.RequestDocument.version.desc()))
    if not doc:
        raise HTTPException(status_code=404, detail="المستند غير موجود")
    return doc


@router.post("/{req_id}/document/{kind}/mark-printed")
def mark_document_printed(req_id: int, kind: str, request: Request,
                          user: models.User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """READY_TO_PRINT → PRINTED: تسجّل من طبع المستند الفعلي ومتى.
    V2.2 §13: يفشل بـ 409 لو ملف المستند غير موجود على القرص — لا نسجل نجاح على عمل لم يحصل."""
    import os
    req = _get_req(db, user, req_id)
    doc = _latest_doc(db, req.id, kind)
    if doc.print_status not in ("ready_to_print", "printed"):
        raise HTTPException(status_code=409, detail="لا يمكن تسجيل الطباعة في هذه الحالة")
    if not (doc.file_path and key_exists(doc.file_path)):
        raise HTTPException(status_code=409,
                            detail="ملف المستند غير موجود على القرص — لا يمكن تسجيل الطباعة")
    doc.print_status = "printed"
    doc.printed_at = datetime.now()
    doc.printed_by = user.id
    audit(db, user, "print_document", "request", req.id, detail=kind, request=request, company_id=req.company_id)
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    if rt:
        from ..notifications import notify_from_template
        notify_from_template(
            db, code="NTF-044", assignee_user_id=user.id, company_id=req.company_id,
            context={"document_name": rt.name, "actor_name": user.full_name or user.role},
            related_entity_type="request", related_entity_id=req.id,
            dedup_key=f"print_done:{doc.id}",
        )
    db.commit()
    return {"ok": True, "print_status": doc.print_status}


@router.post("/{req_id}/document/{kind}/mark-filed")
def mark_document_filed(req_id: int, kind: str, request: Request,
                        user: models.User = Depends(require_perm("upload_documents")),
                        db: Session = Depends(get_db)):
    """PRINTED → FILED: أرشفة النسخة المعتمدة في ملف الموظف (ورقي/إلكتروني).
    V2.2 §13: يشترط وجود الملف فعلاً قبل تسجيل الأرشفة."""
    import os
    req = _get_req(db, user, req_id)
    doc = _latest_doc(db, req.id, kind)
    if doc.print_status != "printed":
        raise HTTPException(status_code=409, detail="يجب تسجيل الطباعة أولًا قبل الأرشفة")
    if not (doc.file_path and key_exists(doc.file_path)):
        raise HTTPException(status_code=409,
                            detail="ملف المستند غير موجود على القرص — لا يمكن تسجيل الأرشفة")
    doc.print_status = "filed"
    doc.filed_at = datetime.now()
    doc.filed_by = user.id
    audit(db, user, "file_document", "request", req.id, detail=kind, request=request, company_id=req.company_id)
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    if rt:
        # P1-03 — الأرشفة بقاعدة واحدة يستدعيها التوليد وهذه الخطوة مًعا.
        #
        # كانت القاعدة مكتوبة هنا وحدها، والمستند لا يدخل الملف قبل أن
        # يضغط أحد «طُبع» ثم «أُرشف». صار الدخول عند الصدور، وتبقى هذه
        # الخطوة لتسجيل الأثر الورقي — و``archive_request_document``
        # idempotent بالمرجع فلا تُنشئ صًفا ثانًيا لنفس الورقة.
        doc_archive.archive_request_document(
            db, req, doc, title=rt.name, actor_id=user.id)
        from ..notifications import notify_from_template
        notify_from_template(
            db, code="NTF-045", assignee_user_id=user.id, company_id=req.company_id,
            context={"document_name": rt.name},
            related_entity_type="request", related_entity_id=req.id,
            dedup_key=f"file_done:{doc.id}",
        )
    db.commit()
    return {"ok": True, "print_status": doc.print_status}


# ----------------------------- مساعدات -----------------------------

def _get_req(db: Session, user: models.User, req_id: int) -> models.Request:
    req = db.get(models.Request, req_id)
    if not req:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    assert_same_company(user, req.company_id, db=db)
    is_self = req.employee_id == user.employee_id
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)

    # الطلبات السرّية (شكاوى/تظلمات، FIX-014): الاطلاع يقتصر على الإدارة العليا،
    # معتمدي المرحلة الفعليين عبر السلسلة كاملة (مثل الشؤون القانونية)، وصاحب الطلب نفسه —
    # لا تجاوز إداري عام حتى لا يطّلع المسؤول المشتكى به على الشكوى ضده.
    if rt and rt.is_confidential:
        if user.role == "super_admin" or is_self:
            return req
        for stage in workflow._chain(rt, req):
            if any(u.id == user.id for u in workflow.resolve_stage_approvers(db, req, stage)):
                return req
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    # خدمة ذاتية: من لا يعتمد/يعالج الطلبات يرى طلباته هو فقط (لا طلبات الزملاء)
    from ..permissions import has_permission
    from ..deps import get_user_perms
    perms = get_user_perms(user, db)
    # AC-03/AP-01 — "معالج الطلبات" لم يعد يُعرَّف بالصلاحية العامة المهجورة:
    # نزعها من الأدوار كان يُخفي الطلب عن معتمِديه الفعليين (404) لأن كل من
    # يعتمد صار يملك صلاحية مجاله لا الصلاحية العامة.
    is_handler = (user.role == "super_admin"
                  or any(has_permission(user.role, perms, x)
                         for x in permissions.APPROVAL_PERMS)
                  or has_permission(user.role, perms, "process_delegate_tasks"))
    if not is_handler and not is_self:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    return req


ROLE_AR = {
    "super_admin": "الإدارة العليا", "company_owner": "صاحب الشركات",
    "company_manager": "المدير العام", "branch_supervisor": "مسؤول الفرع",
    "hr": "شؤون الموظفين", "delegate": "المندوب", "employee": "الموظف",
}


_LEAVE_CODES = {"leave", "REQVAC", "REQSICK", "annual_leave", "sick_leave",
                "unpaid_leave", "hajj_leave", "maternity_leave"}


def _mask_leave_dates_for_employee(payload: dict, request_type_code: str,
                                   viewer_role: str, is_own_request: bool) -> dict:
    """PILOT-P0-3 + P0-#14: يخفي تواريخ الإجازة من عرض الموظف عن طلبه الخاص.

    القاعدة: الموظف/الشخص صاحب الطلب يرى type/status/reason فقط دون
    start_date/end_date/days/return_date. الـ HR والمدير والمسؤول يرون كل شيء
    لتخطيط الجداول.

    P0-#14 — يُطبَّق أيضًا على الأدوار الإدارية اللي بيقدّموا طلبات لأنفسهم
    (HR/Manager/Supervisor مربوطين بـEmployee record) — البيانات تكون حسّاسة
    حتى لو الشخص إداري.

    يشمل كل canonical + legacy leave codes.
    """
    if not (request_type_code in _LEAVE_CODES and is_own_request):
        return payload
    HIDDEN = {"start_date", "end_date", "days", "return_date"}
    return {k: v for k, v in (payload or {}).items() if k not in HIDDEN}


def _serialize(db: Session, req: models.Request, full: bool = False,
               viewer: "models.User | None" = None) -> dict:
    emp = db.get(models.Employee, req.employee_id)
    rt = workflow.get_request_type(db, req.company_id, req.request_type_code)
    chain = workflow._chain(rt, req) if rt else []
    st = workflow.status_info(req.status)
    # V1.5 canonical resolver: يعرض الكود الجديد للطلب بجانب الكود القديم في seed
    from .. import v15_registry
    canonical_info = v15_registry.resolve_request(req.request_type_code)
    # PILOT-P0-3 + P0-#14: إخفاء تواريخ الإجازة من عرض الشخص صاحب الطلب.
    # يشمل الموظف العادي + الأدوار الإدارية اللي مربوطة بـEmployee record
    # وبتقدّم طلب لنفسها (self-request) — HR/Manager/Supervisor.
    # HR/Manager يرون بيانات موظفين آخرين كاملة، بس ما يرون بياناتهم الخاصة.
    is_own = bool(viewer and viewer.employee_id
                  and viewer.employee_id == req.employee_id)
    payload_view = _mask_leave_dates_for_employee(
        req.payload_json or {}, req.request_type_code,
        viewer.role if viewer else "", is_own,
    )
    # P1-#19 — can_decide flag للـUI: الأزرار تظهر فقط للموافق الحالي.
    # Backend authoritative — الـfrontend يعتمد عليه لغلق الأزرار بدل حساب محلي.
    can_current_user_decide = False
    if viewer and req.status == "pending" and req.current_stage < len(chain):
        try:
            can_current_user_decide = workflow.can_decide(
                db, req, viewer, chain[req.current_stage], rt=rt
            )
        except Exception:
            can_current_user_decide = False

    data = {
        "id": req.id, "type": req.request_type_code,
        "type_name": rt.name if rt else req.request_type_code,
        "canonical_workflow": canonical_info.get("canonical"),  # V1.5 WF-XXX (قد يكون None)
        "canonical_subtype": canonical_info.get("subtype"),
        "employee_id": req.employee_id, "employee_name": emp.name if emp else None,
        "status": req.status, "status_code": st["code"], "status_label": st["label"],
        "status_v15": st.get("v15"),  # V1.5 canonical (IN_REVIEW/NEEDS_INFO/...)
        "current_stage": req.current_stage,
        "total_stages": len(chain),
        "payload": payload_view, "payload_masked": is_own and payload_view != (req.payload_json or {}),
        "created_at": req.created_at,
        # P1-#19 — الـUI تخفي أزرار الاعتماد لو false (بدل عرضها ومنع الـclick بـ403)
        "can_current_user_decide": can_current_user_decide,
        # APP-01 — شريط الإجراءات يُبنى من هنا. الواجهة تعرض ما في القائمة
        # ولا تحسب صلاحية: الحساب في مكانين ينحرف أحدهما عن الآخر، وهو
        # سبب اختفاء الأزرار عن المعتمِد الفعليّ.
        "allowed_actions": request_actions.allowed_actions(db, req, viewer),
        # ولمن لا أفعال له: السبب بدل الصمت — من ينتظر دوره يحتاج أن يعرف
        # أنه ينتظر لا أن يظنّ الشاشة معطَّلة.
        "no_actions_reason": request_actions.why_not(db, req, viewer),
    }
    if full:
        approvals = db.scalars(select(models.RequestApproval).where(
            models.RequestApproval.request_id == req.id)
            .order_by(models.RequestApproval.decided_at)).all()
        # كل قرار حسب مرحلته (للعرض: من قرّر، متى، وبأي ملاحظة) بصرف النظر عن نوع القرار
        by_stage = {a.stage_order: a for a in approvals}
        # القرار السلبي لكل مرحلة (رفض أو إرجاع للتصحيح، QA-P2-WF-03) — يحدد لون/نص المرحلة بدقة
        negative = {a.stage_order: a.decision for a in approvals if a.decision in ("rejected", "returned")}
        docs = db.scalars(select(models.RequestDocument).where(
            models.RequestDocument.request_id == req.id)).all()

        def _name(uid):
            u = db.get(models.User, uid) if uid else None
            return (u.full_name or ROLE_AR.get(u.role, u.role)) if u else None

        # حالة كل مرحلة لرسم المسار الهرمي بوضوح
        stages = []
        for i, st in enumerate(chain):
            ap = by_stage.get(i)
            if req.status == "completed":
                state = "done"
            elif req.status == "cancelled":
                state = "done" if i < req.current_stage else ("cancelled" if i == req.current_stage else "skipped")
            elif i in negative:
                state = negative[i]
            elif i < req.current_stage:
                state = "done"
            elif i == req.current_stage:
                state = "current"
            else:
                state = "pending"
            # P8-31 — التسمية تقول من يتصرّف فعًلا، لا من نصّ التعريف.
            #
            # السقوط رسمي: مرحلة «المسؤول المباشر» تنتقل إلى مسؤول الفرع
            # حين لا يكون للموظف مدير مباشر. لكن الشاشة كانت تعرض الدور
            # المُعلَن، فيقرأ المستخدم «بانتظار المسؤول المباشر» وينتظر من
            # لن يتصرّف — والفعل عند غيره.
            #
            # ويُحسب للمرحلة الجارية وحدها: الماضية يحكيها سجلّ القرارات
            # بدورها الفعلي، والقادمة لم يُحسم من يتولّاها بعد.
            effective_role, blocked = st.get("role"), None
            if state == "current":
                actual = workflow.resolve_stage_approvers(db, req, st)
                roles = {u.role for u in actual if u.role}
                if roles and st.get("role") not in roles:
                    effective_role = sorted(roles)[0]
                elif not actual:
                    # مرحلة بلا معتمِد: الطلب واقف ولا أحد يستطيع تحريكه.
                    # وكانت الشاشة تعرضها كغيرها — «بانتظار اعتماد مسؤول
                    # الفرع» — فينتظر الموظف من لا وجود له، ولا يسأل أحد
                    # عمّا يبدو ماضًيا في طريقه. والتنبيه يذهب لشؤون
                    # الموظفين (workflow._warn_unassigned_stage) وحدهم.
                    blocked = "لا معتمِد مرتبط بهذه المرحلة — تواصل مع شؤون الموظفين"
            stages.append({
                "order": i, "label": st.get("label"), "role": st.get("role"),
                "role_label": ROLE_AR.get(st.get("role"), st.get("role")),
                "effective_role": effective_role,
                "effective_role_label": ROLE_AR.get(effective_role, effective_role),
                "delegated_from": (st.get("role")
                                   if effective_role != st.get("role") else None),
                "blocked_reason": blocked,
                "kind": st.get("kind", "approval"), "state": state,
                "approver_name": _name(ap.approver_user_id) if ap else None,
                "decided_at": ap.decided_at if ap else None,
                "note": ap.note if ap else None,
            })

        data["stages"] = stages
        data["chain"] = chain
        data["timeline"] = [
            {"stage": a.stage_order, "label": a.stage_label, "role": a.approver_role,
             "role_label": ROLE_AR.get(a.approver_role, a.approver_role),
             "approver_name": _name(a.approver_user_id),
             "decision": a.decision, "note": a.note, "at": a.decided_at} for a in approvals
        ]
        data["documents"] = [
            {"kind": d.kind, "version": d.version, "created_at": d.created_at,
             "print_status": d.print_status, "printed_at": d.printed_at, "filed_at": d.filed_at,
             # V1.5 Phase 4: canonical OD code + lifecycle status (منفصل عن print_status)
             "od_code": d.od_code,
             "lifecycle_status": d.lifecycle_status}
            for d in docs
        ]
    return data
