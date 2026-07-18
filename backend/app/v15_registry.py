# -*- coding: utf-8 -*-
"""V1.5 Consolidated Revision 2 — Migration Registry & Legacy Alias Resolver.

هذا الملف يمثّل قاعدة الترحيل الآمن (Phase 1) من التصميم السابق (49 نموذج طلب + 42 قالب
PRN) إلى التصميم الرسمي V1.5 المعتمد في V1.6 Executive Book:

- 9 Layouts (LAY-01..LAY-09) — قوالب طباعة موحّدة
- 25 Canonical Documents (OD-001..OD-025) — المستندات الرسمية
- 6 Reports (RPT-001..RPT-006) — التقارير والكشوف (منفصلة عن مستندات المستخدم)
- 2 Internal System Records (SYS-001..SYS-002) — سجلات تقنية داخلية
- Canonical Workflow Registry (WF-001..WF-029) — 29 مسار
- Legacy Alias Resolver — يترجم الأكواد القديمة للـ canonical دون كسر البيانات

القاعدة الحاكمة (V1.5 ص 4): "عند أي تعارض، تسري V1.5 في الكتالوج والمسارات والحالات
والمستندات والتقارير والسجلات التقنية. تبقى إصلاحات الجودة والبيانات والرواتب والتدقيق
والأمان في V1.4 واجبة التنفيذ."

مصدر جداول الإحلال: V1.5 Consolidated Revision 2, Migration Registry pages 5-8.
"""
from __future__ import annotations


# ==============================================================================
# 9 Shared Layouts (V1.5 صفحة 9)
# ==============================================================================
LAYOUTS: dict[str, dict] = {
    "LAY-01": {"name": "Certificate / Letter", "name_ar": "خطابات وشهادات خارجية", "used_by": ["OD-001", "OD-002", "OD-003", "OD-004"]},
    "LAY-02": {"name": "Employment Decision / Notice", "name_ar": "قرارات وظيفية وانضباطية", "used_by": ["OD-005", "OD-006", "OD-008", "OD-010", "OD-011", "OD-015", "OD-020", "OD-024"]},
    "LAY-03": {"name": "Agreement / Acknowledgement", "name_ar": "اتفاقات وإقرارات", "used_by": ["OD-009", "OD-019", "OD-022"]},
    "LAY-04": {"name": "Investigation / Minutes", "name_ar": "تحقيق ومحاضر", "used_by": ["OD-007"]},
    "LAY-05": {"name": "Settlement / Calculation", "name_ar": "تسويات وحسابات", "used_by": ["OD-017", "OD-023", "OD-025"]},
    "LAY-06": {"name": "Clearance / Checklist", "name_ar": "إخلاء وفحص وحزمة سفر", "used_by": ["OD-012", "OD-014", "OD-016"]},
    "LAY-07": {"name": "Government Transaction Cover", "name_ar": "أغلفة متابعة حكومية", "used_by": ["OD-013"]},
    "LAY-08": {"name": "Transaction Receipt / Change Confirmation", "name_ar": "إيصالات وتحديثات", "used_by": ["OD-018", "OD-021"]},
    "LAY-09": {"name": "Report / Statement", "name_ar": "تقارير وكشوف", "used_by": ["RPT-001", "RPT-002", "RPT-003", "RPT-004", "RPT-005", "RPT-006"]},
}


