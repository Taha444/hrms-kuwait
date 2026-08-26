# -*- coding: utf-8 -*-
"""وحدة الصيغ والنماذج: تسجيل صيغ بمتغيّرات {{...}}، تعبئتها تلقائيًا ببيانات الموظف،
ثم معاينتها/طباعتها وأرشفتها في ملف الموظف."""
import html
import os
import re
from datetime import date, datetime

from functools import lru_cache

import bleach
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..database import get_db
from ..deps import (
    assert_same_company,
    audit,
    get_current_user,
    require_perm,
    require_super_admin,
    scope_company_id,
)
from ..permissions import CROSS_COMPANY_ROLES

router = APIRouter(prefix="/templates", tags=["templates"])

# المتغيّرات التلقائية المتاحة (المفتاح: الوصف العربي)
PLACEHOLDERS = {
    "employee_name": "اسم الموظف",
    "employee_name_en": "اسم الموظف (إنجليزي)",
    "employee_id": "الرقم التسلسلي",
    "employee_no": "الرقم الوظيفي الرسمي",  # R1-B
    "civil_id": "الرقم المدني",
    "job_title": "المسمى الوظيفي",
    "department": "القسم/الإدارة",
    "nationality": "الجنسية",
    "basic_salary": "الراتب الأساسي",
    "hire_date": "تاريخ التعيين",
    "contract_type": "نوع العقد",
    "branch_name": "الفرع",
    "phone": "الهاتف",
    "company_name": "اسم الشركة",
    "company_name_en": "اسم الشركة (إنجليزي)",
    "commercial_reg": "السجل التجاري",
    "date_today": "تاريخ اليوم",
    "ref_no": "رقم المرجع",
}

_TOKEN_RE = re.compile(r"\{\{\s*([\w]+)\s*\}\}")

# وسوم تنسيق نصي/جدولي فقط لمحتوى الصيغ، وسمتان آمنتان فقط (class/dir يستخدمهما تصميم حزمة
# HRMS-PR-001..042 ثنائي اللغة) — بلا event handlers أو href/src أو style أو
# iframe/script/style tags (QA-P0-SEC-01: XSS مخزّن عبر body_html المحفوظ).
_ALLOWED_TPL_TAGS = [
    "p", "br", "b", "strong", "i", "em", "u", "s", "small", "sup", "sub",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "thead", "tbody", "tr", "td", "th",
    "ul", "ol", "li", "span", "div", "hr", "blockquote",
]
_ALLOWED_TPL_ATTRS = {"*": ["class", "dir"]}


