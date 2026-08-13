# خريطة المعمارية — أين يُتَّخذ كل قرار

نتيجة SKILL-1 (repo-recon). الغرض: تحديد **مكان القرار** لكل موضوع قبل كتابة أي كود،
حتى يقع الإصلاح على الطبقة الصحيحة لا على أقرب سطر.

## الطبقات

| الطبقة | المسار | ملاحظات |
|---|---|---|
| نماذج ORM | `backend/app/models.py` | SQLAlchemy 2.0، ~50 عمودًا في `Employee` |
| المخططات | `backend/app/schemas.py` | Pydantic v2. **تنبيه:** `EmployeeOut` مستقل عمدًا عن `EmployeeIn` |
| الصلاحيات | `backend/app/permissions.py` | `ROLE_DEFAULT_PERMS` + منح فردية عبر `UserPermission` |
| حراس الطلب | `backend/app/deps.py` | `require_perm`, `resolve_scope`, `assert_same_company` |
| محرك المسار | `backend/app/workflow.py` | سلاسل الاعتماد، الأثر، الإنهاء |
| المهام/الإشعارات | `backend/app/notifications.py` + `notification_templates.py` | 74 قالبًا |
| الرواتب | `backend/app/payroll.py` | حساب الحضور والغياب والخصم |
| نهاية الخدمة | `backend/app/eos.py` | يحسب رصيد الإجازة مستقلًا |
| المستندات/OCR | `backend/app/ocr.py`, `routers/documents.py` | استخراج تواريخ الانتهاء |
| الانتهاء/التجديد | `backend/app/renewal.py`, `scheduler.py` | المسح اليومي |
| i18n | `frontend/src/i18n.tsx` + `labels.ts` | `labels.ts` هو الـlabel map المركزي |
| التوجيه والقائمة | `frontend/src/App.tsx` | `useAccess()` يوحّد القائمة وحارس المسار |

## مكان القرار لكل موضوع

| السؤال | الملف·الدالة | يخص البنود |
|---|---|---|
| **مَن يعتمد المرحلة الحالية؟** | `workflow.py::can_decide` (سطر 489) + `resolve_stage_approvers` | QA-01, 02, 10 |
| **ما مراحل هذا الطلب؟** | `workflow.py::_chain(rt)` — يقرأ `approval_chain_json` من نوع الطلب | QA-10 |
| **كم يوم غياب؟** | `payroll.py` سطر 48–67 | QA-03, 04, 24 |
| **كم رصيد الإجازة؟** | مصدران: `Employee.annual_leave_balance` + `eos.py` (حساب استحقاق) | QA-05 |
| **متى ينتهي المستند؟** | `ocr.py::_parse_date` → `Document.expiry_date` / `Permit.expiry_date` | QA-06, 19, 28 |
| **عدادات لوحة التحكم** | `routers/dashboard.py::dashboard` — استعلامات `count()` محلية | QA-19, 20 |
| **مَن يرى صفحة كذا؟** | `App.tsx::useAccess()` + حارس المسار + `require_perm` على الخادم | QA-21, 23, 29 |
| **الجلسة والتحقق الثنائي** | `routers/auth.py::login` + `security.py::decode_token` | QA-30, 31 |
| **نص ظاهر للمستخدم** | `i18n.tsx` (المفاتيح) + `labels.ts` (الـenums) | QA-07, 13, 14, 17, 22, 25, 27 |
| **مهمة أم إشعار؟** | `notifications.py::create_task` — لا فصل حالي بين النوعين | QA-11, 12 |
| **سجل التدقيق** | `deps.py::audit` | QA-26 |

## ملاحظات معمارية تؤثر على الإصلاح

1. **`can_decide` فيه تجاوز إداري ضمني** (سطر 497): `company_manager` و`company_owner`
   يعتمدان أي مرحلة إلا في الطلبات السرّية. هذا قرار تصميمي مقصود سابقًا
   (FIX-014) لكنه يخالف QA-01.

2. **رصيد الإجازة له مصدران**: عمود `annual_leave_balance` (يُخصم منه الآن عبر
   `_apply_leave` وسجل `leave_ledger`)، وحساب استحقاق في `eos.py` يعتمد سنوات
   الخدمة. الرقمان مختلفان بطبيعتهما — ولذلك ظهر 30 مقابل 92.16.

3. **عدادات لوحة التحكم تستعلم محليًا** ولا تستدعي نفس دوال الصفحات التفصيلية،
   فالانحراف بينهما متوقع بنيويًا لا عرضيًا.

4. **لا فرق بين Task وNotification** في النموذج: كلاهما صف في `tasks`.

5. **`payroll.py` لا يقصّ الفترة على `hire_date`** ولا يميّز «لا سجل» عن «غائب».
