---
name: hrms-release-readiness
description: جاهزية الإطلاق والتسليم في Kuwait HRMS — هوية النسخة والـ Migration Version، النسخ الاحتياطي والمراقبة، تنظيف بيانات QA والحسابات التجريبية، الترحيل الآمن، والتدريب داخل النظام، وصياغة تقرير التسليم Fixed/Not Completed. استخدم هذا السكيل إلزاميا عند الاقتراب من التسليم، وعند أي عمل على النشر أو الـ Migrations أو بيئة العميل، وعند كتابة تقرير الحالة النهائي للمراجع.
---

# HRMS Release Readiness (عناقيد OPS + DATA + UX — 16 بندا)

## 1. هوية النسخة — `OPS-01`
الحالة الحالية: Build `v1.0.0` / Commit `3a74741` / الحكم **NO-GO**.

المطلوب إظهاره في النظام:
```
Version · Commit · Built At · Deployed At · Environment
Migration Version · Feature Flags
```
- **عدم ظهور «Development»** على رابط التسليم.
- **ربط كل اختبار بالـ Build المنشور نفسه** — لا اختبار على بناء وتسليم آخر.
- System Health: `Data` و `Migrations` = **PASS**.
- `OPS-02`: تحديث PWA/Service Worker حتى لا يظل المستخدم على Build قديم.

## 2. انضباط الـ Retest — `OPS-05` (blocker)
- **لا تُرفع Build جديدة أثناء الـ Retest النهائي.**
- المراجعة القادمة **مركّزة على البنود المحددة فقط، وليست Audit جديدا**.
- **لا Scope جديد ولا تحسينات شكلية جانبية** — منصوص عليه صراحة في طلب المراجعة.

## 3. تنظيف بيئة العميل — `OPS-04` و `ACCESS-10`
- [ ] تعطيل Reset Demo Data وأدوات الاختبار
- [ ] عزل وتنظيف بيانات QA حتى لا تختلط ببيانات العميل
- [ ] حذف شهادة الراتب التجريبية من ملف أحمد محمود علي (`DOC-01`)
- [ ] تنظيف الشركة التجريبية المكررة (`DATA-01`)
- [ ] إزالة 2FA من QA Employee Test (`ACCESS-08`)
- [ ] Rotate لمفاتيح Kiosk وعدم عرضها كاملة
- [ ] تعطيل كل كلمات السر التجريبية وإزالة بيانات الدخول الظاهرة
- [ ] حساب Super Admin الحالي داخلي — **لن يُسلَّم للعميل**
- [ ] عدم تفعيل النصوص القانونية الحساسة كـ Production Final قبل اعتماد المختص والمخوّل

## 4. التشغيل والاستضافة — `OPS-03`
```
Backup فعلي للقاعدة والملفات · اختبار Restore
Health Checks · Monitoring · Error Tracking · Structured Logs
Rate Limits · Job Monitoring
تنبيه عند فشل: Daily Scan · Notification · PDF Generation
Rollback Plan · Smoke Test بعد النشر · Data/File Retention
Staging منفصلة عن نسخة العميل
```

## 5. سلامة البيانات — `DATA-01` `DATA-02` `DATA-03`
- **السجل التجاري فريد** (`DATA-01` blocker): التحقق في الواجهة والخادم **وقاعدة البيانات** · رسالة واضحة قبل إنشاء الثانية · عدم إنشاء فروع أو موظفين أو Users لشركة فشل إنشاؤها.
- **إنشاء الموظف ذري** (`DATA-02`): Invalid أو Partial لا ينشئ أي سجل · لا User أو Task أو Audit نجاح لموظف فشل · Transaction و Rollback كاملان · الحقول الإلزامية تشمل Attendance Policy أو Exempt Reason.
- **التصدير** (`DATA-03`): Civil ID و Employee ID و Phone و Passport و IBAN كنص **بدون Scientific Notation أو فقد أصفار** · UTF-8 · Masking حسب الدور · سبب للتصدير الحساس · Export Audit.

