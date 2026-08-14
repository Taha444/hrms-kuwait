# PROGRESS — الحالة الحية لملاحظات QA الـ31

الحالات: `NOT_STARTED` → `IN_PROGRESS` → `FIXED` → `VERIFIED` (أو `BLOCKED` بسبب).
**ممنوع** كتابة `VERIFIED` بعمود دليل فارغ.

| ID | الخطورة | الحالة | السبب الجذري | Commit | الدليل | Sweep (أنواع/شركات/لغات/مسارات) |
|----|---------|--------|--------------|--------|--------|----------------------------------|
| QA-01 | BLOCKER | VERIFIED | C1 — تجاوز ضمني في `can_decide` يعيد True لكل مدير/مالك في أي مرحلة | (هذا الـcommit) | `test_qa01_manager_cannot_approve_a_stage_that_is_not_his` + `test_qa01_no_implicit_override_for_any_role` + `test_qa01_no_sequential_approval_by_same_account` | ✅ / ✅ / n-a / ✅ |
| QA-02 | BLOCKER | VERIFIED | C1 — نفس الدالة: الصندوق مبني عليها | (هذا الـcommit) | `test_qa02_branch_supervisor_receives_the_request` — أُثبت فشله قبل الإصلاح (الطلب في صندوق المدير `{1,2}`) | ✅ / ✅ / n-a / ✅ |
| QA-03 | BLOCKER | VERIFIED | C2 — `payroll.py` كان يعدّ كل يوم بلا سجل غياًبا | (C2) | `test_qa03_unrecorded_days_are_not_deducted` + `test_qa03_recorded_absence_is_still_deducted` — أُثبت الفشل قبل: `assert 10 == 0` | ✅ / ✅ / n-a / ✅ |
| QA-04 | BLOCKER | VERIFIED | C2 — الفترة بلا قصّ على مدة التوظيف | (C2) | `test_qa04_no_absence_before_hire_date` + `test_qa04_attendance_exempt_employee_is_never_charged` — أُثبت الفشل قبل: `assert 0 < 0` | ✅ / ✅ / n-a / ✅ |
| QA-05 | BLOCKER | VERIFIED | C3 — رقمان بمعنيين مختلفين باسم واحد | (C3) | `test_qa05_leave_numbers_come_from_one_source` (cross-consistency) + `test_qa05_the_two_numbers_are_named_apart` | ✅ / ✅ / n-a / ✅ |
| QA-06 | BLOCKER | FIXED | C4 — مخزنان منفصلان (Document/Permit) والـOCR لا يكتب على أيٍّ منهما | (C4) | `test_qa06_document_expiry_syncs_the_permit` + `..._older_document_does_not_expire_a_valid_permit` + `..._manual_date_wins_over_ocr` + `..._backfill_script_is_dry_run_by_default` | ✅ / ✅ / n-a / ⏳ العدادات |
| QA-07 | مهم | NOT_STARTED | C8 | — | — | — |
| QA-08 | مهم | IN_PROGRESS | C9 — نوع REQSIG غير متاح للموظف | `7adca3a` | النوع أُنشئ؛ يلزم تحقق أن الموظف يراه في كتالوج التقديم | — |
| QA-09 | مهم | NOT_STARTED | C9 — أنواع مكررة | — | — | — |
| QA-10 | BLOCKER | VERIFIED | C6 — `_chain` تُعيد القالب كما هو بلا ترشيح بالحمولة | (C6) | `test_qa10_delegate_stage_only_with_travel` + `test_qa10_condition_forms_from_the_ui_are_handled` + `test_qa10_a_leave_without_travel_completes_without_delegate` | ✅ / ✅ / n-a / ✅ |
| QA-11 | مهم | NOT_STARTED | C7 | — | — | — |
| QA-12 | مهم | NOT_STARTED | C7 | — | — | — |
| QA-13 | مهم | NOT_STARTED | C8 | — | — | — |
| QA-14 | مهم | NOT_STARTED | C4 + C8 | — | — | — |
| QA-15 | مهم | NOT_STARTED | C9 | — | — | — |
| QA-16 | مهم | NOT_STARTED | C9 | — | — | — |
| QA-17 | بسيط | VERIFIED | المفتاح غير معرَّف و`t()` تُرجع اسمه فلا يعمل البديل بعد `||` | (QA-17/22/29) | `switch_company` أُضيف لـi18n | ✅ / ✅ / ✅ / n-a |
| QA-18 | مهم | NOT_STARTED | C9 — assignment غير مالي | — | — | — |
| QA-19 | مهم | NOT_STARTED | C4 + C5 | — | — | — |
| QA-20 | مهم | NOT_STARTED | C5 | — | — | — |
| QA-21 | مهم | NOT_STARTED | C9 | — | — | — |
| QA-22 | بسيط | FIXED | `attAr` يغطي حالات الحضور لا أنماطه، فكل نمط يرجع كوده | (QA-17/22/29) | `attModeAr` أُضيف واستُعمل؛ بقيت enums أخرى (prepared/digest) | ⏳ باقي الـenums |
| QA-23 | بسيط | NOT_STARTED | C9 | — | — | — |
| QA-24 | بسيط | NOT_STARTED | C2 | — | — | — |
| QA-25 | بسيط | NOT_STARTED | C8 | — | — | — |
| QA-26 | بسيط | NOT_STARTED | C7 | — | مُهّد له: توسيع `CRITICAL_FIELDS` في `21ffa9c` | — |
| QA-27 | بسيط | NOT_STARTED | C8 | — | — | — |
| QA-28 | مهم | NOT_STARTED | C4 | — | — | — |
| QA-29 | مهم | VERIFIED | C9 — سياسة الصفحة موزّعة على شروط مكتوبة عند كل شاشة | (QA-17/22/29) | القائمة وحارس المسار كلاهما `role === "delegate"` وحده | ✅ / ✅ / n-a / ✅ |
| QA-30 | مهم | VERIFIED | — | `cd408be` | `test_sec01_twofa_full_cycle_works` + `test_sec02` + `test_sec03` | ✅ / ✅ / n-a / ✅ |
| QA-31 | مهم | IN_PROGRESS | — | `cd408be` | الخمول في الواجهة فقط؛ **معيار القبول يشترط رفض الخادم للتوكن** | — |

