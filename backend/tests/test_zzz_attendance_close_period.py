# -*- coding: utf-8 -*-
"""M11 — بابا الإقفال والاستعلام يرفضان فترةً ليست شهرًا حقيقيًا (كانت 2026-99 تُقفَل، وتُسقط close-status بـ500)."""
import pytest

from tests.conftest import auth_headers, login

BAD = ["2026-99", "2026-13", "2026-00", "abc-def", "2026-1", "2026", "٢٠٢٦-٠١"]


@pytest.mark.parametrize("period", BAD)
def test_a_period_that_is_not_a_month_is_refused_everywhere(client, period):
    hr = auth_headers(login(client, "100000000002", "hr12345"))
    for method, path, extra in (("post", "close-month", {}), ("post", "reopen-month", {"reason": "x"}),
                                ("get", "close-status", {})):
        r = getattr(client, method)(f"/api/attendance/{path}", headers=hr,
                                    params={"period": period, "company_id": 1, **extra})
        assert r.status_code == 400, f"{path} {period!r} -> {r.status_code}"