## 6. الترحيل الآمن — `DATA-04`
- عدم حذف الطلبات والمستندات القديمة.
- Legacy Aliases تحل إلى Canonical Definitions.
- **عدم إنشاء طلبات جديدة بالأنواع القديمة بعد التفعيل** (مرتبط بـ `CAT-01` و `API-02`).
- الطلبات المفتوحة: `Legacy Continue` أو `Controlled Migration` — قرار صريح لكل طلب.
- Dual Read مؤقت عند الحاجة · Feature Flags حسب الشركة.
- **Rollback لا يكرر أي معاملة أو مستند.**
- الحفاظ على Attachments و Timeline و Audit والتاريخ.
- **عدم تشغيل النظامين القديم والجديد بالتوازي كحل دائم.**

## 7. Employee ID — `UX-04` (blocker)
غير موجود ولا ظاهر في: إنشاء الموظف · قائمة الموظفين · ملف الموظف · My Profile · البحث · التقارير · المستندات الرسمية.

المولّد: **اختصار الشركة + كود الفرع + تسلسل الموظف داخل الفرع**
- Unique و **آمن عند الإنشاء المتزامن** (قفل أو تسلسل على مستوى قاعدة البيانات، لا `count()+1`).
- لا يُدخل يدويا · لا يُعاد استخدام رقم موظف مؤرشف.
- ثابت بعد نقل الموظف إلا بقاعدة معتمدة صراحة.
- Read Only في كل الشاشات والتقارير والمستندات · **Search بالـ Employee ID**.
- **معالجة الموظفين الحاليين بدونه** — خطوة ترحيل منفصلة.
- مرتبط بـ `DOC-03`: المستند يطبع حاليا رقم الـ DB بدل الرقم الوظيفي.

## 8. التدريب داخل النظام — `UX-06`
الموجود حاليا Welcome panel فقط، وليس Tutorial.

المواصفة: يظهر أول Login **لكل User + Role** · 5 إلى 8 خطوات · Highlight للعناصر · Next/Back/Skip/Finish · زر **Replay Tour** في User Menu · حفظ `tour_completed` لكل User و Role · عربي وإنجليزي و RTL/LTR · Help page أو FAQ قصيرة · **Empty States تشرح الخطوة التالية**.

المحتوى لكل دور:
| الدور | المحاور |
|---|---|
| Employee | Dashboard · My Profile و Employee ID · My Attendance · تقديم الطلب · متابعة الحالة و Needs Info · Tasks/Notifications/Help |
| Branch Supervisor | نطاق الفرع · Employees · Attendance Review · Approvals · Tasks · Reports |
| HR | Create Employee · Link User · Edit Employee · Attendance Review · Requests/Approvals · Documents/Signatures/Renewals · Reports |
| Manager | Company scope · Approvals · Attendance Review · Users/Permissions · Reports · Branches/Kiosk |
| Accountant | اختيار الشركة والفترة · Closed Attendance · Payroll Preview · Prepare/Approve/Lock · Adjustments · Reports |
| PRO | Assigned Scope · Operations Alerts · Start Renewal · Documents/Fees/Reference · Verification · Archive/History · Help |

## 9. اتساق الواجهة — `UX-01` `UX-07`
القيم الخام المتبقية في الواجهة العربية: `active · delegate · digest · sla_escalation · prepared · residency`
(تم إصلاح: `qr · gps · both · none`)

بقية المطلوب: عربي وإنجليزي متسقان · RTL/LTR · **توقيت الكويت** · تنسيق تاريخ موحد · KWD وتقريب معتمد · لا أسماء Field أو Status تقنية · Sidebar بارتفاع كامل مع Scroll داخلي · لا قص أو تداخل · Desktop و Mobile · Labels و Keyboard و Focus و Contrast و Zoom 200%.

## 10. تقرير التسليم
```bash
python3 .claude/hrms/scripts/defects.py --report
```
يخرج قائمة بكل بند وحالته `Fixed / Not Completed / Skipped` مع الدليل.

**أرفق معه إلزاميا:**
- Full Commit SHA
- وقت الـ Deployment
- Migration Version

**قبل الإرسال:** تأكد أن `--sev blocker` لا يعرض أي بند مفتوح. أي blocker مفتوح = الحكم يبقى NO-GO.
