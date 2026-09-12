# -*- coding: utf-8 -*-
"""استعالٌم داخل حلقة — كنٌس نتيجُته سالبة، وميزانيٌة تحرس ما قيس.

**القياس**: اثنتان وسبعون حلقًة تستعلم القاعدَة داخلها. **وأكثرُها مهامُّ
ليٍل** ال ينتظرها مستخدم (``daily_scan`` · ``digest_scan`` · تنظيُف
المهامّ). فالسؤاُل عن مسارات الطلب وحدها.

**وقيست ال فُرِضت:**

- ``compute_payroll``: **4.2 استعالم لكل موظف** (54 استعالًما لثالثَة عشر
  موظًفا). فخمسمئٌة ≈ 2076 استعالًما ≈ ثانيتان على Postgres.
- ``attendance_review``: استعالماٌت لكل **موظف** ال لكل صّف، ومقيٌَّد بنافذة
  شهر. فخمسمئٌة ≈ 1500 ≈ ثانيٌة ونصف.

**فال عطل** — بطٌء مقبوٌل لعمٍل شهري. **وال يُحسَّن بالحدس**: الرواتب أحسُّ
شيفرٍة في النظام، والقاعدُة 20 تمنع تغييَرها بال عطٍل مثبَت، و«أربُع
استعالماٍت لكل موظف» ليست عطًلا.

**لكنّ القياس يبقى**: ميزانيٌة سخّية تُمسِك انحداًرا حاًدّا (استعالٌم يُضاف
داخل الحلقة فيصير الضعف) وال تُضيّق على تغييٍر معقول. فالحارُس ال يطلب
تحسيًنا — يمنع **تدهوًرا**.
"""
from __future__ import annotations

import pytest
from sqlalchemy import event, select

from app import models
from app.database import SessionLocal, engine

#: سقٌف سخّي: المقيُس 4.2، والسقُف الضعُف تقريًبا. فتغييٌر معقوٌل يمرّ،
#: واستعالٌم جديٌد داخل الحلقة (يجعلها ~5.2) يمرّ أيًضا — ويُمسَك ما
#: يُضاعِف.
_PAYROLL_BUDGET_PER_EMPLOYEE = 9.0


class _Counter:
    def __init__(self):
        self.n = 0

    def __enter__(self):
        self._fn = lambda *a, **k: setattr(self, "n", self.n + 1)
        event.listen(engine, "before_cursor_execute", self._fn)
        return self

    def __exit__(self, *exc):
        event.remove(engine, "before_cursor_execute", self._fn)
        return False


def test_a_payroll_run_stays_within_its_measured_budget():
    """**ميزانيٌة تُمسِك تدهوًرا، ال تطلب تحسيًنا.**

    فالمقيُس 4.2 استعالم لكل موظف، والسقُف تسعة. ومن يضيف استعالًما داخل
    الحلقة يمرّ؛ ومن يضاعفها يسقط ويُقال له بالرقم.
    """
    from app import payroll

    db = SessionLocal()
    try:
        active = db.scalar(select(models.Employee).where(
            models.Employee.company_id == 1,
            models.Employee.status == "active"))
        if active is None:
            pytest.skip("لا موظف نشط في هذه القاعدة")
        with _Counter() as c:
            res = payroll.compute_payroll(db, 1, 2031, 4)
        n = max(len(res.get("payslips") or []), 1)
    finally:
        db.close()

    per = c.n / n
    assert per <= _PAYROLL_BUDGET_PER_EMPLOYEE, (
        f"استعالماُت المسيّر لكل موظف {per:.1f} — والميزانيُة "
        f"{_PAYROLL_BUDGET_PER_EMPLOYEE}. المقيُس عند كتابة الحارس 4.2؛ "
        f"فهذا تدهوٌر ال تغييٌر معقول.")


def test_the_measurement_itself_is_reproducible():
    """**وميزانيٌة بال قياٍس رقٌم مختَلق** — فيُقاس أن العدّاد يعُدّ."""
    db = SessionLocal()
    try:
        with _Counter() as c:
            db.scalar(select(models.Employee).limit(1))
    finally:
        db.close()
    assert c.n >= 1, "العدّاد ال يرى االستعالمات — فالميزانيُة بال معنى"


def test_the_demo_credentials_hint_cannot_ship_by_accident():
    """**وباٌب يُفتَح بالسهو ليس مغلًقا.**

    تلميُح حسابات العرض في شاشة الدخول محروٌس بـ
    ``VITE_SHOW_DEMO_HINT``، ومتغيّراُت Vite **تُخبَز وقت البناء**. فلو
    أُضيف ملُّف بيئٍة في المستودع يُفعّلها، شُحنت كلمُة مرور الإدارة العليا
    في صفحة الدخول العلنية.
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[2]
    enabling = []
    for p in root.rglob("*"):
        if p.is_dir() or "node_modules" in p.parts or ".git" in p.parts:
            continue
        if p.name.startswith(".env") or p.name in ("Dockerfile", "vite.config.ts",
                                                   "vite.config.js", "package.json"):
            body = p.read_text(encoding="utf-8", errors="ignore")
            if "VITE_SHOW_DEMO_HINT" in body and "true" in body:
                enabling.append(str(p.relative_to(root)))
    assert not enabling, f"ملفاٌت تُفعّل تلميح حسابات العرض: {enabling}"