# ==============================================================================
# 25 Canonical Documents (OD-001..OD-025) — المستندات الرسمية (V1.5 pages 10-11)
# كل OD يستخدم layout واحد ويحدد الحقول الإلزامية وطبيعة السرية.
# ==============================================================================
CANONICAL_DOCUMENTS: dict[str, dict] = {
    "OD-001": {"name_ar": "شهادة راتب", "name_en": "Salary Certificate", "layout": "LAY-01",
               "required": ["employee_name", "civil_id", "job_title", "hire_date", "gross_salary", "target_entity"],
               "produces_pdf": True, "confidential": False, "spec_page": 10},
    "OD-002": {"name_ar": "شهادة لمن يهمه الأمر / خبرة / NOC", "name_en": "NOC / Experience / To Whom It May Concern",
               "layout": "LAY-01",
               "required": ["employee_name", "job_title", "hire_date", "target_entity", "purpose"],
               "produces_pdf": True, "confidential": False, "spec_page": 10},
    "OD-003": {"name_ar": "خطاب موجه لجهة رسمية", "name_en": "Official Entity Letter", "layout": "LAY-01",
               "required": ["employee_name", "target_entity", "subject"],
               "produces_pdf": True, "confidential": False, "spec_page": 10},
    "OD-004": {"name_ar": "عرض وظيفي", "name_en": "Employment Offer Letter", "layout": "LAY-01",
               "required": ["candidate_name", "job_title", "basic_salary", "start_date"],
               "produces_pdf": True, "confidential": False, "spec_page": 10},
    "OD-005": {"name_ar": "قرار تغيير وظيفي (نقل/راتب/موقع/ترقية)",
               "name_en": "Employment Change Decision", "layout": "LAY-02",
               "required": ["employee_name", "old_state", "new_state", "effective_date", "reason"],
               "produces_pdf": True, "confidential": False, "spec_page": 10,
               "legal_note_ar": "قرار إداري رسمي — لا ينفذ الأثر المالي قبل اعتماد المالية."},
    "OD-006": {"name_ar": "قرار إنذار / مخالفة", "name_en": "Warning / Violation Decision", "layout": "LAY-02",
               "required": ["employee_name", "incident_date", "incident_summary", "policy_reference"],
               "produces_pdf": True, "confidential": True, "spec_page": 10,
               "legal_note_ar": "توقيع الموظف يفيد العلم والاستلام فقط، ولا يعد إقرارًا بصحة الواقعة."},
    "OD-007": {"name_ar": "محضر تحقيق إداري", "name_en": "Administrative Investigation Minutes",
               "layout": "LAY-04",
               "required": ["employee_name", "investigation_date", "subject", "attendees", "result"],
               "produces_pdf": True, "confidential": True, "spec_page": 10,
               "legal_note_ar": "يحفظ حق الدفاع؛ لا يعد قرارًا نهائيًا حتى اعتماد الجهة المختصة."},
    "OD-008": {"name_ar": "قرار خصم", "name_en": "Deduction Decision", "layout": "LAY-02",
               "required": ["employee_name", "deduction_amount", "reason", "payroll_month"],
               "produces_pdf": True, "confidential": True, "spec_page": 10,
               "legal_note_ar": "لا ينفذ الخصم قبل اكتمال موافقة HR والمالية وإتاحة حق الاعتراض."},
    "OD-009": {"name_ar": "إقرار / رد الموظف", "name_en": "Employee Acknowledgement / Reply",
               "layout": "LAY-03",
               "required": ["employee_name", "received_at", "warning_reference", "response"],
               "produces_pdf": True, "confidential": True, "spec_page": 10},
    "OD-010": {"name_ar": "قرار / نتيجة تظلم", "name_en": "Grievance Decision", "layout": "LAY-02",
               "required": ["employee_name", "against_person", "subject", "decision"],
               "produces_pdf": True, "confidential": True, "spec_page": 10,
               "legal_note_ar": "ملف محدود الاطلاع (Restricted Audit) — يمنع الاطلاع الجانبي."},
    "OD-011": {"name_ar": "قرار اعتماد إجازة", "name_en": "Leave Approval Decision", "layout": "LAY-02",
               "required": ["employee_name", "leave_type", "start_date", "end_date", "days_count"],
               "produces_pdf": True, "confidential": False, "spec_page": 10},
    "OD-012": {"name_ar": "إفادة مالية للسفر", "name_en": "Financial Clearance for Travel", "layout": "LAY-06",
               "required": ["employee_name", "financial_status", "approved_at"],
               "produces_pdf": True, "confidential": False, "spec_page": 10},
    "OD-013": {"name_ar": "غلاف متابعة معاملة حكومية", "name_en": "Government Transaction Cover Sheet",
               "layout": "LAY-07",
               "required": ["employee_name", "transaction_type", "government_entity", "reference_no"],
               "produces_pdf": True, "confidential": False, "spec_page": 10,
               "legal_note_ar": "غلاف متابعة داخلي — النظام لا يُصدر مستندًا حكوميًا مزيفًا؛ الأصل يُرفع من الجهة."},
    "OD-014": {"name_ar": "محضر تسليم/استلام (عهدة أو مستندات)",
               "name_en": "Asset / Document Handover Record", "layout": "LAY-06",
               "required": ["employee_name", "items_list", "condition", "handover_date"],
               "produces_pdf": True, "confidential": False, "spec_page": 11},
    "OD-015": {"name_ar": "قبول استقالة / إنهاء عقد", "name_en": "Resignation Acceptance / Contract End",
               "layout": "LAY-02",
               "required": ["employee_name", "resignation_date", "last_working_day", "notice_period"],
               "produces_pdf": True, "confidential": False, "spec_page": 11},
    "OD-016": {"name_ar": "شهادة إخلاء طرف", "name_en": "Clearance Certificate", "layout": "LAY-06",
               "required": ["employee_name", "assets_status", "documents_status", "finance_status", "department_signoffs"],
               "produces_pdf": True, "confidential": False, "spec_page": 11,
               "legal_note_ar": "لا يغلق بدون توقيع كل الإدارات المعنية."},
    "OD-017": {"name_ar": "تسوية نهاية خدمة", "name_en": "End of Service Settlement", "layout": "LAY-05",
               "required": ["employee_name", "hire_date", "last_working_day", "salary_basis",
                            "entitlements_total", "deductions_total", "net_amount"],
               "produces_pdf": True, "confidential": True, "spec_page": 11,
               "legal_note_ar": "نتيجة مبدئية قابلة للمراجعة قبل الاعتماد النهائي."},
    "OD-018": {"name_ar": "إيصال / تأكيد إجراء (استئذان/تصحيح حضور/إضافي/عودة)",
               "name_en": "Action Receipt / Confirmation", "layout": "LAY-08",
               "required": ["employee_name", "action_type", "reference_id", "effective_date"],
               "produces_pdf": True, "confidential": False, "spec_page": 11},
    "OD-019": {"name_ar": "إقرار استلام عهدة",
               "name_en": "Asset Receipt Acknowledgement", "layout": "LAY-03",
               "required": ["employee_name", "assets_list", "received_at"],
               "produces_pdf": True, "confidential": False, "spec_page": 11},
    "OD-020": {"name_ar": "طلب / نتيجة تدريب", "name_en": "Training Request / Outcome",
               "layout": "LAY-02",
               "required": ["employee_name", "course", "provider", "dates", "cost"],
               "produces_pdf": True, "confidential": False, "spec_page": 11},
    "OD-021": {"name_ar": "إشعار تحديث بيانات (شخصية/بنك/جهة اتصال)",
               "name_en": "Data Update Notice", "layout": "LAY-08",
               "required": ["employee_name", "changed_fields", "updated_at", "approved_by"],
               "produces_pdf": True, "confidential": True, "spec_page": 11},
    "OD-022": {"name_ar": "اتفاقية سلفة / قرض", "name_en": "Advance / Loan Agreement",
               "layout": "LAY-03",
               "required": ["employee_name", "amount", "installments_count", "first_deduction_month",
                            "employee_ack"],
               "produces_pdf": True, "confidential": True, "spec_page": 11,
               "legal_note_ar": "توقيع الموظف يعد إقرارًا صريحًا بجدول الاستقطاع."},
    "OD-023": {"name_ar": "إيصال مصروفات", "name_en": "Expense Reimbursement Receipt", "layout": "LAY-05",
               "required": ["employee_name", "amount", "category", "date", "receipt_ref"],
               "produces_pdf": True, "confidential": False, "spec_page": 11},
    "OD-024": {"name_ar": "قرار اعتراض راتب / خصم", "name_en": "Payroll / Deduction Objection Decision",
               "layout": "LAY-02",
               "required": ["employee_name", "period", "disputed_amount", "decision", "reason"],
               "produces_pdf": True, "confidential": True, "spec_page": 11},
    "OD-025": {"name_ar": "قسيمة راتب", "name_en": "Payslip", "layout": "LAY-05",
               "required": ["employee_name", "period", "basic_salary", "allowances_total",
                            "deductions_total", "net_salary"],
               "produces_pdf": True, "confidential": True, "spec_page": 11,
               "legal_note_ar": "بيانات مالية شخصية — يُخفى IBAN جزئيًا للأدوار بلا صلاحية view_actual."},
}


