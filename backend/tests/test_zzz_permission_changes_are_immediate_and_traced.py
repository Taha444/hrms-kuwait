# -*- coding: utf-8 -*-
"""M02 #5 — تعديل الصلاحية يسري فورًا (منحًا وسحبًا)، وضبطُ المصفوفة يقيّد ما سُحب وما مُنح."""
from sqlalchemy import select

from app import models
from app.database import SessionLocal
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")


def _hr_export(client):
    h = auth_headers(login(client, *HR))
    return client.get("/api/reports/employees", headers=h, params={"fmt": "csv"}).status_code


def test_a_grant_and_a_revoke_take_effect_on_the_very_next_request(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    db = SessionLocal()
    hr_id = db.scalar(select(models.User.id).where(models.User.civil_id == HR[0]))
    db.close()
    assert _hr_export(client) == 403
    try:
        r = client.post(f"/api/users/{hr_id}/permissions", headers=admin,
                        json={"perm_codes": ["export_reports"]})
        assert r.status_code == 200, r.text
        assert _hr_export(client) == 200, "المنحةُ لم تسرِ فورًا"
    finally:
        client.delete(f"/api/users/{hr_id}/permissions/export_reports", headers=admin)
    assert _hr_export(client) == 403, "السحبُ لم يسرِ فورًا"


def test_setting_the_matrix_records_what_was_removed_and_granted(client):
    admin = auth_headers(login(client, "000000000000", "admin123"))
    db = SessionLocal()
    hr_id = db.scalar(select(models.User.id).where(models.User.civil_id == HR[0]))
    db.close()
    cat = client.get("/api/users/permission-matrix", headers=admin).json()["pages"]
    page = next(p for p in cat if p["actions"])
    try:
        r = client.post(f"/api/users/{hr_id}/matrix", headers=admin,
                        json={"grants": {page["code"]: [page["actions"][0]]}})
        assert r.status_code == 200, r.text
        db = SessionLocal()
        row = db.scalars(select(models.AuditLog).where(
            models.AuditLog.action == "set_permission_matrix",
            models.AuditLog.entity_id == hr_id).order_by(models.AuditLog.id.desc())).first()
        assert row and row.after_json and f"{page['code']}.{page['actions'][0]}" in row.after_json["granted"]
        assert "granted" in (row.before_json or {}) and row.detail
        db.close()
    finally:
        client.post(f"/api/users/{hr_id}/matrix/reset", headers=admin)
