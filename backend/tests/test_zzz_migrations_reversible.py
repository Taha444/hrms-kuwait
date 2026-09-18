# -*- coding: utf-8 -*-
"""خطة التراجع (DLV-26) تقوم على ترحيلاٍت تُعكَس — فيُقاس ذلك.

التراجُع عن نشرٍة فيها ترحيٌل يمرّ بـ``alembic downgrade``؛ وترحيٌل بلا
عكٍس يعمل يجعل الخطَة ورقًة. فهنا: قاعدٌة جديدة تُبنى بالترحيلات كلّها، ثم
تُعكَس آخُر عشرة، ثم تُعاد — بلا خطأ، وإلى الرأس نفسه. والنافذُة متحرّكة:
كلُّ ترحيٍل جديد يدخلها فيُقاس عكُسه قبل أن يُنشر.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _alembic(url: str, *args: str) -> str:
    env = dict(os.environ, DATABASE_URL=url, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, f"alembic {' '.join(args)}:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}"
    return r.stdout + r.stderr


def _current(url: str) -> str | None:
    m = re.search(r"^([0-9a-z]{8,})(?: \(head\))?\s*$", _alembic(url, "current"), re.M)
    return m.group(1) if m else None


def test_the_last_ten_migrations_reverse_and_reapply(tmp_path):
    url = f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    _alembic(url, "upgrade", "head")
    head = _current(url)
    assert head, "لم يُقرأ رأس الترحيلات"
    _alembic(url, "downgrade", "-10")
    back = _current(url)
    assert back and back != head, back
    _alembic(url, "upgrade", "head")
    assert _current(url) == head
