# -*- coding: utf-8 -*-
"""
محرك التنبيهات التلقائية. يولّد التنبيهات ديناميكيًا بناءً على قواعد:
- قرب/تجاوز انتهاء الإقامة وإذن العمل
- قرب/تجاوز انتهاء الترخيص
- قرب/تجاوز انتهاء المستندات
- تجاوز عدد العمالة الفعلي للحد المسموح في الترخيص
"""
from datetime import date

import db


def _days_left(expiry):
    if not expiry:
        return None
    try:
        return (date.fromisoformat(str(expiry)[:10]) - date.today()).days
    except ValueError:
        return None


def _severity(days_left):
    if days_left is None:
        return "info"
    if days_left < 0:
        return "expired"     # منتهي
    if days_left <= 7:
        return "critical"    # حرج
    return "warning"         # تحذير


def generate_alerts(company_id=None, lead_days_default=30):
    """
    يولّد قائمة التنبيهات. إذا حُدِّد company_id فالنطاق شركة واحدة،
    وإلا فكل الشركات (للإدارة العليا).
    """
    alerts = []
    where_company = "WHERE company_id=?" if company_id else ""
    params = (company_id,) if company_id else ()

    # عتبة التنبيه لكل شركة
    lead_map = {}
    for c in db.query("SELECT id, alert_lead_days FROM companies"):
        lead_map[c["id"]] = c["alert_lead_days"] or lead_days_default

    # ---- الإقامات وأذونات العمل ----
    permits = db.query(
        f"""SELECT p.*, e.name AS employee_name
            FROM permits p JOIN employees e ON e.id = p.employee_id
            {('WHERE p.company_id=?' if company_id else '')}""",
        params,
    )
    kind_label = {"residency": "إقامة", "work_permit": "إذن عمل"}
    for p in permits:
        dl = _days_left(p["expiry_date"])
        lead = lead_map.get(p["company_id"], lead_days_default)
        if dl is not None and dl <= lead:
            alerts.append({
                "type": "permit",
                "category": kind_label.get(p["kind"], p["kind"]),
                "severity": _severity(dl),
                "days_left": dl,
                "company_id": p["company_id"],
                "title": f"{kind_label.get(p['kind'], p['kind'])} الموظف {p['employee_name']}",
                "detail": f"تنتهي بتاريخ {p['expiry_date']}",
                "expiry_date": p["expiry_date"],
                "entity_id": p["employee_id"],
            })

    # ---- التراخيص ----
    licenses = db.query(f"SELECT * FROM licenses {where_company}", params)
    for lic in licenses:
        dl = _days_left(lic["expiry_date"])
        lead = lead_map.get(lic["company_id"], lead_days_default)
        if dl is not None and dl <= lead:
            alerts.append({
                "type": "license",
                "category": "ترخيص",
                "severity": _severity(dl),
                "days_left": dl,
                "company_id": lic["company_id"],
                "title": f"ترخيص: {lic['name']}",
                "detail": f"ينتهي بتاريخ {lic['expiry_date']}",
                "expiry_date": lic["expiry_date"],
                "entity_id": lic["id"],
            })

        # تجاوز عدد العمالة المسموح
        allowed = lic["allowed_workers"] or 0
        if allowed > 0:
            actual = db.query(
                "SELECT COUNT(*) AS c FROM employees WHERE license_id=? AND status='active'",
                (lic["id"],), one=True,
            )["c"]
            if actual > allowed:
                alerts.append({
                    "type": "capacity",
                    "category": "تجاوز عمالة",
                    "severity": "critical",
                    "days_left": None,
                    "company_id": lic["company_id"],
                    "title": f"تجاوز الحد المسموح في ترخيص: {lic['name']}",
                    "detail": f"العمالة الفعلية {actual} مقابل المسموح {allowed}",
                    "expiry_date": None,
                    "entity_id": lic["id"],
                })

    # ---- المستندات ----
    documents = db.query(f"SELECT * FROM documents {where_company}", params)
    for doc in documents:
        dl = _days_left(doc["expiry_date"])
        lead = lead_map.get(doc["company_id"], lead_days_default)
        if dl is not None and dl <= lead:
            alerts.append({
                "type": "document",
                "category": "مستند",
                "severity": _severity(dl),
                "days_left": dl,
                "company_id": doc["company_id"],
                "title": f"مستند: {doc['title']}",
                "detail": f"ينتهي بتاريخ {doc['expiry_date']}",
                "expiry_date": doc["expiry_date"],
                "entity_id": doc["id"],
            })

    # ترتيب: المنتهي أولًا ثم الأقرب انتهاءً
    order = {"expired": 0, "critical": 1, "warning": 2, "info": 3}
    alerts.sort(key=lambda a: (order.get(a["severity"], 9),
                               a["days_left"] if a["days_left"] is not None else 9999))
    return alerts
