# -*- coding: utf-8 -*-
"""M16 #1 — نوافذ الانتهاء (90/30) من مصدرٍ واحد: كل الشاشات تُجمع على حدودها."""
import re
from pathlib import Path

from app import expiry_windows as W, renewal
from app.notifications import EXPIRY_THRESHOLDS
from app.routers import operations, pro

APP = Path(__file__).resolve().parents[1] / "app"
SURFACES = ("routers/dashboard.py", "routers/org.py", "routers/renewals.py", "routers/operations.py",
            "routers/pro.py", "renewal.py")


def test_every_surface_agrees_on_the_boundary_days():
    for d in (-1, 0, W.URGENT_DAYS, W.URGENT_DAYS + 1, W.WINDOW_DAYS, W.WINDOW_DAYS + 1, None):
        assert operations._urgency(d) == W.urgency(d)
        assert pro._urgency(d) == ("none" if d is None else W.urgency(d))
    assert renewal.classify(W.WINDOW_DAYS + 1) is None
    assert renewal.classify(W.WINDOW_DAYS) == "early"
    assert renewal.classify(W.URGENT_DAYS + 1) == "early"
    assert renewal.classify(W.URGENT_DAYS) == "normal"
    assert max(EXPIRY_THRESHOLDS) == W.WINDOW_DAYS and W.URGENT_DAYS in EXPIRY_THRESHOLDS


def test_no_surface_re_hardcodes_the_windows():
    literal = re.compile(r"timedelta\(days=(90|30)\)|(days_left|days)\s*(<=|>)\s*(90|30)\b")
    offenders = {f: literal.findall((APP / f).read_text(encoding="utf-8")) for f in SURFACES}
    offenders = {f: v for f, v in offenders.items() if v}
    assert not offenders, f"عتباتٌ مكتوبة يدويًا خارج expiry_windows: {offenders}"