# script/style: bleach بـstrip=True يحذف الوسم ويُبقي نصّه، فيظهر "alert(1)"
# مكتوًبا داخل مستند رسمي مطبوع. ليس ثغرة تنفيذ — لا وسم يبقى — لكنه نص
# دخيل على ورقة تُقدَّم لجهة خارجية. يُحذف بمحتواه قبل التعقيم.
_DROP_WITH_CONTENT = re.compile(
    r"<\s*(script|style|iframe|object|embed)\b.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL)


def _sanitize_body_html(raw: str) -> str:
    cleaned = _DROP_WITH_CONTENT.sub("", raw or "")
    return bleach.clean(cleaned, tags=_ALLOWED_TPL_TAGS,
                        attributes=_ALLOWED_TPL_ATTRS, strip=True)


def unknown_placeholders(body_html: str) -> list[str]:
    """V2.2 §28.4 (STR-06) — الرموز التي لا يعرفها النظام في هذا القالب.

    ROOT CAUSE: ``_fill_html`` تستبدل أي رمز مجهول بنقاط، فقالب يكتب
    ``{{empolyee_name}}`` بخطأ مطبعي يُحفظ بلا شكوى ويُطبع بفراغ — ويُكتشف
    حين يقرأ موظفٌ شهادته وفيها سطر نقاط مكان اسمه. التحقق وقت الحفظ يجعل
    الخطأ يظهر لمن يستطيع إصلاحه، لا لمن يتضرّر منه.

    القائمة **مشتقّة لا مكتوبة**، من ثلاثة مصادر:
    1. ``PLACEHOLDERS`` المُعلَنة للواجهة
    2. مفاتيح ``_build_context`` الفعلية — تُقرأ من الدالة نفسها
    3. ما تستخدمه القوالب الرسمية المبذورة — فهي حدّ ما يدعمه النظام فعلًا

    قائمة يدوية ثالثة كانت ستنحرف عن الثلاثة مع أول حقل يُضاف، وهو نمط
    "موضعان يصفان قاعدة واحدة" نفسه.
    """
    return sorted(set(_TOKEN_RE.findall(body_html or "")) - _known_placeholders())


@lru_cache(maxsize=1)
def _known_placeholders() -> frozenset[str]:
    """الرموز المسموحة — مشتقّة من الإعلان والسياق والقوالب الرسمية."""
    from ..seed import DEFAULT_TEMPLATES

    used_by_official: set[str] = set()
    for entry in DEFAULT_TEMPLATES:
        used_by_official |= set(_TOKEN_RE.findall(entry[-1] or ""))
    return frozenset(set(PLACEHOLDERS) | _context_keys() | used_by_official)


def _context_keys() -> set[str]:
    """مفاتيح السياق الفعلية — تُقرأ من الدالة نفسها لا من قائمة موازية."""
    import inspect
    import re as _re
    src = inspect.getsource(_build_context)
    return set(_re.findall(r'"(\w+)":', src))


@router.get("/placeholders")
def placeholders(user: models.User = Depends(require_perm("manage_templates"))):
    return PLACEHOLDERS


@router.get("")
def list_templates(company_id: int | None = None,
                   user: models.User = Depends(require_perm("manage_templates")),
                   db: Session = Depends(get_db)):
    """صيغ الشركة المختارة + الصيغ العامة (company_id = null)."""
    cid = scope_company_id(user, company_id)
    q = select(models.DocumentTemplate).where(models.DocumentTemplate.is_active == True)  # noqa: E712
    rows = db.scalars(q.order_by(models.DocumentTemplate.category, models.DocumentTemplate.name)).all()
    out = []
    for t in rows:
        if t.company_id not in (None, cid) and user.role not in CROSS_COMPANY_ROLES:
            continue
        if cid is not None and t.company_id not in (None, cid):
            continue
        out.append({"id": t.id, "code": t.code, "name": t.name, "name_en": t.name_en,
                    "category": t.category, "is_global": t.company_id is None,
                    "placeholders": sorted(set(_TOKEN_RE.findall(t.body_html)))})
    return out


@router.get("/exists")
def templates_exist(codes: str,
                    user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """R9 §11 — يستعلم عن وجود قوالب بأكواد محددة (comma-separated).
    الردّ: `{"CODE1": true, "CODE2": false}`. المستخدم أي دور مسجّل.
    الاستخدام النموذجي: الـfrontend يفحص قبل عرض زر توليد لتجنب 404 لاحق.
    """
    codes_list = [c.strip() for c in codes.split(",") if c.strip()]
    if not codes_list:
        return {}
    found = set(db.scalars(select(models.DocumentTemplate.code).where(
        models.DocumentTemplate.code.in_(codes_list),
        models.DocumentTemplate.is_active == True,  # noqa: E712
    )).all())
    return {code: (code in found) for code in codes_list}


@router.get("/{tpl_id}")
def get_template(tpl_id: int, user: models.User = Depends(require_perm("manage_templates")),
                 db: Session = Depends(get_db)):
    t = db.get(models.DocumentTemplate, tpl_id)
    if not t:
        raise HTTPException(status_code=404, detail="الصيغة غير موجودة")
    if t.company_id is not None:
        assert_same_company(user, t.company_id, db=db)
    return {"id": t.id, "name": t.name, "name_en": t.name_en, "category": t.category, "body_html": t.body_html,
            "placeholders": sorted(set(_TOKEN_RE.findall(t.body_html)))}


@router.post("", status_code=201)
def create_template(data: schemas.DocumentTemplateIn, request: Request,
                    user: models.User = Depends(require_super_admin),
                    db: Session = Depends(get_db)):
    # إنشاء النماذج حصري للإدارة العليا؛ باقي المستخدمين يختارون من الموجود
    t = models.DocumentTemplate(company_id=None, name=data.name, name_en=data.name_en, category=data.category,
                                body_html=_sanitize_body_html(data.body_html), code=data.code, created_by=user.id)
    db.add(t)
    db.flush()
    audit(db, user, "create_template", "template", t.id, request=request)
    db.commit()
    # STR-06 — تُبلَّغ ولا تمنع: النظام يدعم حقوًلا مخصّصة عمًدا عبر extras،
    # فالرفض يهدم ميزة قائمة. لكن السكوت عنها يجعل خطأ مطبعًيا واحًدا
    # يُطبع سطر نقاط مكان اسم الموظف في شهادته.
    return {"ok": True, "id": t.id,
            "unknown_placeholders": unknown_placeholders(data.body_html)}


@router.put("/{tpl_id}")
def update_template(tpl_id: int, data: schemas.DocumentTemplateIn, request: Request,
                    user: models.User = Depends(require_super_admin),
                    db: Session = Depends(get_db)):
    """V2.2 §14 — كل تعديل يُنشئ نسخة تاريخية للحفاظ على المستندات القديمة المرتبطة بها."""
    t = db.get(models.DocumentTemplate, tpl_id)
    if not t:
        raise HTTPException(status_code=404, detail="الصيغة غير موجودة")
    # نحفظ النسخة الحالية قبل الكتابة فوقها
    last_version = db.scalar(select(models.DocumentTemplateVersion).where(
        models.DocumentTemplateVersion.template_id == t.id,
    ).order_by(models.DocumentTemplateVersion.version.desc()))
    next_version = (last_version.version + 1) if last_version else 1
    db.add(models.DocumentTemplateVersion(
        template_id=t.id, version=next_version,
        body_html=t.body_html, name=t.name, category=t.category,
        edited_by=user.id, change_note=f"تحديث بواسطة {user.civil_id}",
    ))
    t.name, t.name_en, t.category = data.name, data.name_en, data.category
    t.body_html = _sanitize_body_html(data.body_html)
    # R1-A §8 — تحديث القالب يزيد عدّاد الإصدار (يُختم على أي مستند مُولّد لاحقًا)
    t.version = (t.version or 1) + 1
    audit(db, user, "update_template", "template", t.id, request=request)
    db.commit()
    return {"ok": True, "version": next_version, "template_version": t.version}


@router.get("/{tpl_id}/versions")
def list_template_versions(tpl_id: int,
                           user: models.User = Depends(require_super_admin),
                           db: Session = Depends(get_db)):
    """V2.2 §14 — قائمة النسخ التاريخية للقالب."""
    t = db.get(models.DocumentTemplate, tpl_id)
    if not t:
        raise HTTPException(status_code=404, detail="الصيغة غير موجودة")
    rows = db.scalars(select(models.DocumentTemplateVersion).where(
        models.DocumentTemplateVersion.template_id == tpl_id,
    ).order_by(models.DocumentTemplateVersion.version.desc())).all()
    return [{"id": v.id, "version": v.version, "name": v.name,
             "edited_by": v.edited_by, "edited_at": v.edited_at.isoformat(),
             "change_note": v.change_note} for v in rows]


@router.delete("/{tpl_id}")
def delete_template(tpl_id: int, request: Request,
                    user: models.User = Depends(require_super_admin),
                    db: Session = Depends(get_db)):
    """V2.2 §14 — لا يُحذف قالب مستخدم:
    - لو مرتبط بأنواع طلبات نشطة (default_template_code) → 409 وقائمة الأنواع.
    - لو مرتبط بمستندات مُوَلَّدة من قبل → soft-delete فقط (is_active=False)
      حفاظًا على قابلية عرض المستندات القديمة."""
    t = db.get(models.DocumentTemplate, tpl_id)
    if not t:
        raise HTTPException(status_code=404, detail="الصيغة غير موجودة")
    if t.code:
        active_uses = db.scalars(select(models.RequestType).where(
            models.RequestType.default_template_code == t.code,
            models.RequestType.is_active.is_(True),
        )).all()
        if active_uses:
            names = ", ".join(rt.name for rt in active_uses[:5])
            raise HTTPException(status_code=409,
                                detail=f"الصيغة مستخدمة في: {names} — عطّل الأنواع أولاً")
    t.is_active = False
    audit(db, user, "delete_template", "template", t.id, request=request)
    db.commit()
    return {"ok": True}


# أسماء الأيام كما تُكتب في صدر نموذج الهيئة العامة للقوى العاملة.
# الترتيب يطابق datetime.weekday(): الاثنين = 0.
_DAY_AR = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")
_DAY_EN = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _residency_number(db: Session, emp: models.Employee) -> str:
    """رقم إقامة الموظف السارية — يُحفظ في permits لا كعمود على الموظف."""
    p = db.scalar(
        select(models.Permit)
        .where(models.Permit.employee_id == emp.id, models.Permit.kind == "residency")
        .order_by(models.Permit.expiry_date.desc())
    )
    return (p.number or "") if p else ""


def _build_context(db: Session, emp: models.Employee) -> dict:
    company = db.get(models.Company, emp.company_id)
    branch = db.get(models.Branch, emp.branch_id) if emp.branch_id else None
    department = db.get(models.Department, emp.department_id) if emp.department_id else None

    # P0-#11 — bilingual contract_type + clauses للعقد الحكومي الرسمي (PAM template)
    is_indefinite = emp.contract_type == "indefinite"
    contract_type_ar = "غير محدد المدة" if is_indefinite else "محدد المدة"
    contract_type_en = "of indefinite term" if is_indefinite else "of definite term"
    # Clause إضافية لو محدد المدة: "لمدة سنة واحدة" (يمكن للـextras تعديلها)
    contract_term_clause_ar = "" if is_indefinite else "، لمدة سنة واحدة قابلة للتجديد باتفاق الطرفين لمدد مماثلة لا تتجاوز خمس سنوات"
    contract_term_clause_en = "" if is_indefinite else ", for a term of ONE YEAR renewable with the approval of the parties for similar terms not exceeding five years"

    return {
        "employee_name": emp.name or "",
        "employee_name_en": emp.name_en or "",
        "employee_id": str(emp.id),
        "employee_no": emp.employee_no or "",  # R1-B — الرقم الوظيفي الرسمي
        "civil_id": emp.civil_id or "",
        "passport_number": emp.passport_number or "",  # P0-#11 — نموذج PAM يحتاجه
        "date_of_birth": emp.date_of_birth.isoformat() if emp.date_of_birth else "",
        "job_title": emp.job_title or "",
        "department": department.name if department else "",
        "nationality": emp.nationality or "",
        # QA-13 — الوحدة تخصّ الجملة لا القيمة. كانت القيمة تحمل "د.ك" بينما
        # القوالب تكتبها بعدها ("{{basic_salary}} د.ك") فتُطبع "د.ك د.ك"،
        # وفي النسخة الإنجليزية "KWD 1234.000 د.ك". القيمة رقم مجرّد الآن،
        # ولمن يحتاج الوحدة مفتاح صريح.
        "basic_salary": f"{emp.basic_salary:.3f}" if emp.basic_salary else "",
        "basic_salary_kwd": f"{emp.basic_salary:.3f} د.ك" if emp.basic_salary else "",
        # QA-13 — كانا يأتيان من إدخال العميل: يُطبعان نقاًطا حين لا يرسلهما
        # النموذج، والأخطر أنهما رقمان ماليان قابلان للتزوير من الفورم.
        # النظام لا يسجّل بدلات منفصلة، فالبدل = الفرق بين الفعلي والأساسي.
        "allowances_total": f"{max((emp.actual_salary or emp.basic_salary or 0) - (emp.basic_salary or 0), 0):.3f}",
        "gross_salary": f"{(emp.actual_salary or emp.basic_salary or 0):.3f}",
        "hire_date": emp.hire_date.isoformat() if emp.hire_date else "",
        "contract_type": contract_type_ar,  # backward compat (النص القديم)
        "contract_type_ar": contract_type_ar,
        "contract_type_en": contract_type_en,
        "contract_term_clause_ar": contract_term_clause_ar,
        "contract_term_clause_en": contract_term_clause_en,
        "branch_name": branch.name if branch else "",
        "phone": emp.phone or "",
        "company_name": company.name if company else "",
        "company_name_en": (company.name_en or "") if company else "",
        "commercial_reg": (company.commercial_reg or "") if company else "",
        "date_today": date.today().isoformat(),
        "ref_no": f"{emp.company_id}-{emp.id}-{datetime.now():%Y%m%d}",
        # P0-#11 — قيم افتراضية من قانون العمل الكويتي (قابلة للـoverride عبر extras):
        "probation_days": "100",
        "annual_leave_days": "30",
        "special_conditions": "لا يوجد / None",

        # ── حقول نموذج PAM الحرفي (الترحيل v5o6p7q8r9s) ──────────────────────
        # النموذج الرسمي يذكر اليوم والتاريخ صراحًة في صدر العقد
        "contract_date": (emp.hire_date.strftime("%d/%m/%Y") if emp.hire_date
                          else date.today().strftime("%d/%m/%Y")),
        "day_name_ar": _DAY_AR[(emp.hire_date or date.today()).weekday()],
        "day_name_en": _DAY_EN[(emp.hire_date or date.today()).weekday()],
        # ممثل الشركة في التوقيع — يقع على الشركة لا على الموظف. الحقول غير
        # موجودة في النموذج بعد، فنقرأها بأمان: العقد يُطبع بخانة فارغة تُملأ
        # يدويًا بدل أن يفشل التوليد كله.
        "company_rep_name": (getattr(company, "rep_name", None) or company.name) if company else "",
        "company_rep_name_en": ((getattr(company, "rep_name_en", None)
                                 or company.name_en or "") if company else ""),
        "company_rep_civil_id": (getattr(company, "rep_civil_id", "") or "") if company else "",
        # النموذج يفرّق بين رقم الجواز ورقم الإقامة في بيانات الطرف الثاني.
        # رقم الإقامة يُحفظ في permits لا كعمود على الموظف.
        "residency_number": _residency_number(db, emp),
        "nationality_en": emp.nationality_en or emp.nationality or "",
        "job_title_en": emp.job_title_en or emp.job_title or "",
        # مدة العقد المحدد — نصًّا كما في النموذج
        "contract_years_ar": "سنة" if not is_indefinite else "",
        "contract_years_en": "ONE YEARS" if not is_indefinite else "",
        # البند الثالث عشر: ثلاثة أسطر شروط خاصة، الافتراضي "لا يوجد"
        "special_condition_1": "لا يوجد",
        "special_condition_2": "لا يوجد",
        "special_condition_3": "لا يوجد",
        # خانتا التوقيع تُملآن عند الطباعة بعد الاعتماد
        "company_signature": "",
        "employee_signature": "",
    }


# ============================================================================
# R1-A §8 — Preview / Generate Decoupled Pipeline
# ============================================================================
# Preview: يعرض HTML فقط. لا يكتب ملف ولا صف Document. لا يمكن اعتباره مصدرًا
#          رسميًا للطباعة (Mark Printed مرفوض على أي مستند بلا is_issued=True).
# Generate: يكتب الملف على القرص، ينشئ صف Document بكل الـmetadata الرسمية
#          (reference_no, template_version, checksum_sha256, generated_at/by,
#          signature_version)، ويصير قابلًا للـMark Printed / Filed.
# ----------------------------------------------------------------------------


def _resolve_authoritative_data(db: Session, emp: models.Employee, extras: dict) -> dict:
    """يبني سياق التوليد من مصدر السلطة (DB) فقط. حقول العميل تُقبل فقط لو ما
    لها مقابل authoritative — لمنع تزوير الراتب/التاريخ من الفورم.
    """
    ctx = _build_context(db, emp)
    # مفاتيح authoritative (لا تُقبَل من input) — الراتب والتاريخ والاسم من DB فقط
    LOCKED = {"basic_salary", "basic_salary_kwd", "allowances_total", "gross_salary",
              "hire_date", "civil_id", "employee_name",
              "employee_name_en", "employee_id", "job_title", "nationality",
              "contract_type", "company_name", "company_name_en",
              "commercial_reg", "branch_name", "department"}
    for k, v in (extras or {}).items():
        if k in LOCKED:
            continue  # نتجاهل بصمت لضمان صحة البيانات
        ctx[k] = str(v)
    return ctx


def _fill_html(t: models.DocumentTemplate, ctx: dict) -> str:
    def repl(m):
        key = m.group(1)
        return html.escape(str(ctx.get(key, "................")))
    filled = _TOKEN_RE.sub(repl, _sanitize_body_html(t.body_html))
    return _wrap_printable(t, ctx, filled)


def _generate_reference_no(db: Session, template_code: str | None, company_id: int,
                          template_version: int) -> str:
    """رقم مرجعي فريد ومقروء: {CODE}/{COMPANY}/{YYYYMM}/{SEQ4}
    مثال: HRMS-PR-001/3/202608/0042"""
    now = datetime.utcnow()
    period = now.strftime("%Y%m")
    prefix = f"{template_code or 'DOC'}/{company_id}/{period}/"
    last = db.scalar(select(models.Document.reference_no).where(
        models.Document.reference_no.like(f"{prefix}%"),
    ).order_by(models.Document.reference_no.desc()))
    seq = 1
    if last:
        try:
            seq = int(last.rsplit("/", 1)[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{prefix}{seq:04d}"


@router.post("/{tpl_id}/preview")
def preview_template(tpl_id: int, data: schemas.TemplateRenderIn, request: Request,
                     user: models.User = Depends(require_perm("manage_templates")),
                     db: Session = Depends(get_db)):
    """R1-A §8 — Preview فقط. لا كتابة على القرص، لا صف DB، لا مرجع رسمي.
    نتيجته HTML بس. للحصول على مستند رسمي قابل للطباعة استخدم /generate."""
    t = db.get(models.DocumentTemplate, tpl_id)
    if not t:
        raise HTTPException(status_code=404, detail="الصيغة غير موجودة")
    emp = db.get(models.Employee, data.employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    assert_same_company(user, emp.company_id, db=db)
    if t.company_id is not None:
        assert_same_company(user, t.company_id, db=db)

    ctx = _resolve_authoritative_data(db, emp, data.extra or {})
    rendered = _fill_html(t, ctx)
    audit(db, user, "preview_template", "employee", emp.id,
          detail=f"{t.name} (preview only, not stored)", request=request)
    db.commit()
    return {
        "html": rendered,
        "is_preview": True,
        "is_issued": False,
        "warning": "هذه معاينة فقط — لا تُعتبر مستندًا رسميًا. استخدم زر «توليد» لإصدار مستند مرجعي.",
    }


@router.post("/{tpl_id}/generate")
def generate_template(tpl_id: int, data: schemas.TemplateRenderIn, request: Request,
                      user: models.User = Depends(require_perm("manage_templates")),
                      db: Session = Depends(get_db)):
    """R1-A §8 — Generate: يُصدر مستندًا رسميًا مع كل metadata (reference_no،
    template_version، checksum SHA-256، generated_at/by، signature_version).
    المستند يصير قابلًا للـMark Printed / Filed."""
    import hashlib

    t = db.get(models.DocumentTemplate, tpl_id)
    if not t:
        raise HTTPException(status_code=404, detail="الصيغة غير موجودة")
    emp = db.get(models.Employee, data.employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    assert_same_company(user, emp.company_id, db=db)
    if t.company_id is not None:
        assert_same_company(user, t.company_id, db=db)

    ctx = _resolve_authoritative_data(db, emp, data.extra or {})
    reference_no = _generate_reference_no(db, t.code, emp.company_id, t.version or 1)
    ctx["ref_no"] = reference_no  # يظهر في الترويسة

    rendered = _fill_html(t, ctx)
    pdf_bytes = rendered.encode("utf-8")
    checksum = hashlib.sha256(pdf_bytes).hexdigest()

    # كتابة الملف الفعلي — الاسم يحوي reference للتتبّع
    folder = os.path.join(settings.upload_dir, "forms")
    os.makedirs(folder, exist_ok=True)
    safe_ref = reference_no.replace("/", "_")
    fname = f"{safe_ref}.html"
    fpath = os.path.join(folder, fname)
    with open(fpath, "wb") as f:
        f.write(pdf_bytes)

    # نسخة توقيع مصدر المستند لو له توقيع نشط
    sig_version = None
    active_sig = db.scalar(select(models.EmployeeSignature).where(
        models.EmployeeSignature.user_id == user.id,
        models.EmployeeSignature.status == "active",
    ).order_by(models.EmployeeSignature.version.desc())) if hasattr(models, "EmployeeSignature") else None
    if active_sig:
        sig_version = getattr(active_sig, "version", None)

    doc = models.Document(
        company_id=emp.company_id, entity_type="employee", entity_id=emp.id,
        document_type_code=f"form_{t.code or t.id}", title=t.name, file_path=fpath,
        mime="text/html", version=1, is_current=True, uploaded_by=user.id,
        # R1-A §8 — Immutable Metadata
        is_issued=True,
        reference_no=reference_no,
        template_version=t.version or 1,
        checksum_sha256=checksum,
        generated_at=datetime.utcnow(),
        generated_by=user.id,
        signature_version=sig_version,
    )
    db.add(doc)
    db.flush()

    audit(db, user, "generate_template", "employee", emp.id,
          detail=f"{t.name} → {reference_no}", request=request,
          after={"reference_no": reference_no, "checksum_sha256": checksum,
                "template_version": t.version or 1})
    db.commit()

    return {
        "html": rendered,
        "is_preview": False,
        "is_issued": True,
        "document_id": doc.id,
        "reference_no": reference_no,
        "template_version": t.version or 1,
        "checksum_sha256": checksum,
        "generated_at": doc.generated_at.isoformat() + "Z",
        "signature_version": sig_version,
        "filename": f"{safe_ref}.html",
    }


@router.post("/{tpl_id}/render")
def render_template(tpl_id: int, data: schemas.TemplateRenderIn, request: Request,
                    user: models.User = Depends(require_perm("manage_templates")),
                    db: Session = Depends(get_db)):
    """DEPRECATED — طريق قديم للتوافق العكسي. يعيد التوجيه إلى preview أو generate
    حسب data.save. سيُزال في إصدار قادم. استخدم /preview أو /generate صراحةً."""
    if data.save:
        return generate_template(tpl_id, data, request, user, db)
    return preview_template(tpl_id, data, request, user, db)


def _wrap_printable(t: "models.DocumentTemplate", ctx: dict, body: str) -> str:
    """يبني هيكل الصفحة ثنائي اللغة الموحّد (ترويسة الشركة، العنوان، صف المرجع/التاريخ،
    صف الشركة/الفرع/الحالة، شبكة بيانات الموظف)، ويضع محتوى الصيغة الخاص بها (body) في الوسط."""
    title_en = t.name_en or ""
    ref_no = html.escape(str(ctx.get("ref_no", "")))
    date_today = html.escape(str(ctx.get("date_today", "")))
    company_name = html.escape(str(ctx.get("company_name", "")))
    company_name_en = html.escape(str(ctx.get("company_name_en", "")))
    branch_name = html.escape(str(ctx.get("branch_name", "")))

    def cell(ar_label, en_label, value):
        v = html.escape(str(value)) if value else "................"
        return f"<td><span class='muted'>{ar_label} / {en_label}</span><br>{v}</td>"

    info_grid = f"""
<table class="info-grid">
<tr>{cell('اسم الموظف', 'Employee Name', ctx.get('employee_name'))}
{cell('الرقم المدني', 'Civil ID', ctx.get('civil_id'))}</tr>
<tr>{cell('الرقم الوظيفي', 'Employee ID', ctx.get('employee_id'))}
{cell('المسمى الوظيفي', 'Job Title', ctx.get('job_title'))}</tr>
<tr>{cell('القسم', 'Department', ctx.get('department'))}
{cell('الفرع', 'Branch', ctx.get('branch_name'))}</tr>
</table>"""

    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>{html.escape(t.name)}</title>
<style>
@page {{ size: A4; margin: 1.8cm; }}
body {{ font-family: "Tajawal","Segoe UI",Tahoma,Arial; color:#111; line-height:1.8; font-size:14px; }}
.doc {{ max-width: 860px; margin: 0 auto; }}
.header-row {{ display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #333; padding-bottom:10px; margin-bottom:10px; }}
.company-block {{ text-align:right; }} .company-block .en {{ direction:ltr; color:#555; font-size:13px; }}
h1 {{ text-align:center; font-size:20px; margin:6px 0 0; }}
h1 .en {{ display:block; direction:ltr; font-size:15px; color:#555; font-weight:normal; }}
table {{ width:100%; border-collapse: collapse; margin-bottom:10px; }}
td,th {{ border:1px solid #999; padding:6px 8px; font-size:13px; vertical-align:top; }}
.muted {{ color:#666; font-size:11px; }}
.meta-row td {{ background:#f7f7f7; }}
.info-grid td {{ width:33%; }}
.sig-row td {{ text-align:center; height:70px; vertical-align:bottom; }}
.footer {{ margin-top:18px; border-top:1px solid #ccc; padding-top:8px; font-size:11px; color:#777; text-align:center; }}
.noprint {{ position:fixed; top:12px; left:12px; }}
@media print {{ .noprint {{ display:none; }} }}
</style></head><body>
<div class="noprint" style="font:13px/1.6 system-ui;background:#f7f7f7;border:1px solid #ddd;border-radius:6px;padding:8px 12px">للطباعة: Ctrl+P &nbsp;·&nbsp; For printing: Ctrl+P</div>
<div class="doc">
<div class="header-row">
<div class="company-block">{company_name}<div class="en">{company_name_en}</div></div>
<div><span class="muted">كود: {html.escape(t.code or '')}</span></div>
</div>
<h1>{html.escape(t.name)}<span class="en">{title_en}</span></h1>
<table class="meta-row"><tr>
<td>التاريخ / Date: {date_today}</td><td>المرجع / Reference No.: {ref_no}</td>
</tr><tr>
<td>الشركة / الفرع — Company / Branch: {company_name} / {branch_name}</td>
<td>الحالة / Status: صادر — Issued</td>
</tr></table>
{info_grid}
{body}
<div class="footer">رمز التحقق / Verification Code: {ref_no}</div>
</div>
</body></html>"""