# ==============================================================================
# 6 Reports (RPT-001..RPT-006) — تقارير مستقلة عن مستندات المستخدم (V1.5 ص 12)
# ==============================================================================
REPORTS: dict[str, dict] = {
    "RPT-001": {"name": "Leave Balance Statement", "name_ar": "بيان رصيد إجازات", "legacy_alias": "PRN-029"},
    "RPT-002": {"name": "Attendance Summary", "name_ar": "ملخص حضور", "legacy_alias": "PRN-030"},
    "RPT-003": {"name": "Late / Absence Statement", "name_ar": "كشف تأخير وغياب", "legacy_alias": "PRN-031"},
    "RPT-004": {"name": "Payroll Summary", "name_ar": "ملخص رواتب", "legacy_alias": "PRN-032"},
    "RPT-005": {"name": "Deductions Report", "name_ar": "تقرير خصومات", "legacy_alias": "PRN-033"},
    "RPT-006": {"name": "Employee Profile Summary", "name_ar": "ملخص ملف موظف", "legacy_alias": "PRN-042"},
}


# ==============================================================================
# 2 Internal System Records (V1.5 ص 12)
# ==============================================================================
SYSTEM_RECORDS: dict[str, dict] = {
    "SYS-001": {"name": "Signature Evidence Record", "name_ar": "سجل إثبات التوقيع الإلكتروني", "legacy_alias": "PRN-040", "visibility": "internal"},
    "SYS-002": {"name": "Legal Review Case", "name_ar": "حالة مراجعة قانونية", "legacy_alias": "PRN-internal", "visibility": "restricted"},
}


