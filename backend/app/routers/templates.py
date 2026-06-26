# -*- coding: utf-8 -*-
"""وحدة الصيغ والنماذج: تسجيل صيغ بمتغيّرات {{...}}، تعبئتها تلقائيًا ببيانات الموظف،
ثم معاينتها/طباعتها وأرشفتها في ملف الموظف."""
import html
import os
import re
from datetime import date, datetime

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
    "civil_id": "الرقم المدني",
    "job_title": "المسمى الوظيفي",
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
        out.append({"id": t.id, "name": t.name, "category": t.category,
                    "is_global": t.company_id is None,
                    "placeholders": sorted(set(_TOKEN_RE.findall(t.body_html)))})
    return out


@router.get("/{tpl_id}")
def get_template(tpl_id: int, user: models.User = Depends(require_perm("manage_templates")),
                 db: Session = Depends(get_db)):
    t = db.get(models.DocumentTemplate, tpl_id)
    if not t:
        raise HTTPException(status_code=404, detail="الصيغة غير موجودة")
    if t.company_id is not None:
        assert_same_company(user, t.company_id)
    return {"id": t.id, "name": t.name, "category": t.category, "body_html": t.body_html,
            "placeholders": sorted(set(_TOKEN_RE.findall(t.body_html)))}


@router.post("", status_code=201)
def create_template(data: schemas.DocumentTemplateIn, request: Request,
                    user: models.User = Depends(require_super_admin),
                    db: Session = Depends(get_db)):
    # إنشاء النماذج حصري للإدارة العليا؛ باقي المستخدمين يختارون من الموجود
    t = models.DocumentTemplate(company_id=None, name=data.name, category=data.category,
                                body_html=data.body_html, code=data.code, created_by=user.id)
    db.add(t)
    db.flush()
    audit(db, user, "create_template", "template", t.id, request=request)
    db.commit()
    return {"ok": True, "id": t.id}


@router.put("/{tpl_id}")
def update_template(tpl_id: int, data: schemas.DocumentTemplateIn, request: Request,
                    user: models.User = Depends(require_super_admin),
                    db: Session = Depends(get_db)):
    t = db.get(models.DocumentTemplate, tpl_id)
    if not t:
        raise HTTPException(status_code=404, detail="الصيغة غير موجودة")
    t.name, t.category, t.body_html = data.name, data.category, data.body_html
    audit(db, user, "update_template", "template", t.id, request=request)
    db.commit()
    return {"ok": True}


@router.delete("/{tpl_id}")
def delete_template(tpl_id: int, user: models.User = Depends(require_super_admin),
                    db: Session = Depends(get_db)):
    t = db.get(models.DocumentTemplate, tpl_id)
    if not t:
        raise HTTPException(status_code=404, detail="الصيغة غير موجودة")
    t.is_active = False
    db.commit()
    return {"ok": True}


def _build_context(db: Session, emp: models.Employee) -> dict:
    company = db.get(models.Company, emp.company_id)
    branch = db.get(models.Branch, emp.branch_id) if emp.branch_id else None
    return {
        "employee_name": emp.name or "",
        "civil_id": emp.civil_id or "",
        "job_title": emp.job_title or "",
        "nationality": emp.nationality or "",
        "basic_salary": f"{emp.basic_salary:.3f} د.ك" if emp.basic_salary else "",
        "hire_date": emp.hire_date.isoformat() if emp.hire_date else "",
        "contract_type": "غير محدد المدة" if emp.contract_type == "indefinite" else "محدد المدة",
        "branch_name": branch.name if branch else "",
        "phone": emp.phone or "",
        "company_name": company.name if company else "",
        "company_name_en": (company.name_en or "") if company else "",
        "commercial_reg": (company.commercial_reg or "") if company else "",
        "date_today": date.today().isoformat(),
        "ref_no": f"{emp.company_id}-{emp.id}-{datetime.now():%Y%m%d}",
    }


@router.post("/{tpl_id}/render")
def render_template(tpl_id: int, data: schemas.TemplateRenderIn, request: Request,
                    user: models.User = Depends(require_perm("manage_templates")),
                    db: Session = Depends(get_db)):
    """يعبّئ الصيغة ببيانات الموظف تلقائيًا + أي حقول إضافية، ويعيد HTML للطباعة."""
    t = db.get(models.DocumentTemplate, tpl_id)
    if not t:
        raise HTTPException(status_code=404, detail="الصيغة غير موجودة")
    emp = db.get(models.Employee, data.employee_id)
    if not emp:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    assert_same_company(user, emp.company_id)
    if t.company_id is not None:
        assert_same_company(user, t.company_id)

    ctx = _build_context(db, emp)
    ctx.update({k: str(v) for k, v in (data.extra or {}).items()})  # حقول مخصّصة يدخلها المستخدم

    def repl(m):
        key = m.group(1)
        # تهريب القيم المُدرجة (بيانات الموظف/المدخلات) لمنع حقن HTML/XSS
        return html.escape(str(ctx.get(key, "................")))

    filled = _TOKEN_RE.sub(repl, t.body_html)
    rendered = _wrap_printable(t.name, filled)

    document_id = None
    if data.save:
        folder = os.path.join(settings.upload_dir, "forms")
        os.makedirs(folder, exist_ok=True)
        fname = f"form_{t.id}_emp{emp.id}_{int(datetime.now().timestamp())}.html"
        fpath = os.path.join(folder, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(rendered)
        doc = models.Document(
            company_id=emp.company_id, entity_type="employee", entity_id=emp.id,
            document_type_code=f"form_{t.code or t.id}", title=t.name, file_path=fpath,
            mime="text/html", version=1, is_current=True, uploaded_by=user.id)
        db.add(doc)
        db.flush()
        document_id = doc.id

    audit(db, user, "render_template", "employee", emp.id, detail=t.name, request=request)
    db.commit()
    return {"html": rendered, "filename": f"{t.name} - {emp.name}.html", "document_id": document_id}


def _wrap_printable(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<title>{title}</title>
<style>
@page {{ size: A4; margin: 2.2cm; }}
body {{ font-family: "Tajawal","Segoe UI",Tahoma,Arial; color:#111; line-height:1.9; font-size:15px; }}
h1,h2,h3 {{ text-align:center; }}
.doc {{ max-width: 820px; margin: 0 auto; }}
table {{ width:100%; border-collapse: collapse; }} td,th {{ border:1px solid #999; padding:8px; }}
.noprint {{ position:fixed; top:12px; left:12px; }}
@media print {{ .noprint {{ display:none; }} }}
</style></head><body>
<button class="noprint" onclick="window.print()">🖨️ طباعة</button>
<div class="doc">{body}</div>
</body></html>"""
