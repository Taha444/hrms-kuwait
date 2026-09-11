# -*- coding: utf-8 -*-
"""الورديات: صار لها تعريف وإسناد، وأثرهما مقيس.

**العطل**: الوردية تُقرأ عند كل بصمة (``_compute_in_status``) وفي
المسيّر، ولا سبيل إلى تعريفها إلا بالواجهة البرمجية — ولا إلى **إسنادها**
لموظف أصًلا.

**وما يترتّب على غيابها ليس نقص ميزة بل خطأ صامت**: من لا وردية له
يُوسَم «حاضر» دائًما مهما كان وقت بصمته. فشركة بلا ورديات تقرأ تقارير
حضور نظيفة تماًما — ولا أحد فيها متأخّر أبًدا.

**وسجلٌّ يُنشأ ولا يُعدَّل**: خطأ في وقت البدء كان يبقى إلى الأبد ويُخطئ
في وسم كل حضور بعده، وعلاجه الوحيد وردية ثانية وإعادة إسناد الجميع.
"""
from __future__ import annotations

import inspect
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app import models
from app.clock import KUWAIT_TZ
from app.database import SessionLocal
from app.routers import attendance as att
from tests.conftest import auth_headers, login

HR = ("100000000002", "hr12345")     # يملك manage_attendance
EMP = ("100000000101", "emp12345")

FRONT = Path(__file__).resolve().parents[2] / "frontend"
PAGE = FRONT / "src" / "pages" / "Shifts.tsx"
PROFILE = FRONT / "src" / "pages" / "EmployeeProfile.tsx"
APP = FRONT / "src" / "App.tsx"
I18N = FRONT / "src" / "i18n.tsx"


def _emp():
    db = SessionLocal()
    try:
        return db.scalar(select(models.Employee).where(
            models.Employee.civil_id == EMP[0]))
    finally:
        db.close()


def test_a_shift_can_be_defined_and_corrected(client):
    """**جوهر البناء**: تُعرَّف الوردية وتُصحَّح — لا تُنشأ فتُخلَّد."""
    hdr = auth_headers(login(client, *HR))
    r = client.post("/api/shifts", headers=hdr, json={
        "name": "دوام مسائي", "start_time": "14:00:00", "end_time": "22:00:00",
        "work_days": "0,1,2,3,4", "grace_minutes": 10})
    assert r.status_code == 201, r.text[:250]
    sid = r.json()["id"]

    upd = client.put(f"/api/shifts/{sid}", headers=hdr, json={
        "name": "دوام مسائي", "start_time": "15:00:00", "end_time": "23:00:00",
        "work_days": "0,1,2,3,4", "grace_minutes": 5})
    assert upd.status_code == 200, upd.text[:250]

    db = SessionLocal()
    try:
        sh = db.get(models.Shift, sid)
        assert sh.start_time == time(15, 0) and sh.grace_minutes == 5
    finally:
        db.close()


def test_the_correction_is_recorded_because_it_changes_marking(client):
    """وتعديل وردية يمسّ وسم حضور من عليها — فيُقيَّد بما كان وما صار."""
    hdr = auth_headers(login(client, *HR))
    sid = client.post("/api/shifts", headers=hdr, json={
        "name": "قياس التدقيق", "start_time": "09:00:00", "end_time": "18:00:00",
        "work_days": "0,1", "grace_minutes": 20}).json()["id"]
    client.put(f"/api/shifts/{sid}", headers=hdr, json={
        "name": "قياس التدقيق", "start_time": "07:00:00", "end_time": "16:00:00",
        "work_days": "0,1", "grace_minutes": 0})

    db = SessionLocal()
    try:
        row = db.scalar(select(models.AuditLog).where(
            models.AuditLog.action == "update_shift",
            models.AuditLog.entity_id == sid))
    finally:
        db.close()
    assert row is not None, "تعديل الوردية بلا أثر في التدقيق"
    assert row.before_json and row.after_json, "قُيّد التعديل بلا ما كان وما صار"


def test_the_list_shows_who_is_actually_on_each_shift(client):
    """**ووردية لا أحد عليها لا تفعل شيًئا** — فالعدد معروض لا مخفيّ.

    من يعرّف وردية ثم لا يُسندها يظنّ الحضور مضبوًطا وهو لم يتغيّر.
    """
    hdr = auth_headers(login(client, *HR))
    sid = client.post("/api/shifts", headers=hdr, json={
        "name": "بلا أحد", "start_time": "08:00:00", "end_time": "17:00:00",
        "work_days": "0", "grace_minutes": 15}).json()["id"]

    rows = client.get("/api/shifts", headers=hdr).json()
    mine = next(x for x in rows if x["id"] == sid)
    assert mine["employee_count"] == 0, mine
    assert all("employee_count" in x for x in rows)