# ==============================================================================
# Canonical Workflow Registry (V1.5 pages 5-8 + Workflow Guide)
# 29 canonical workflows (WF-001..WF-029) — تحل محل 53 نوع طلب قديم
# ==============================================================================
CANONICAL_WORKFLOWS: dict[str, dict] = {
    "WF-001": {"name_ar": "طلب إجازة عادي", "name_en": "Normal Leave Request", "od": ["OD-011"]},
    "WF-002": {"name_ar": "إجازة سفر", "name_en": "Travel Leave", "od": ["OD-011", "OD-012", "OD-013"]},
    "WF-003": {"name_ar": "استئذان أثناء الدوام / خروج مبكر", "name_en": "Permission / Early Departure", "od": ["OD-018"]},
    "WF-004": {"name_ar": "تصحيح حضور / تبرير تأخير", "name_en": "Attendance Correction / Late Justification", "od": ["OD-018"]},
    "WF-005": {"name_ar": "شهادة راتب", "name_en": "Salary Certificate", "od": ["OD-001"]},
    "WF-006": {"name_ar": "شهادة لمن يهمه الأمر / خبرة", "name_en": "NOC / Experience Certificate", "od": ["OD-002"]},
    "WF-007": {"name_ar": "تحديث بيانات شخصية / اتصال", "name_en": "Personal / Contact Data Update", "od": ["OD-021"]},
    "WF-008": {"name_ar": "تحديث حساب بنكي", "name_en": "Bank Account Update", "od": ["OD-021"]},
    "WF-009": {"name_ar": "سلفة / قرض", "name_en": "Advance / Loan", "od": ["OD-022"]},
    "WF-010": {"name_ar": "استرداد مصروفات", "name_en": "Expense Reimbursement", "od": ["OD-023"]},
    "WF-011": {"name_ar": "اعتراض راتب", "name_en": "Payroll Objection", "od": ["OD-024"]},
    "WF-012": {"name_ar": "اعتراض خصم", "name_en": "Deduction Objection", "od": ["OD-024"]},
    "WF-013": {"name_ar": "إصدار خصم (داخلي)", "name_en": "Issue Deduction (internal)", "od": ["OD-008"]},
    "WF-014": {"name_ar": "إصدار إنذار / مخالفة (داخلي)", "name_en": "Issue Warning / Violation (internal)", "od": ["OD-006", "OD-009"]},
    "WF-015": {"name_ar": "رد على إنذار", "name_en": "Reply to Warning", "od": ["OD-009"]},
    "WF-016": {"name_ar": "تظلم / شكوى سرّية", "name_en": "Confidential Grievance", "od": ["OD-010"]},
    "WF-017": {"name_ar": "عمل إضافي", "name_en": "Overtime", "od": ["OD-018"]},
    "WF-018": {"name_ar": "تغيير وظيفي (نقل/راتب/موقع/وردية)", "name_en": "Employment Change (transfer/salary/location/shift)", "od": ["OD-005"]},
    "WF-019": {"name_ar": "تجديد إقامة عادية", "name_en": "Normal Residency Renewal", "od": ["OD-013"]},
    "WF-020": {"name_ar": "تجديد إقامة مبكر", "name_en": "Early Residency Renewal", "od": ["OD-013"]},
    "WF-021": {"name_ar": "تجديد إذن عمل", "name_en": "Work Permit Renewal", "od": ["OD-013"]},
    "WF-022": {"name_ar": "تحديث جواز", "name_en": "Passport Update", "od": ["OD-013"]},
    "WF-023": {"name_ar": "تحديث بطاقة مدنية", "name_en": "Civil ID Update", "od": ["OD-013"]},
    "WF-024": {"name_ar": "استقالة", "name_en": "Resignation", "od": ["OD-015"]},
    "WF-025": {"name_ar": "تسوية نهاية خدمة", "name_en": "EOS Settlement", "od": ["OD-017"]},
    "WF-026": {"name_ar": "إخلاء طرف", "name_en": "Clearance", "od": ["OD-016"]},
    "WF-027": {"name_ar": "طلب تدريب", "name_en": "Training Request", "od": ["OD-020"]},
    "WF-028": {"name_ar": "ترقية / مراجعة راتب / بدل", "name_en": "Promotion / Salary Review / Allowance", "od": ["OD-005"]},
    "WF-029": {"name_ar": "طلب عام / تصنيف", "name_en": "General Triage", "od": []},
}


