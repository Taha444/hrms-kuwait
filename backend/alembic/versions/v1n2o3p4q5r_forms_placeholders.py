# -*- coding: utf-8 -*-
"""FRM-01 — إزالة النوائب الورقية من الصيغ الخمس.

كانت القوالب تطبع خانات نموذج ورقي في مستند يولّده النظام: ``[____]``
و``[Bank/Embassy/Other]`` و``[DD/MM/YYYY]`` و``[Bank/Cash]``. وخانة فارغة
في ورقة تُقدَّم لبنك أو سفارة ليست خانة تُملأ باليد — هي إقرار مطبوع بأن
البيانات ناقصة.

والتحديث على المحفوظ في القاعدة لا على البذرة وحدها: قاعدة عميل قائمة لا
تُعاد بذرتها، فتبقى فيها القوالب القديمة إلى الأبد.

Revision ID: v1n2o3p4q5r
Revises: u0m1n2o3p4q
"""
import sqlalchemy as sa
from alembic import op

revision = "v1n2o3p4q5r"
down_revision = "u0m1n2o3p4q"
branch_labels = None
depends_on = None

#: (الكود، النصّ القديم، النصّ الجديد) — على مستوى صفّ الجدول الواحد
ROWS: list[tuple[str, str, str]] = [
    ("HRMS-PR-001",
     "[____] /KWD البدلات [____] /KWD الراتب الأساسي",
     "الراتب الأساسي: {{basic_salary}} د.ك · البدلات: {{allowances_total}} د.ك"),
    ("HRMS-PR-001",
     "[Bank/Embassy/Other] الجهة الموجه إليها [____] /KWD الإجمالي",
     "الإجمالي: {{gross_salary}} د.ك · الجهة الموجّه إليها: {{target_entity}}"),
    ("HRMS-PR-006",
     "[ ] نوع العقد [DD/MM/YYYY] تاريخ التعيين",
     "تاريخ التعيين: {{hire_date}} · نوع العقد: {{contract_type_ar}}"),
    ("HRMS-PR-006",
     "[____] /KWD الراتب الفعلي [____] /KWD الراتب الرسمي",
     "الراتب الرسمي: {{official_salary}} د.ك · الراتب الفعلي: {{actual_salary}} د.ك"),
    ("HRMS-PR-006",
     "[ ] مكان العمل الفعلي [ ] مكان العمل الرسمي",
     "مكان العمل: {{work_location}}"),
    ("HRMS-PR-006",
     "[DD/MM/YYYY] انتهاء الإقامة [ ] رقم الإقامة",
     "رقم الإقامة: {{residency_no}} · انتهاء الإقامة: {{residency_expiry}}"),
    ("HRMS-PR-008", "[ ] اسم البنك", "اسم البنك: {{bank_name}}"),
    ("HRMS-PR-008", "[ ] رقم الحساب", "رقم الحساب / الآيبان: {{bank_account_iban}}"),
    ("HRMS-PR-008",
     "[DD/MM/YYYY] تاريخ البدء [____] /KWD راتب التحويل",
     "راتب التحويل: {{basic_salary}} د.ك · تاريخ البدء: {{transfer_start_date}}"),
    ("HRMS-PR-009",
     "[Bank/Cash] طريقة الصرف [Monthly] دورة الصرف",
     "دورة الصرف: {{payroll_cycle}} · طريقة الصرف: {{payment_method}}"),
    ("HRMS-PR-009",
     "[Active] الحالة [MM/YYYY] آخر راتب مصروف",
     "الحالة: {{employment_status}} · آخر راتب مصروف: {{last_payroll_month}}"),
    ("HRMS-PR-032",
     "[____] البدلات [____] الراتب الأساسي",
     "الراتب الأساسي: {{basic_salary}} د.ك · البدلات: {{allowances_total}} د.ك"),
    ("HRMS-PR-032",
     "[____] المكافآت [____] العمل الإضافي",
     "العمل الإضافي: {{overtime_pay}} د.ك · المكافآت: {{bonuses}} د.ك"),
    ("HRMS-PR-032",
     "[____] السلف [____] الخصومات",
     "الخصومات: {{total_deductions}} د.ك · السلف: {{advances}} د.ك"),
    ("HRMS-PR-032",
     "[Bank/Cash] طريقة الدفع [____] صافي الراتب د.ك",
     "صافي الراتب: {{net_salary}} د.ك · طريقة الدفع: {{payment_method}}"),
]

#: العناوين الإنجليزية المقابلة — كانت مبعثرة الترتيب («IBAN/» وحدها)
EN_LABELS: list[tuple[str, str, str]] = [
    ("HRMS-PR-008", "IBAN/", "Bank Name"),
    ("HRMS-PR-008", "Bank Name Account / IBAN", "Account / IBAN"),
    ("HRMS-PR-006", ". Residency No Residency Expiry", "Residency No. / Expiry"),
]


def _apply(conn, pairs, direction: str) -> int:
    changed = 0
    for code, old, new in pairs:
        a, b = (old, new) if direction == "up" else (new, old)
        row = conn.execute(sa.text(
            "SELECT id, body_html FROM document_templates WHERE code = :c"
        ), {"c": code}).fetchone()
        if not row or not row[1] or a not in row[1]:
            continue
        conn.execute(sa.text(
            "UPDATE document_templates SET body_html = :b WHERE id = :i"
        ), {"b": row[1].replace(a, b), "i": row[0]})
        changed += 1
    return changed


def upgrade() -> None:
    bind = op.get_bind()
    n = _apply(bind, ROWS, "up") + _apply(bind, EN_LABELS, "up")
    print(f"[migration v1n2o3p4q5r] نُظّف {n} صًفا من نوائب الصيغ")


def downgrade() -> None:
    bind = op.get_bind()
    _apply(bind, EN_LABELS, "down")
    _apply(bind, ROWS, "down")
