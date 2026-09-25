# -*- coding: utf-8 -*-
"""M16 — المسح اليومي لا يُنبّه مرتين على الإقامة الواحدة ولا يُنبّه عن مستند من غادر.

قيس بتشغيل ``daily_scan``: إقامةُ موظفٍ حيّ تُنشئ مهمتين كتصريح ومهمتين كمستند (الإقامة تنعكس
في جدول التصاريح ومسحُها هناك)، وجوازُ موظفٍ حالتُه ``terminated`` يُنشئ مهمتين للمندوبين.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import delete as sa_delete, select

from app import models
from app.clock import today
from app.database import SessionLocal
from app.notifications import daily_scan
from tests.conftest import purge


def _tasks(db, kind, ids):
    return db.scalars(select(models.Task).where(
        models.Task.related_entity_type == kind, models.Task.related_entity_id.in_(ids))).all()


def test_the_scan_does_not_duplicate_permit_alerts_nor_alert_for_departed_staff():
    db = SessionLocal()
    soon = today() + timedelta(days=10)
    made = {}
    try:
        live = models.Employee(company_id=1, name="M16-LIVE", civil_id="777100001", status="active",
                               basic_salary=400, hire_date=date(2020, 1, 1))
        gone = models.Employee(company_id=1, name="M16-GONE", civil_id="777100002",
                               status="terminated", basic_salary=400, hire_date=date(2020, 1, 1))
        db.add_all([live, gone])
        db.flush()

        def doc(emp, code, title):
            d = models.Document(company_id=1, entity_type="employee", entity_id=emp.id,
                                document_type_code=code, title=title, file_path="x", version=1,
                                is_current=True, expiry_date=soon, uploaded_by=1)
            db.add(d)
            return d
        d_gone = doc(gone, "passport", "M16 جواز منتهٍ")
        d_res = doc(live, "residency", "M16 إقامة")
        d_pass = doc(live, "passport", "M16 جواز حيّ")
        permit = models.Permit(company_id=1, employee_id=live.id, kind="residency",
                               status="active", number="M16", expiry_date=soon)
        db.add(permit)
        db.commit()
        made = dict(live=live.id, gone=gone.id, docs=[d_gone.id, d_res.id, d_pass.id],
                    permit=permit.id)

        daily_scan(db)
        db.commit()

        assert not _tasks(db, "document", [d_gone.id]), "جوازُ موظفٍ أُنهيت خدمته يُنبَّه عنه"
        assert not _tasks(db, "document", [d_res.id]), "الإقامة تُنبَّه مرتين (تصريح ومستند)"
        assert _tasks(db, "permit", [permit.id]), "فُقد تنبيهُ التصريح نفسه"
        assert _tasks(db, "document", [d_pass.id]), "جوازُ موظفٍ حيّ لا يُنبَّه عنه"
    finally:
        if made:
            ids = [t.id for k, e in (("document", made["docs"]), ("permit", [made["permit"]]))
                   for t in _tasks(db, k, e)]
            purge(db, "tasks", ids)
            db.execute(sa_delete(models.Document).where(models.Document.id.in_(made["docs"])))
            purge(db, "permits", [made["permit"]])
            purge(db, "employees", [made["live"], made["gone"]])
            db.commit()
        db.close()