# ==============================================================================
# Legacy → Canonical alias map (V1.5 Migration Registry pages 5-8)
# مفاتيح: أكواد الطلبات القديمة (REQ-*, ADM-*, أسماء seed المختصرة).
# قيم: (canonical_workflow_code, optional_subtype, note)
# ==============================================================================
LEGACY_REQUEST_ALIASES: dict[str, dict] = {
    # V1.4 seed codes (تُستخدم فعلياً في workflow.py DEFAULT_REQUEST_TYPES)
    "leave": {"canonical": "WF-001", "note": "قد يتحول إلى WF-002 لو travel_required=true"},
    "salary_certificate": {"canonical": "WF-005", "note": "Alias retired — استخدم OD-001"},
    "exit_permission": {"canonical": "WF-003", "subtype": "EARLY_DEPARTURE"},
    "advance": {"canonical": "WF-009", "subtype": "ADVANCE"},
    "loan": {"canonical": "WF-009", "subtype": "LOAN"},

    # V1.5 Migration Registry (ص 5-8) — أكواد REQ-* الرسمية
    "REQ-LV-001": {"canonical": "WF-001", "note": "قد يتحول إلى WF-002 حسب travel_required"},
    "REQ-PER-002": {"canonical": "WF-003"},
    "REQ-EXIT-003": {"canonical": "WF-003", "subtype": "EARLY_DEPARTURE"},
    "REQ-LATE-004": {"canonical": "WF-004", "subtype": "LATE_JUSTIFICATION"},
    "REQ-ATT-005": {"canonical": "WF-004", "subtype": "ATTENDANCE_CORRECTION"},
    "REQ-SHIFT-006": {"canonical": "WF-018", "subtype": "SHIFT_CHANGE"},
    "REQ-OT-007": {"canonical": "WF-017", "subtype": "OVERTIME"},
    "REQ-WLOC-008": {"canonical": "WF-018", "subtype": "TEMP_WORKPLACE_ASSIGNMENT"},
    "REQ-MIS-009": {"canonical": "WF-018", "subtype": "EXTERNAL_WORK_MISSION"},
    "REQ-RES-E-010": {"canonical": "WF-020", "subtype": "EARLY_RESIDENCY_RENEWAL"},
    "REQ-RES-N-011": {"canonical": "WF-019", "subtype": "NORMAL_RESIDENCY_RENEWAL"},
    "REQ-PASS-012": {"canonical": "WF-022", "subtype": "PASSPORT_UPDATE"},
    "REQ-CID-013": {"canonical": "WF-023", "subtype": "CIVIL_ID_UPDATE"},
    "REQ-WP-014": {"canonical": "WF-021", "subtype": "WORK_PERMIT_RENEWAL"},
    "REQ-GOV-015": {"canonical": "WF-019", "note": "PRO contextual case — subtype حسب المعاملة"},
    "REQ-TRF-LIC-016": {"canonical": "PRO-COMPANY-CASE", "note": "Internal contextual — لا يظهر للموظف"},
    "REQ-DOC-017": {"canonical": "WF-007", "note": "Rule-based merge — يفصل حسب نوع المستند"},
    "REQ-DATA-018": {"canonical": "WF-007", "subtype": "PERSONAL_DATA_UPDATE"},
    "REQ-BANK-019": {"canonical": "WF-008", "subtype": "BANK_ACCOUNT_UPDATE"},
    "REQ-CONTACT-020": {"canonical": "WF-007", "subtype": "CONTACT_UPDATE"},
    "REQ-CERT-SAL-021": {"canonical": "WF-005", "subtype": "SALARY_CERTIFICATE"},
    "REQ-CERT-EMP-022": {"canonical": "WF-006", "subtype": "TO_WHOM_IT_MAY_CONCERN"},
    "REQ-CERT-EXP-023": {"canonical": "WF-006", "subtype": "EXPERIENCE_CERTIFICATE"},
    "REQ-FILE-024": {"canonical": "DOCUMENTS-MY", "note": "Contextual action — تنزيل/طلب نسخة"},
    "REQ-ADV-025": {"canonical": "WF-009", "subtype": "ADVANCE_OR_LOAN"},
    "REQ-EXP-026": {"canonical": "WF-010", "subtype": "EXPENSE_REIMBURSEMENT"},
    "REQ-ALLOW-027": {"canonical": "WF-028", "subtype": "ALLOWANCE_REVIEW"},
    "REQ-PAY-028": {"canonical": "WF-011", "subtype": "PAYROLL_OBJECTION"},
    "REQ-DED-029": {"canonical": "WF-012", "subtype": "DEDUCTION_OBJECTION"},
    "REQ-GRV-030": {"canonical": "WF-016", "subtype": "CONFIDENTIAL_GRIEVANCE"},
    "REQ-VIO-031": {"canonical": "WF-015", "note": "Contextual appeal — قد يتحول إلى WF-016"},
    "REQ-WARN-032": {"canonical": "WF-015", "subtype": "REPLY_TO_WARNING"},
    "REQ-GEN-033": {"canonical": "WF-029", "subtype": "GENERAL_TRIAGE"},
    "REQ-TRN-034": {"canonical": "WF-027", "subtype": "TRAINING"},
    "REQ-TRF-035": {"canonical": "WF-018", "subtype": "TRANSFER"},
    "REQ-PROMO-036": {"canonical": "WF-028", "subtype": "PROMOTION"},
    "REQ-CON-037": {"canonical": "HR-CONTRACT-CASE", "note": "Internal — تجديد/عدم تجديد عقد"},
    "REQ-RESIGN-038": {"canonical": "WF-024", "subtype": "RESIGNATION_NOTICE"},
    "REQ-EOS-039": {"canonical": "WF-025", "subtype": "EOS_SETTLEMENT"},
    "REQ-CLR-040": {"canonical": "WF-026", "subtype": "CLEARANCE"},

    # ADM-* داخلية (V1.5 ص 8)
    "ADM-ACTUAL-042": {"canonical": "WF-018", "subtype": "SALARY_OR_WORKPLACE_CHANGE"},
    "ADM-DED-043": {"canonical": "WF-013", "subtype": "ISSUE_DEDUCTION"},
    "ADM-VIO-044": {"canonical": "WF-014", "note": "Discipline case — قد يتحول إلى WF-013"},
    "ADM-WARN-045": {"canonical": "WF-014", "subtype": "ISSUE_WARNING"},
    "ADM-MISS-047": {"canonical": "TASK-CONTEXTUAL", "note": "إشعار نقص مستندات داخل الحالة"},
}


