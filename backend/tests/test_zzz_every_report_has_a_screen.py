# -*- coding: utf-8 -*-
"""M21 #1 — كل تقريرٍ على الخادم له شاشةٌ في الواجهة: النقطةُ بلا شاشة عطلٌ صامت (لا أحد يراها فلا يُكتشف فيها شيء).

كان «تشغيل المسارات» (AC-15) نقطةً بلا شاشة — فيه نسبةُ خرق المهلة التي قالت 100% بلا طلبٍ واحد (SW-012) ولم يرها أحد.
الحارس يشتقّ التقارير من الراوتر نفسه، فتقريرٌ يُضاف غدًا بلا شاشةٍ يُسقطه.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _report_paths():
    src = (ROOT / "backend" / "app" / "routers" / "reports.py").read_text(encoding="utf-8")
    paths = re.findall(r'@router\.get\("(/[^"]*)"', src)
    return sorted({"/reports" + re.sub(r"/\{[^}]+\}.*", "", p) for p in paths})


def test_every_report_endpoint_is_used_by_a_screen():
    ui = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "frontend" / "src").rglob("*.tsx"))
    paths = _report_paths()
    assert len(paths) >= 5, paths
    orphans = [p for p in paths if p not in ui]
    assert not orphans, f"تقاريرُ بلا شاشة: {orphans}"


def test_the_workflow_report_labels_exist_in_both_languages():
    tr = (ROOT / "frontend" / "src" / "i18n_screens.ts").read_text(encoding="utf-8")
    for key in ("rep_wf_title", "rep_wf_sla", "rep_wf_stage", "rep_wf_return_rate"):
        line = next(l for l in tr.splitlines() if l.strip().startswith(key + ":"))
        assert "ar:" in line and "en:" in line
