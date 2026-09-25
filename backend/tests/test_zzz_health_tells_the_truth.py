# -*- coding: utf-8 -*-
"""M24 — لوحة الصحة تقول الحقيقة: تُنذر بما ينقص، وتعرض كلَّ فحصٍ ترجعه.

١) ``environment_report`` كان يفحص ثلاث مكتباتٍ ويترك ``pypdf`` التي تستوردها ``fill()``:
   فقالت لوحة الإنتاج «جاهز» (``can_render_pdf``) والعقد يسقط 500 لكل موظف (2026-09-24).
٢) النسخة الاحتياطية خارج الخادم غائبة عن الإنتاج ولا شيء في اللوحة يقول ذلك — سطرُ إقلاعٍ
   وحده. فصار فحصٌ ``backup`` يُعلن ``not_configured`` بمتغيّراته.
٣) الشاشة «حالة النظام» كانت تعرض 9 بطاقات من 12 فحصًا: لا العقد ولا رابط التحقق ولا الحسابات
   الافتراضية. فالحارس يشتقّ مفاتيح الفحوص من الاستجابة نفسها.
"""
from __future__ import annotations

import sys
from pathlib import Path

from tests.conftest import auth_headers, login

SCREEN = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "SystemHealth.tsx"


def test_a_missing_generator_library_makes_the_contract_check_degraded(monkeypatch):
    from app.gov_contract_form import environment_report

    assert environment_report()["missing_libs"] == [], "بيئة الاختبار تنقصها مكتبة"
    monkeypatch.setitem(sys.modules, "pypdf", None)   # import pypdf → ImportError
    r = environment_report()
    assert "pypdf" in r["missing_libs"]
    assert r["can_render_pdf"] is False and r["status"] == "degraded"
    assert "pypdf" in r["note"]


def test_the_health_report_declares_the_offsite_backup_state(client, monkeypatch):
    monkeypatch.delenv("BACKUP_S3_BUCKET", raising=False)
    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY", raising=False)
    admin = auth_headers(login(client, "000000000000", "admin123"))
    body = client.get("/api/health/deep", headers=admin).json()
    bk = body["checks"].get("backup")
    assert bk, "لا فحص للنسخة الاحتياطية في لوحة الصحة"
    assert bk["status"] == "not_configured" and bk["configured"] is False
    assert "BACKUP_S3_BUCKET" in bk["note"]


def test_the_system_health_screen_renders_every_check_the_endpoint_returns(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    checks = client.get("/api/health/deep", headers=admin).json()["checks"]
    src = SCREEN.read_text(encoding="utf-8")
    missing = sorted(k for k in checks if f"c.{k}" not in src)
    assert not missing, f"فحوصٌ يرجعها /health/deep ولا بطاقة لها في الشاشة: {missing}"