# ==============================================================================
# Legacy PRN template → canonical OD/RPT/SYS map
# ==============================================================================
LEGACY_PRN_ALIASES: dict[str, str] = {
    # Certificates & Letters
    "HRMS-PR-001": "OD-001", "PRN-001": "OD-001",
    "HRMS-PR-002": "OD-002", "PRN-002": "OD-002",
    "HRMS-PR-003": "OD-002", "PRN-003": "OD-002",  # experience → NOC subtype
    "HRMS-PR-004": "OD-021", "PRN-004": "OD-021",
    "HRMS-PR-005": "OD-002", "PRN-005": "OD-002",
    "HRMS-PR-006": "RPT-006", "PRN-006": "RPT-006",
    "HRMS-PR-007": "OD-002", "PRN-007": "OD-002",
    "HRMS-PR-008": "OD-021", "PRN-008": "OD-021",
    "HRMS-PR-009": "OD-001", "PRN-009": "OD-001",
    "HRMS-PR-010": "OD-002", "PRN-010": "OD-002",
    # Employment decisions
    "HRMS-PR-011": "OD-004", "PRN-011": "OD-004",
    "HRMS-PR-012": "OD-005", "PRN-012": "OD-005",
    "HRMS-PR-013": "OD-005", "PRN-013": "OD-005",
    "HRMS-PR-014": "OD-015", "PRN-014": "OD-015",
    "HRMS-PR-015": "OD-005", "PRN-015": "OD-005",  # termination decision
    "HRMS-PR-016": "OD-005", "PRN-016": "OD-005",
    "HRMS-PR-017": "OD-005", "PRN-017": "OD-005",
    "HRMS-PR-018": "OD-005", "PRN-018": "OD-005",
    "HRMS-PR-019": "OD-005", "PRN-019": "OD-005",
    "HRMS-PR-020": "OD-005", "PRN-020": "OD-005",
    # Discipline
    "HRMS-PR-021": "OD-008", "PRN-021": "OD-008",
    "HRMS-PR-022": "OD-006", "PRN-022": "OD-006",
    "HRMS-PR-023": "OD-006", "PRN-023": "OD-006",
    "HRMS-PR-024": "OD-007", "PRN-024": "OD-007",
    "HRMS-PR-025": "OD-006", "PRN-025": "OD-006",
    # Attendance / Payroll
    "HRMS-PR-026": "OD-018", "PRN-026": "OD-018",
    "HRMS-PR-027": "OD-011", "PRN-027": "OD-011",
    "HRMS-PR-028": "OD-018", "PRN-028": "OD-018",
    "HRMS-PR-029": "RPT-001", "PRN-029": "RPT-001",
    "HRMS-PR-030": "RPT-002", "PRN-030": "RPT-002",
    "HRMS-PR-031": "RPT-003", "PRN-031": "RPT-003",
    "HRMS-PR-032": "RPT-004", "PRN-032": "RPT-004",
    "HRMS-PR-033": "RPT-005", "PRN-033": "RPT-005",
    # Government
    "HRMS-PR-034": "OD-013", "PRN-034": "OD-013",
    "HRMS-PR-035": "OD-013", "PRN-035": "OD-013",
    "HRMS-PR-036": "OD-013", "PRN-036": "OD-013",
    "HRMS-PR-037": "OD-013", "PRN-037": "OD-013",
    # EOS / Clearance / Assets
    "HRMS-PR-038": "OD-017", "PRN-038": "OD-017",
    "HRMS-PR-039": "OD-016", "PRN-039": "OD-016",
    "HRMS-PR-040": "OD-014", "PRN-040": "OD-014",
    "HRMS-PR-041": "OD-014", "PRN-041": "OD-014",
    # System records
    "HRMS-PR-042": "SYS-001", "PRN-042": "SYS-001",
}