def test_assigning_a_shift_changes_how_attendance_is_marked(client):
    """**والأثر الحقيقي**: بلا وردية «حاضر» دائًما، ومعها يُحتسب التأخير.

    وهذا ما يجعل الشاشة ميزًة لا صًفا في جدول: تُقاس السلسلة كاملة —
    تعريف، ثم إسناد، ثم تغيّر الوسم.
    """
    emp = _emp()
    db = SessionLocal()
    try:
        fresh = db.get(models.Employee, emp.id)
        had = fresh.shift_id
        fresh.shift_id = None
        db.commit()
    finally:
        db.close()

    # **ولحظاُت القياس بتوقيت الكويت** — وكانت تُبنى بتوقيت UTC كأن
    # ساعَة الوردية غرينتشية. وهو الافتراض الخاطئ نفسه الذي كان في
    # الشيفرة: «الثامنة» تُكتب محلّية وتُقرأ UTC. فلمّا صحّت الشيفرة سقط
    # الحارس — لأنه كان يحمل العطل في بياناته.
    def _at(hour: int, minute: int = 0) -> datetime:
        local = datetime.now(KUWAIT_TZ).replace(
            hour=hour, minute=minute, second=0, microsecond=0)
        return local.astimezone(timezone.utc)

    late = _at(11, 0)
    db = SessionLocal()
    try:
        fresh = db.get(models.Employee, emp.id)
        # بلا وردية: حاضر مهما تأخّر
        assert att._compute_in_status(db, fresh, late) == "present"

        shift = models.Shift(company_id=fresh.company_id, name="قياس الوسم",
                             start_time=time(8, 0), end_time=time(17, 0),
                             work_days="0,1,2,3,4", grace_minutes=15)
        db.add(shift); db.flush()
        fresh.shift_id = shift.id
        db.commit()

        fresh = db.get(models.Employee, emp.id)
        assert att._compute_in_status(db, fresh, late) == "late", (
            "أُسندت الوردية ولم يتغيّر الوسم"
        )
        # وداخل السماح يبقى حاضًرا — الحدّ يعمل في الاتجاهين.
        on_time = _at(8, 10)
        assert att._compute_in_status(db, fresh, on_time) == "present"

        fresh.shift_id = had
        db.commit()
    finally:
        db.close()


def test_the_employee_profile_can_assign_a_shift():
    """**وتعريف بلا إسناد عبث**: الحقل يقبله الخادم وكان بلا مدخل."""
    page = PROFILE.read_text(encoding="utf-8")
    assert 'id="epf-edit-shift"' in page, "لا مدخل لإسناد وردية"
    assert "shift_id: e.shift_id" in page, "النموذج لا يُملأ بالوردية الحالية"
    assert "sh_employee_none_hint" in page, (
        "لا تحذير لمن بلا وردية — يُوسَم حاضًرا دائًما بلا أن يعرف أحد"
    )


def test_the_shift_field_is_actually_editable_on_the_server():
    """والمدخل مبنيٌّ على ما يقبله الخادم — لا على ظنّ."""
    src = (Path(__file__).resolve().parents[1] / "app" / "routers"
           / "employees.py").read_text(encoding="utf-8")
    assert '"shift_id"' in src, "الخادم لم يعد يقبل إسناد الوردية"


def test_the_screen_says_what_happens_without_a_shift():
    """ومن يقرأ تقرير حضور بلا متأخّرين يحتاج أن يعرف لماذا."""
    page = PAGE.read_text(encoding="utf-8")
    assert "sh_no_shift_note" in page
    assert "sh_unused" in page, "لا إشارة إلى وردية بلا موظفين"


def test_the_screen_has_a_way_in():
    """وشاشة بلا رابط غير موجودة عملًيا."""
    app = APP.read_text(encoding="utf-8")
    assert 'to="/shifts"' in app and 'path="/shifts"' in app
    assert "import Shifts" in app


def test_every_label_exists_in_both_languages():
    """ونصٌّ ناقص في لغة يظهر مفتاًحا خاًما على الشاشة."""
    import re

    text = PAGE.read_text(encoding="utf-8") + PROFILE.read_text(encoding="utf-8")
    i18n = I18N.read_text(encoding="utf-8")
    keys = set(re.findall(r't\("(sh_[a-z_0-9]+)"\)', text))
    assert keys, "لا مفاتيح — تحقّق من الشاشة"
    for k in sorted(keys):
        at = i18n.find(f"{k}: {{")
        assert at >= 0, f"المفتاح «{k}» غير معرَّف"
        nxt = re.search(r"\n  [a-z_0-9]+: ", i18n[at + len(k):])
        entry = i18n[at:at + len(k) + (nxt.start() if nxt else 400)]
        assert "ar:" in entry and "en:" in entry, f"«{k}» ناقص في إحدى اللغتين"


def test_no_label_key_is_defined_twice_and_none_leaks_markdown():
    """ولا مفتاح مكرَّر، ولا ماركداون يُعرَض حرفًيا."""
    import collections
    import re

    text = I18N.read_text(encoding="utf-8")
    keys = re.findall(r"^  ([a-z_0-9]+):\s*\{", text, re.M)
    dupes = [k for k, n in collections.Counter(keys).items() if n > 1]
    assert not dupes, f"مفاتيح مكرَّرة: {dupes}"
    leaks = re.findall(r'(?:ar|en): "([^"]*\*\*[^"]*)"', text)
    assert not leaks, f"ماركداون في نصّ يُعرَض حرفًيا: {leaks[:3]}"
