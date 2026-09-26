# -*- coding: utf-8 -*-
"""M15 #2 — مهمةُ التنبيه تقود إلى مكان العمل: كانت «تجديد الإقامة: فلان» طريقًا مسدودًا بلا وجهة.

الوجهةُ من الخادم (مصدرٌ واحد) والحارس يقيس أنها **مسارٌ موجودٌ فعلًا** في الواجهة، فوجهةٌ إلى شاشةٍ غير موجودة تُسقطه.
"""
import re
from pathlib import Path
from types import SimpleNamespace

from app.routers.tasks import _TARGET_BY_ENTITY, task_target_path

ROOT = Path(__file__).resolve().parents[2] / "frontend" / "src"


def _routes():
    app = (ROOT / "App.tsx").read_text(encoding="utf-8")
    return set(re.findall(r'path="([^"]+)"', app))


def _exists(target, routes):
    """المسارُ موجودٌ حرفيًا أو يطابق نمطًا بمعامل (/requests/:id)."""
    for r in routes:
        if r == "*":                      # المسارُ الشامل يطابق كلَّ شيء فلا يُثبت وجود شاشة
            continue
        pattern = "/".join("[^/]+" if part.startswith(":") else re.escape(part) for part in r.split("/"))
        if re.fullmatch(pattern, target):
            return True
    return False


def test_a_residency_alert_leads_to_the_renewals_screen_and_every_target_is_a_real_route():
    t = SimpleNamespace(type="renew_residency", related_entity_type="permit", related_entity_id=5)
    assert task_target_path(t) == "/renewals"
    t2 = SimpleNamespace(type="renew_work_permit", related_entity_type="permit", related_entity_id=5)
    assert task_target_path(t2) == "/pro"
    assert task_target_path(SimpleNamespace(type="x", related_entity_type="request", related_entity_id=9)) == "/requests/9"
    assert task_target_path(SimpleNamespace(type="x", related_entity_type=None, related_entity_id=None)) is None
    routes = _routes()
    samples = list(_TARGET_BY_ENTITY.values()) + ["/renewals", "/pro", "/requests/9", "/employees/3"]
    missing = [s for s in samples if not _exists(s, routes)]
    assert not missing, f"وجهاتٌ لا مسارَ لها في الواجهة: {missing}"


def test_the_inbox_renders_the_link():
    src = (ROOT / "pages" / "Tasks.tsx").read_text(encoding="utf-8")
    assert "x.target_path" in src and "<Link" in src