def resolve_request(code: str) -> dict:
    """يعيد الـ canonical workflow لكود طلب قديم أو حديث.

    الاستخدام:
        info = resolve_request("leave")
        # → {"canonical": "WF-001", "note": "قد يتحول ..."}

    لو الكود canonical أصلاً (WF-XXX) يُعاد كما هو. لو غير معروف يُعاد dict فارغ.
    """
    if not code:
        return {}
    if code in CANONICAL_WORKFLOWS:
        return {"canonical": code, "name_ar": CANONICAL_WORKFLOWS[code]["name_ar"]}
    return LEGACY_REQUEST_ALIASES.get(code, {})


def resolve_template(code: str) -> str | None:
    """يعيد الـ canonical OD/RPT/SYS لكود قالب قديم (PRN-XXX أو HRMS-PR-XXX).

    مثال: resolve_template("PRN-001") → "OD-001"
    """
    if not code:
        return None
    if code.startswith(("OD-", "RPT-", "SYS-", "LAY-")):
        return code
    return LEGACY_PRN_ALIASES.get(code)


def migration_version() -> str:
    """رقم إصدار مخطط الترحيل الحالي (يظهر في manifest للتحقق من توافق البيانات)."""
    return "v1.5-consolidated-rev-2"


def summary() -> dict:
    """يعيد ملخص إحصائي لسجل الترحيل — يُستخدم في /api/manifest."""
    return {
        "canonical_workflows": len(CANONICAL_WORKFLOWS),
        "canonical_documents": len(CANONICAL_DOCUMENTS),
        "reports": len(REPORTS),
        "system_records": len(SYSTEM_RECORDS),
        "layouts": len(LAYOUTS),
        "legacy_request_aliases": len(LEGACY_REQUEST_ALIASES),
        "legacy_template_aliases": len(LEGACY_PRN_ALIASES),
        "migration_version": migration_version(),
    }


def resolve_canonical_document(code: str) -> dict | None:
    """يعيد OD متصفة كاملة لكود canonical أو legacy PRN."""
    if not code:
        return None
    if code in CANONICAL_DOCUMENTS:
        return {"od_code": code, **CANONICAL_DOCUMENTS[code]}
    od = LEGACY_PRN_ALIASES.get(code)
    if od and od in CANONICAL_DOCUMENTS:
        return {"od_code": od, "legacy_alias": code, **CANONICAL_DOCUMENTS[od]}
    return None
