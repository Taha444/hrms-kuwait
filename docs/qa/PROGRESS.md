# PROGRESS — الحالة الحية لملاحظات QA الـ31

الحالات: `NOT_STARTED` → `IN_PROGRESS` → `FIXED` → `VERIFIED` (أو `BLOCKED` بسبب).
**ممنوع** كتابة `VERIFIED` بعمود دليل فارغ.

| ID | الخطورة | الحالة | السبب الجذري | Commit | الدليل | Sweep (أنواع/شركات/لغات/مسارات) |
|----|---------|--------|--------------|--------|--------|----------------------------------|
| QA-01 | BLOCKER | VERIFIED | C1 — تجاوز ضمني في `can_decide` يعيد True لكل مدير/مالك في أي مرحلة | (هذا الـcommit) | `test_qa01_manager_cannot_approve_a_stage_that_is_not_his` + `test_qa01_no_implicit_override_for_any_role` + `test_qa01_no_sequential_approval_by_same_account` | ✅ / ✅ / n-a / ✅ |
| QA-02 | BLOCKER | VERIFIED | C1 — نفس الدالة: الصندوق مبني عليها | (هذا الـcommit) | `test_qa02_branch_supervisor_receives_the_request` — أُثبت فشله قبل الإصلاح (الطلب في صندوق المدير `{1,2}`) | ✅ / ✅ / n-a / ✅ |
| QA-03 | BLOCKER | NOT_STARTED | C2 — `payroll.py:48-67` بلا حالة `UNRECORDED` | — | — | — |
| QA-04 | BLOCKER | NOT_STARTED | C2 — بلا قصّ على `hire_date` | — | — | — |
| QA-05 | BLOCKER | NOT_STARTED | C3 — مصدران للرصيد | — | مُهّد له: `leave_ledger` في `0bc4736` | — |
| QA-06 | BLOCKER | NOT_STARTED | C4 — تاريخ الانتهاء لا يُخزَّن | — | — | — |
| QA-07 | مهم | NOT_STARTED | C8 | — | — | — |
| QA-08 | مهم | IN_PROGRESS | C9 — نوع REQSIG غير متاح للموظف | `7adca3a` | النوع أُنشئ؛ يلزم تحقق أن الموظف يراه في كتالوج التقديم | — |
| QA-09 | مهم | NOT_STARTED | C9 — أنواع مكررة | — | — | — |
| QA-10 | BLOCKER | NOT_STARTED | C6 — المسار قالب ثابت | — | — | — |
| QA-11 | مهم | NOT_STARTED | C7 | — | — | — |
| QA-12 | مهم | NOT_STARTED | C7 | — | — | — |
| QA-13 | مهم | NOT_STARTED | C8 | — | — | — |
| QA-14 | مهم | NOT_STARTED | C4 + C8 | — | — | — |
| QA-15 | مهم | NOT_STARTED | C9 | — | — | — |
| QA-16 | مهم | NOT_STARTED | C9 | — | — | — |
| QA-17 | بسيط | NOT_STARTED | C8 | — | — | — |
| QA-18 | مهم | NOT_STARTED | C9 — assignment غير مالي | — | — | — |
| QA-19 | مهم | NOT_STARTED | C4 + C5 | — | — | — |
| QA-20 | مهم | NOT_STARTED | C5 | — | — | — |
| QA-21 | مهم | NOT_STARTED | C9 | — | — | — |
| QA-22 | بسيط | NOT_STARTED | C8 | — | — | — |
| QA-23 | بسيط | NOT_STARTED | C9 | — | — | — |
| QA-24 | بسيط | NOT_STARTED | C2 | — | — | — |
| QA-25 | بسيط | NOT_STARTED | C8 | — | — | — |
| QA-26 | بسيط | NOT_STARTED | C7 | — | مُهّد له: توسيع `CRITICAL_FIELDS` في `21ffa9c` | — |
| QA-27 | بسيط | NOT_STARTED | C8 | — | — | — |
| QA-28 | مهم | NOT_STARTED | C4 | — | — | — |
| QA-29 | مهم | IN_PROGRESS | C9 | `09be6ed` | أُزيلت من HR والمدير؛ المطلوب المندوب **فقط** — المالك والمحاسب وadmin_employee ما زالوا يرونها | — |
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
