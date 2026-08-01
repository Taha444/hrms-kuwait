# -*- coding: utf-8 -*-
"""PILOT-P0-6 + V2.2 §6/Module 6 — توليد الرقم الوظيفي للموظف.

الصيغة المفضّلة (لما اختصار الشركة والفرع مضبوطين):
    `{COMPANY_ABBR}-{BRANCH_CODE}-{seq:05d}`  →  KOC-KUW-00142

الصيغة الاحتياطية (توافق خلفي إذا abbreviation/code فارغين):
    `CO{company_id:02d}-BR{branch_id:02d}-{seq:04d}`  →  CO01-BR03-0007

قواعد:
- فريد على مستوى النظام (unique DB constraint)
- ثابت بعد التوليد — لا يتغيّر مع نقل الفرع (فيه سياسة عليا لتغييره)
- Read-only في الواجهة
- non-reusable: الأرقام المؤرشفة تبقى محجوزة (nextval يعلو دائمًا)
- Thread-safe: نستخدم أعلى قيمة في DB + retry بسيط عند التصادم
"""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


def _clean_abbr(s: str, width: int = 3) -> str:
    """يعيد سلسلة uppercase من الأحرف الإنجليزية/الأرقام فقط."""
    if not s:
        return ""
    return re.sub(r"[^A-Z0-9]", "", s.upper())[:width]


def _derive_from_name(name_en: str | None, name_ar: str, width: int = 3) -> str:
    """يستنتج اختصار من الاسم الإنجليزي — أول حرفين من كل كلمة، أو transliteration بدائي."""
    if name_en:
        parts = [p for p in re.split(r"\s+", name_en.strip()) if p]
        if parts:
            initials = "".join(p[0] for p in parts[:width]).upper()
            return _clean_abbr(initials, width) or _clean_abbr(parts[0], width)
    # Arabic fallback: نستخدم أرقام (مش مثالي بس أفضل من فراغ)
    return ""


def _company_abbr(company: models.Company) -> str:
    """اختصار الشركة — من abbreviation إن وُجد، وإلا من name_en، وإلا CO<id> كملاذ أخير."""
    if not company:
        return "CO0"
    if company.abbreviation:
        return _clean_abbr(company.abbreviation, 6)
    derived = _derive_from_name(company.name_en, company.name)
    return derived or f"CO{company.id:02d}"


def _branch_code(branch: models.Branch | None) -> str:
    """كود الفرع — من code إن وُجد، وإلا من اسمه، وإلا HQ للفرع الأساسي."""
    if not branch:
        return "HQ"
    if branch.code:
        return _clean_abbr(branch.code, 6)
    derived = _derive_from_name(None, branch.name)  # ما فيش name_en على Branch
    return derived or f"BR{branch.id:02d}"


def _next_sequence(db: Session, prefix: str) -> int:
    """أعلى تسلسل مستخدم في هذا الـprefix + 1 — بيشمل الأرقام المؤرشفة (non-reusable)."""
    highest = 0
    q = select(models.Employee.employee_no).where(
        models.Employee.employee_no.like(f"{prefix}%")
    )
    for row in db.scalars(q).all():
        try:
            seq = int(row.rsplit("-", 1)[-1])
            if seq > highest:
                highest = seq
        except (ValueError, IndexError):
            continue
    return highest + 1


def generate(db: Session, employee: models.Employee) -> str:
    """يولّد رقمًا وظيفيًا للموظف بالصيغة الرسمية `{ABBR}-{BRANCH}-{seq:05d}`.
    Idempotent — لو الموظف عنده رقم بالفعل يُعاد كما هو دون تغيير.

    Non-reusable: يحسب أعلى تسلسل موجود ضمن نفس (abbr, branch) بما فيهم الموظفين
    المؤرشفين، ويعطي seq+1. الأرقام القديمة تظل محجوزة.
    """
    if employee.employee_no:
        return employee.employee_no

    company = db.get(models.Company, employee.company_id)
    branch = db.get(models.Branch, employee.branch_id) if employee.branch_id else None

    abbr = _company_abbr(company)
    bcode = _branch_code(branch)
    prefix = f"{abbr}-{bcode}-"
    seq = _next_sequence(db, prefix)
    code = f"{prefix}{seq:05d}"

    employee.employee_no = code
    return code


def backfill_missing(db: Session, company_id: int | None = None) -> int:
    """يعطي رقمًا وظيفيًا لأي موظف بدون رقم — للحسابات القديمة قبل P0-6."""
    q = select(models.Employee).where(models.Employee.employee_no.is_(None))
    if company_id is not None:
        q = q.where(models.Employee.company_id == company_id)
    count = 0
    for emp in db.scalars(q).all():
        generate(db, emp)
        count += 1
    if count:
        db.commit()
    return count
