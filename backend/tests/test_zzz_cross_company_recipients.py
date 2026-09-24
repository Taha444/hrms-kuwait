# -*- coding: utf-8 -*-
"""متعدّد الشركات يستلم تنبيهات كل شركاته (SW-011، 2026-09-24).

قيس على الإنتاج: المندوب الحكومي الوحيد عضوٌ في الشركات الخمس و``company_id`` عنده الأولى،
فتراخيص الشركات الأخرى المنتهية (أحدُها منذ 1195 يومًا) لم تصل مهمةً إلى أحد.
"""
import secrets
from datetime import timedelta

from sqlalchemy import select

from app import models
from app.clock import today as kuwait_today
from app.database import SessionLocal
from app.notifications import daily_scan, users_by_role
from app.security import hash_password
from tests.conftest import purge


def test_a_linked_member_receives_the_alerts_of_every_company_he_belongs_to():
    db = SessionLocal()
    home = models.Company(name="شركة الأم للتنبيه")
    away = models.Company(name="شركة أخرى للتنبيه")
    db.add_all([home, away])
    db.flush()
    pro = models.User(civil_id="777" + secrets.token_hex(4)[:9].translate(str.maketrans("abcdef", "123456")),
                      password_hash=hash_password("x12345678"), full_name="مندوب متعدد",
                      role="delegate", company_id=home.id, is_cross_company=True)
    db.add(pro)
    db.flush()
    emp = models.Employee(company_id=away.id, name="سجل المندوب هناك", status="active")
    db.add(emp)
    db.flush()
    db.add(models.UserCompanyLink(user_id=pro.id, company_id=away.id, employee_id=emp.id))
    lic = models.License(company_id=away.id, name="ترخيص منتهٍ", license_no="ZZ/1",
                         status="active", expiry_date=kuwait_today() - timedelta(days=100))
    db.add(lic)
    db.commit()
    ids = dict(home=home.id, away=away.id, pro=pro.id, lic=lic.id, emp=emp.id)
    try:
        assert pro.id in [u.id for u in users_by_role(db, away.id, ["delegate"])], "لا يُعدّ مستلمًا"
        assert pro.id in [u.id for u in users_by_role(db, home.id, ["delegate"])]
        daily_scan(db)
        got = db.scalars(select(models.Task).where(
            models.Task.type == "license_expiring", models.Task.assignee_user_id == pro.id,
            models.Task.related_entity_id == lic.id)).all()
        assert got, "ترخيص شركةٍ ينتمي إليها لم يصله"
        assert all(t.company_id == away.id for t in got)
        # والمنتهي يُقال منتهيًا لا «قارب على الانتهاء» ولا «خلال -100 يومًا».
        assert "منتهي" in got[0].title and "قارب" not in got[0].title, got[0].title
        assert "منذ 100 يومًا" in got[0].detail and "-100" not in got[0].detail, got[0].detail
    finally:
        db.rollback()
        purge(db, "tasks", [t.id for t in db.scalars(select(models.Task).where(
            models.Task.assignee_user_id == ids["pro"])).all()])
        purge(db, "licenses", [ids["lic"]])
        purge(db, "user_company_links", [x.id for x in db.scalars(select(models.UserCompanyLink).where(
            models.UserCompanyLink.user_id == ids["pro"])).all()])
        purge(db, "users", [ids["pro"]])
        purge(db, "employees", [ids["emp"]])
        purge(db, "companies", [ids["home"], ids["away"]])
        db.commit()
        db.close()
