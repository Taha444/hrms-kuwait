# -*- coding: utf-8 -*-
"""من يحرّر الصيغ — قرار المالك (2026-09-18): صاحب الشركات + HR.

كان تحريُرها وإنشاؤها لـsuper_admin وحده، وقاعدُة المالك تمنع منحه لأحد:
فلا أحَد عند العميل يغيّر نصَّ شهادٍة أو قرار — ولا «القوالب الخمسة» التي
خالفت نسختها في الشيفرة وقيل إنها «تُطبَّق من شاشة الصيغ».

- **صاحب الشركات** يحرّر الصيغة المشتركة نفسها (مشتركٌة بين شركاته).
- **HR** يحرّر لشركته: تحريُر صيغٍة مشتركة يُنشئ **نسخًة لشركته** تحلّ
  محلّها عندها — فلا يغيّر HR شركٍة نصَّ الشركات الأخرى.
- **الصيغة المخالفة للشيفرة** يطبّق صاحب الشركات نسختَها بزّر — نسخٌة
  جديدة في السجل لا كتابٌة صامتة.
"""
from __future__ import annotations

from sqlalchemy import select

from app import models
from app.database import SessionLocal
from app.seed import DEFAULT_TEMPLATES
from tests.conftest import auth_headers, login

OWNER = ("111111111111", "owner123")
HR1 = ("100000000002", "hr12345")
HR2 = ("200000000002", "hr12345")
MGR = ("100000000001", "manager123")

CODE = "HRMS-PR-009"
SEED = {e[0]: e[4] for e in DEFAULT_TEMPLATES}


def _global():
    db = SessionLocal()
    try:
        t = db.scalar(select(models.DocumentTemplate).where(
            models.DocumentTemplate.code == CODE,
            models.DocumentTemplate.company_id.is_(None)))
        return t.id, t.name, t.category, t.body_html
    finally:
        db.close()


def _cleanup(global_body):
    db = SessionLocal()
    try:
        t = db.scalar(select(models.DocumentTemplate).where(
            models.DocumentTemplate.code == CODE,
            models.DocumentTemplate.company_id.is_(None)))
        t.body_html = global_body
        for c in db.scalars(select(models.DocumentTemplate).where(
                models.DocumentTemplate.code == CODE,
                models.DocumentTemplate.company_id.isnot(None))).all():
            for v in db.scalars(select(models.DocumentTemplateVersion).where(
                    models.DocumentTemplateVersion.template_id == c.id)).all():
                db.delete(v)
            db.delete(c)
        db.commit()
    finally:
        db.close()


def _body(name, category, text):
    return {"name": name, "category": category, "body_html": f"<p>{text}</p>"}


def test_the_manager_does_not_edit_templates(client):
    tid, name, cat, body = _global()
    r = client.put(f"/api/templates/{tid}", headers=auth_headers(login(client, *MGR)),
                   json=_body(name, cat, "تعديل المدير"))
    assert r.status_code == 403, (r.status_code, r.text[:150])


def test_hr_edits_a_company_copy_and_leaves_the_shared_one(client):
    tid, name, cat, body = _global()
    try:
        r = client.put(f"/api/templates/{tid}", headers=auth_headers(login(client, *HR1)),
                       json=_body(name, cat, "نص شركة واحد"))
        assert r.status_code == 200, r.text[:200]
        db = SessionLocal()
        try:
            assert db.get(models.DocumentTemplate, tid).body_html == body, "تغيّر النص المشترك"
            copy = db.scalar(select(models.DocumentTemplate).where(
                models.DocumentTemplate.code == CODE,
                models.DocumentTemplate.company_id == 1))
            assert copy is not None and "نص شركة واحد" in copy.body_html
            copy_id = copy.id
        finally:
            db.close()
        mine = client.get("/api/templates", headers=auth_headers(login(client, *HR1))).json()
        ids = {t["id"] for t in mine if t["code"] == CODE}
        assert ids == {copy_id}, ids
        # والشركة الأخرى ترى المشتركة كما هي، ولا تحرّر نسخة غيرها.
        other = client.get("/api/templates", headers=auth_headers(login(client, *HR2))).json()
        assert {t["id"] for t in other if t["code"] == CODE} == {tid}
        r = client.put(f"/api/templates/{copy_id}", headers=auth_headers(login(client, *HR2)),
                       json=_body(name, cat, "تسلّل"))
        assert r.status_code in (403, 404), r.status_code
    finally:
        _cleanup(body)


def test_the_owner_edits_the_shared_template_with_a_version(client):
    tid, name, cat, body = _global()
    try:
        h = auth_headers(login(client, *OWNER))
        before = len(client.get(f"/api/templates/{tid}/versions", headers=h).json())
        r = client.put(f"/api/templates/{tid}", headers=h, json=_body(name, cat, "نص المالك"))
        assert r.status_code == 200, r.text[:200]
        after = client.get(f"/api/templates/{tid}/versions", headers=h)
        assert after.status_code == 200 and len(after.json()) == before + 1
    finally:
        _cleanup(body)


def test_the_owner_applies_the_system_version_of_a_drifted_template(client):
    tid, name, cat, body = _global()
    try:
        db = SessionLocal()
        try:
            db.get(models.DocumentTemplate, tid).body_html = "<p>نص قديم يخالف الشيفرة</p>"
            db.commit()
        finally:
            db.close()
        h = auth_headers(login(client, *OWNER))
        row = next(t for t in client.get("/api/templates", headers=h).json() if t["id"] == tid)
        assert row.get("drifted") is True
        assert client.post(f"/api/templates/{tid}/apply-system-version",
                           headers=auth_headers(login(client, *HR1))).status_code == 403
        r = client.post(f"/api/templates/{tid}/apply-system-version", headers=h)
        assert r.status_code == 200, r.text[:200]
        db = SessionLocal()
        try:
            assert db.get(models.DocumentTemplate, tid).body_html == SEED[CODE]
        finally:
            db.close()
    finally:
        _cleanup(body)
