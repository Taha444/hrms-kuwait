---
name: hrms-acceptance-verification
description: التحقق من تنفيذ بنود مواصفة Kuwait HRMS V2.2 — 15 معيار قبول إلزامي، 18 اختبار مسار (RW-01..18)، 20 اختبار مستند (DOC-01..20)، و7 فحوص بنيوية، مع سجل امتثال وسكريبتات فحص. استخدم هذا السكيل إلزاميا عند أي سؤال عن "هل تم تنفيذ البند؟" أو "ما المتبقي؟" أو عند مراجعة PR أو كتابة اختبارات أو قبل أي إطلاق مرحلة. استخدمه أيضا بعد كل تعديل على المحرك أو الصلاحيات أو المستندات للتأكد أن البند لم ينكسر.
---

# HRMS Acceptance Verification (V2.2 §13، §14، §30)

## الأدوات
```bash
python3 .claude/hrms/scripts/check.py --init            # أول مرة فقط
python3 .claude/hrms/scripts/check.py                   # التقرير الكامل
python3 .claude/hrms/scripts/check.py --gate engine     # بوابة واحدة
python3 .claude/hrms/scripts/check.py --pending         # الناقص فقط
python3 .claude/hrms/scripts/check.py --set RW-08 pass --note "spec/tasks/claim_spec.rb"
bash .claude/hrms/scripts/antipattern-scan.sh .         # فحص الأنماط الممنوعة
```
السجل المرجعي: `.claude/hrms/compliance.json` — **لا تعدّله** إلا عند تغيّر المواصفة.
الحالة الفعلية: `.claude/hrms/status.json` — يُحدَّث مع كل بند يُنجَز.

## قاعدة الإثبات
**البند لا يُعتبر منفذا بادعاء.** كل بند يُقفَل بـ `pass` يحتاج **دليلا واحدا على الأقل**:
- مسار ملف اختبار آلي يغطيه، أو
- استعلام قاعدة بيانات يثبت القيد، أو
- لقطة/مخرَج فعلي (PDF، استجابة API بكود الحالة).

عند `--set X pass` بلا `--note` — اعتبرها غير مكتملة واسأل عن الدليل.

## الخريطة: البند ← الاختبار المقترح
| البند | نوع الاختبار المناسب |
|---|---|
| AC-06, RW-01, RW-02, RW-16 | اختبار API سلبي (403/409) بمستخدم غير معيّن أو تفويض منته |
| AC-07, RW-10 | اختبار تكامل: NEEDS_INFO → استكمال → نفس `request_id` ونفس المراجع |
| AC-08, RW-18 | اختبار وحدة على `policy_version` snapshot |
| AC-09, RW-09 | اختبار محرك: خطوتان متتاليتان لنفس الشخص |
| RW-08 | اختبار تزامن: 4 مستخدمين، Claim واحد ينجح |
| RW-17, DOC-06 | اختبار idempotency: نفس الطلب مرتين → أثر واحد |
| RW-14, DOC-12 | اختبار ALL_OF مع جهة OPEN → لا FINAL CLEARED |
| RW-15, DOC-18, AC-12 | حقن فشل في مولّد PDF → حالة الطلب لا تتغير |
| DOC-02, DOC-16, DOC-17 | فحص محتوى PDF المُولَّد نصيا (استخراج نص + assertions) |
| DOC-09, DOC-10, DOC-19 | اختبار صفحة QR: الحقول الظاهرة والمحجوبة |
| STR-01, STR-02, STR-04 | استعلام عد بسيط على الكتالوج |
| STR-03 | تكرار على كل PRN تاريخي عبر Alias Resolver |

## بوابات المراحل (§12)
لا تنتقل لمرحلة قبل إغلاق بوابتها:

| المرحلة | العمل | بوابة الخروج |
|---|---|---|
| 0 — قرار الأعمال | اعتماد المصفوفة والحدود والسياسات والمسؤولين | توقيع Product Owner و HR و Finance و PRO + مراجعة قانونية محلية |
| 1 — تنظيف الكتالوج | 53 → 29 Canonical، حذف التكرار، تحديد internal/contextual | كل دور يرى allowlist صحيحا؛ Employee 15-18 خدمة → `--gate catalog` |
| 2 — المحرك والصلاحيات | Step Types، Resolver، Claim، Delegation، SLA، Field Permissions، Audit | لا action لغير المعيّن؛ لا self-approval؛ NEEDS_INFO يستأنف → `--gate engine` + `--gate permissions` |
| 3 — Pilot منخفض المخاطر | Leave، Permission، Salary Certificate، Personal Data، Bank Update، Expense، Advance، Attendance Correction | سيناريوهات happy/negative/exception كاملة على بيانات Demo |
| 4 — العمليات المتخصصة | Payroll objections، discipline، grievance، overtime، PRO/residency | فصل القرار عن التحقق والتنفيذ وإثبات الخصوصية |
| 5 — الخروج والمستندات | Resignation، EOS، Clearance، document lifecycle، acknowledgements | إخلاء طرف متواز، PDF حقيقي، Audit كامل → `--gate documents` + `--gate templates` |
| 6 — الترحيل والإطلاق | ترحيل المفتوح، مراقبة SLA، تدريب، تعطيل المسارات القديمة | لا طلبات يتيمة أو مزدوجة، rollback مجرّب، تقارير تشغيلية → `--gate migration` |

## عند مراجعة PR
1. شغّل `antipattern-scan.sh` على الـ diff.
2. حدّد أي بنود يمسّها التغيير من السجل.
3. تحقق أن اختبارات تلك البنود موجودة وتمر.
4. حدّث `status.json` بالبنود التي أُغلقت في هذا الـ PR.
5. أبلغ بالبنود التي **انكسرت** بسبب التغيير — لا تكتفِ بالجديدة.

## الحكم النهائي للمهندس (§33)
**لا يُعتبر أي Workflow مكتملا** إذا كان يتطلب مستندا ولم ينتج نسخة نهائية قابلة للاستخدام والتوقيع والتحقق والأرشفة.
**ولا يُعتبر أي PDF رسميا** إذا كان مجرد Print لصفحة الطلب أو لمسار الموافقات.
