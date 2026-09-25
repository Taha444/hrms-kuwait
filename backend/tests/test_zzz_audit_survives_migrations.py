# -*- coding: utf-8 -*-
"""M22 #7 — لا ترحيلَ (ولا تراجعَ عنه) يُسقط جدول التدقيق أو أعمدته أو يحذف صفوفه.

كان ``downgrade`` في ``2b1c2d3e4f50`` يُسقط قبل/بعد والفاعلَ الأصلي ومعرّفَ الربط — أثرَ قراراتٍ
لا يُستعاد؛ وترحيلٌ لاحق كتب القاعدة صراحةً («لا حذف») دون أن يُفرَض على الأول.
"""
import re
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"
#: الترحيل الأول: ``downgrade`` فيه هو التراجعُ الكاملُ إلى قاعدةٍ فارغة — يُسقط كلَّ جدول بطبيعته.
INITIAL_REVISION = "68862c46506d_initial_schema.py"
DESTRUCTIVE = re.compile(
    r"drop_table\([^)]*audit_log|drop_column\([^)]*audit_log|DELETE\s+FROM\s+audit_log|"
    r"TRUNCATE\s+(TABLE\s+)?audit_log|DROP\s+TABLE\s+(IF\s+EXISTS\s+)?audit_log", re.I)


def test_no_migration_destroys_audit_log_data():
    offenders = []
    for f in sorted(VERSIONS.glob("*.py")):
        if f.name == INITIAL_REVISION:
            continue
        text = f.read_text(encoding="utf-8")
        if "audit_log" not in text:
            continue
        if DESTRUCTIVE.search(text):
            offenders.append(f.name)
        # حلقةُ إسقاطٍ على أعمدة الجدول (لا يظهر اسمه في السطر نفسه)
        for m in re.finditer(r"for\s+col\s+in\s*\(([^)]*)\)\s*:\s*\n\s*op\.drop_column\(\s*\"audit_log\"", text):
            offenders.append(f.name)
    assert not offenders, f"ترحيلاتٌ تُتلف سجلّ التدقيق: {sorted(set(offenders))}"
