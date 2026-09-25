# -*- coding: utf-8 -*-
"""M22 #5 — الخادم يُرجع UTC عاريًا ("…T20:26:59")؛ الواجهة تختمه UTC فلا يتبع العرضُ منطقةَ جهاز القارئ."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "frontend" / "src" / "utils" / "datetime.ts"


@pytest.mark.skipif(shutil.which("node") is None, reason="node غير متاح")
def test_a_naive_server_timestamp_is_read_as_utc_in_any_reader_timezone():
    text = SRC.read_text(encoding="utf-8")
    regex_line = re.search(r"^const _NAIVE_DATETIME = .*;$", text, re.M).group(0)
    stamp_line = re.search(r"^  const v = .*;$", text, re.M).group(0)
    js = (regex_line.replace("const ", "var ", 1) + "\n"
          "function f(raw){ " + stamp_line.strip() + " return new Date(v).toISOString(); }\n"
          "console.log([f('2026-09-25T20:26:59.031810'), f('2026-09-25 20:26:59'),"
          " f('2026-09-25T23:26:59+03:00'), f('2026-09-25T20:26:59Z')].join('|'));")
    for tz in ("America/New_York", "Asia/Kuwait", "Pacific/Auckland"):
        out = subprocess.run(["node", "-e", js], capture_output=True, text=True,
                             env={**__import__("os").environ, "TZ": tz}).stdout.strip()
        assert out == ("2026-09-25T20:26:59.031Z|2026-09-25T20:26:59.000Z|"
                       "2026-09-25T20:26:59.000Z|2026-09-25T20:26:59.000Z"), (tz, out)