## سجل الكنس (SKILL-9)

### C1 — QA-01 + QA-02
| السؤال | الإجابة |
|---|---|
| نوع طلب/دور آخر بنفس المشكلة؟ | لا — `can_decide` دالة واحدة محايدة للنوع، والكنس أثبت عدم وجود نسخة ثانية لمنطق «من يعتمد» |
| شركة أخرى (MUF)؟ | مغطّاة — الدالة تُرشّح بـ`req.company_id` بلا أي تفرّع خاص بشركة |
| لغة أخرى (EN)؟ | لا نص متأثر عدا رسالة 403 وهي في موضع واحد |
| مسار آخر (API/تصدير/طباعة)؟ | ثلاثة مستهلكين فقط: الصندوق (`requests.py:372`)، مسار القرار، وعلَم الواجهة (`:800`) — كلهم على القاعدة نفسها |

### C2 — QA-03 + QA-04
| السؤال | الإجابة |
|---|---|
| نوع/دور آخر بنفس المشكلة؟ | لا — حساب واحد في `compute_payroll`؛ الكنس أثبت عدم وجود حساب غياب ثانٍ |
| شركة أخرى (MUF)؟ | مغطّاة — الدالة تأخذ `company_id` بلا تفرّع خاص |
| لغة أخرى؟ | لا نص متأثر |
| مسار آخر (تقارير/تصدير)؟ | `reports.py:102` يستهلك ناتج `compute_payroll` نفسه فيرث الإصلاح |

### C3 — QA-05
| السؤال | الإجابة |
|---|---|
| نوع/دور آخر؟ | لا — الصيغة صارت في `leave_balance.py` وحده، وEOS يستدعيها |
| شركة أخرى؟ | مغطّاة — `annual_leave_days` يُقرأ من الشركة نفسها |
| لغة أخرى؟ | لا نص متأثر |
| مسار آخر؟ | الملف الشخصي وEOS يستدعيان نفس الدالة؛ سنوات الخدمة نفسها صارت من `eos.service_breakdown` |

### C6 — QA-10
| السؤال | الإجابة |
|---|---|
| نوع/دور آخر؟ | كُنست الأنواع الـ54: لا مرحلة أخرى مشروطة ضمًنا بلا شرط صريح |
| شركة أخرى؟ | مغطّاة — الترشيح بحمولة الطلب لا بالشركة |
| لغة أخرى؟ | لا نص متأثر |
| مسار آخر؟ | كل مستهلكي `_chain` (9 مواضع) صاروا يمرّرون الطلب |

## جولة ما بعد إعادة الاختبار الإنتاجي — 2026-08-14

| البند | الحالة | السبب الجذري | الدليل |
|---|---|---|---|
| QA-09 سفر خارج البلاد لا يُحفظ | مُصلَح `45189fc` | قاعدة `show` موثّقة ومستخدمة في REQLV بلا مُقيِّم في الخادم ولا الواجهة، فظهرت "الوجهة" دائًما فمُلئت بدل تأشير `travel_required` | اختباران: دلالة `show` في `conditional_requirements`، ووجودها في `evalConditionals` |
| QA-07 REQSIG غائب عن الموظف | مُصلَح `6739d9a` | وُرِث `visible_to_employee=False` الافتراضي المخصّص لإجراءات ADM* الداخلية | استدعاء `/requests/types?creatable_only` بحساب موظف |
| QA-08 أنواع مكرّرة | مُصلَح `6739d9a` | صفوف قديمة في القاعدة (التعريفات ٥٤ كوًدا فريًدا بلا أسماء مكرّرة) — أُلغي التكرار بالهوية في كتالوج الإنشاء وحده | اختبار يُدخل صًفا مكرًرا ويتحقق أن الكتالوج الكامل لا يُخفيه |
| QA-23 خروج تلقائي حقيقي | مُصلَح `8603b5d` | المهلة مؤقّت متصفح فقط، يتجاوزه استدعاء الـAPI مباشرة | اختبار يتجاوز الواجهة ويتحقق أن رمز التجديد الحقيقي يُرفض |

**الحالة:** 457/457 اختبار خلفي أخضر، `tsc` نظيف، ترحيلان جديدان (`y8r9s0t1u2v`, `z9s0t1u2v3w`) مُختبَران على قاعدة منفصلة.

**معلّق يحتاج بيانات الإنتاج:** رابط "الموظفون" عند المالك — `company_owner` يملك `view_employee` في
`ROLE_DEFAULT_PERMS`، والصلاحيات تُجمَع ولا تُطرَح، فلا سبب في الكود لاختفاء الرابط.
يلزم ناتج `/auth/me` لذلك الحساب (`role` و`permissions`) لتحديد السبب.
