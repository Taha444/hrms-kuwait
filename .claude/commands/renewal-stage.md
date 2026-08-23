---
description: نفّذ مرحلة واحدة من مسار التجديد — مرّر اسم الحالة
---

المرحلة: $ARGUMENTS

```bash
python3 .claude/hrms/scripts/renewal.py --show $ARGUMENTS
```

اقرأ شروط الخروج المعروضة، واقرأ السكيل المختص:
- `EXPIRY_DETECTED` / `RENEWAL_STARTED` → `hrms-renewal-alert-to-case`
- `CONTRACT_*` / `SENT_TO_EMPLOYEE` / `AWAITING_*` / `EMPLOYEE_SIGNED_*` / `RETURNED_TO_PRO` / `GOVERNMENT_PROCESSING` / `FINAL_PACKAGE_UPLOADED` → `hrms-renewal-contract-signing`
- `OCR_PROCESSED` / `DATA_CONFIRMED` → `hrms-renewal-ocr-verification`
- `DOCUMENTS_UPDATED` / `FINAL_VERIFICATION` / `COMPLETED` → `hrms-renewal-propagation`

ثم:
1. افحص ما هو موجود فعلا في الكود لهذه المرحلة — لا تفترض
2. نفّذ الناقص فقط
3. تأكد أن **كل شرط خروج** متحقق — اذكرها واحدا واحدا بحالته
4. اختبر الانتقال من الحالة السابقة وإلى الحالة التالية
5. تأكد أن الحدث سُجِّل في Timeline بـ Actor و Role و Timestamp و Renewal ID
6. سجّل البنود المتأثرة بدليل

اختبر على **GUF و MUF** وبحساب الدور الحقيقي لكل مرحلة.
