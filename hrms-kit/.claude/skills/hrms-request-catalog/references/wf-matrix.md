# مصفوفة المسارات WF-001 → WF-029 (V2.2 §6 + §23)

الأعمدة: الكود | النوع | المسار الواقعي | الشروط والاستثناءات | المخرَج النهائي + نوع النتيجة

## أ. الوقت والخطابات والبيانات (WF-001 → WF-008)

**WF-001 إجازة عادية**
مسار: `Employee → System balance check → Direct Manager DECISION → Auto-post attendance → Notify HR/Employee`
شروط: HR يدخل فقط عند رصيد سالب، أو مدة/نوع استثنائي، أو تعارض سياسة/Blackout. لا Company Manager افتراضيا.
مخرَج: `OD-011` اعتماد إجازة — `INTERNAL_OFFICIAL_DECISION`. الأثر: خصم/حجز الرصيد وتحديث الحضور.

**WF-002 إجازة سفر**
مسار: مسار الإجازة العادي أولا؛ بعد اعتماده تُنشأ Case مستقلة لـ PRO/Travel Docs عند الحاجة.
شروط: Finance فقط إذا وُجدت تذكرة/سلفة على الشركة. PRO ينفّذ ولا يعتمد الإجازة.
مخرَج: `OD-011` + `OD-012` حزم TRAVEL_MEMO/FINANCE/DOCUMENTS — `INTERNAL_OFFICIAL_DECISION`.

**WF-003 استئذان**
مسار: `Employee → Direct Manager DECISION → Auto-update attendance → Completed`
شروط: HR مراجعة استثناء فقط. لا PRO ولا Finance.
مخرَج: `OD-018/PERMISSION` — `TRANSACTION_RECEIPT`.

**WF-004 تصحيح حضور**
مسار: `Employee/Manager → Manager confirmation → HR Attendance VALIDATION → Update attendance`
شروط: يمكن الإكمال الآلي عند وجود دليل جهاز موثوق وحدود سياسة واضحة.
مخرَج: `OD-018/ATTENDANCE_CORRECTION` مع سجل before/after — `TRANSACTION_RECEIPT`.

**WF-005 شهادة راتب**
مسار: `Employee → System eligibility/data check → Auto-generate → HR digital seal if policy → Deliver`
شروط: لا Manager. Finance فقط إذا وُجدت تفاصيل غير معتمدة أو كشف حساس خارج السياسة.
مخرَج: `OD-001` حسب Profile — `EXTERNAL_COMPANY_DOCUMENT`.

**WF-006 لمن يهمه الأمر / NOC**
مسار: `Employee → System rule → Auto-generate` أو `HR validation → Deliver`
شروط: لجهة/غرض محدد كاستثناء معلن، لا خطوة ثابتة.
مخرَج: `OD-002` بأحد Profiles: TWIMC / BANK / EXPERIENCE / NOC — `EXTERNAL_COMPANY_DOCUMENT`.

**WF-007 تعديل بيانات شخصية**
مسار: `Employee → Field-based validation → HR validates identity fields → Apply → Notify`
شروط: الهاتف/العنوان قد يكونان آليين. الجواز/المدني/البنك تتحول لمسار متخصص.
مخرَج: `OD-021/PERSONAL_DATA` — `TRANSACTION_RECEIPT`.

**WF-008 تحديث حساب بنكي**
مسار: `Employee → HR identity check → Finance/Payroll IBAN validation → Dual-control activation → Notify`
شروط: **لا يفعّل الحساب نفس الشخص الذي أدخله.** يُسجّل old/new و effective month.
مخرَج: `OD-021/BANK_ACCOUNT` مع IBAN مقنّع — `TRANSACTION_RECEIPT`.

## ب. المالية والانضباط والتغييرات (WF-009 → WF-018)

**WF-009 سلفة/قرض**
مسار: `Employee → Policy eligibility → Manager recommendation → Finance DECISION → Employee accepts terms → Payroll schedules`
شروط: المبالغ فوق حد السياسة تنتقل إلى Authorized Signatory. **الإقرار ليس اعتمادا.**
مخرَج: `OD-022` اتفاق وجدول سداد موقّع — `INTERNAL_OFFICIAL_DECISION`.

**WF-010 مصروفات**
مسار: `Employee → Cost-center Manager DECISION → Finance document/tax validation → Payment execution → Notify`
شروط: اعتماد إضافي فقط فوق حد القيمة أو خارج الميزانية. لا HR.
مخرَج: `OD-023` تسوية مصروف وإشعار دفع — `TRANSACTION_RECEIPT`.

**WF-011 اعتراض راتب**
مسار: `Employee → Payroll specialist investigation → Correct automatically` أو `Finance/HR manager DECISION عند النزاع → Notify`
شروط: SLA قصير، لا يبقى Pending. يُحفظ before/after calculation.
مخرَج: `OD-024/PAYROLL` — `INTERNAL_OFFICIAL_DECISION`.

**WF-012 اعتراض خصم**
مسار: `Employee → Independent HR case owner → Finance evidence → HR authorized decision/committee → Notify`
شروط: **لا يقرر الشخص الذي أصدر الخصم في الاعتراض.** يمكن تصعيد قانوني وفق السياسة.
مخرَج: `OD-024/DEDUCTION` — `INTERNAL_OFFICIAL_DECISION`.

**WF-013 إصدار خصم**
مسار: `Manager/HR incident → HR policy/legal validation → Authorized HR decision → Finance/Payroll execution → Employee acknowledgement`
شروط: Finance ينفّذ الأثر ولا يقرر المخالفة. **لا يظهر في Self-Service.**
مخرَج: `OD-008` قرار خصم؛ `RPT-005` عند طلب كشف تجميعي — `INTERNAL_OFFICIAL_DECISION`.

**WF-014 إصدار إنذار**
مسار: `Manager incident report → HR validation → Authorized issuer decision → Document → Employee acknowledgement`
شروط: الموظف يُقر بالاستلام أو يُسجَّل رفض التوقيع. اعتراضه مسار منفصل.
مخرَج: `OD-006` + `OD-009/ACKNOWLEDGEMENT` — `INTERNAL_OFFICIAL_DECISION`.

**WF-015 رد على إنذار**
مسار: `داخل warning case → Employee response → Independent HR review → Attach outcome → Filed`
شروط: **لا يظهر كطلب عام**، ولا يطبع حقولا مالية أو سفر.
مخرَج: `OD-009/RESPONSE` — حفظ رد الموظف دون تعديل أصله.

**WF-016 تظلم**
مسار: `Employee confidential case → Conflict check → Independent HR/Ethics owner → Contributor/legal if needed → Decision → Notify`
شروط: **يُستبعد المشكو في حقه وسلسلته المتعارضة.** وصول مقيّد جدا.
مخرَج: `OD-010` قرار تظلم مقيّد الاطلاع — `INTERNAL_OFFICIAL_DECISION`.

**WF-017 عمل إضافي**
مسار: `Manager pre-authorization → Employee logs hours → Manager confirms actual → Payroll validates rate → Payroll execution`
شروط: **لا يُدفع بلا تكليف مسبق** إلا باستثناء موثق. Finance لا يعيد قرار التشغيل.
مخرَج: `OD-018/OVERTIME` + أثر Payroll — `INTERNAL_OFFICIAL_DECISION`.

**WF-018 تغيير راتب / مكان عمل** — **يُقسم إلى مسارين**
- Salary: `Manager proposal → HR Comp → Finance budget → Signatory → HR apply`
- Transfer: `Manager/HR → Receiving Manager → HR apply`؛ Finance فقط لأثر مالي.
مخرَج: `OD-005/SALARY` أو `OD-005/TRANSFER` — `INTERNAL_OFFICIAL_DECISION`.

## ج. الإقامة والخروج والتطوير (WF-019 → WF-029)

**WF-019 تجديد إقامة عادي**
مسار: `System/HR creates case by expiry → HR document check → PRO execution stages → Upload evidence → Complete → Notify`
شروط: لا Manager افتراضيا. تُدار كمراحل Case لا كموافقات متكررة.
مخرَج: `OD-013/RESIDENCY` + Government Artifact — `GOVERNMENT_ARTIFACT`.

**WF-020 تجديد إقامة مبكر**
مسار: `Employee/HR request → HR validates exception → PRO executes → Notify`
شروط: Manager فقط لتأثير سفر/تشغيل. Finance فقط لرسوم خارج السياسة.
مخرَج: `OD-013/EARLY_RESIDENCY` + Government Artifact — `GOVERNMENT_ARTIFACT`.

**WF-021 تجديد إذن عمل**
مسار: `PRO internal case → HR employment validation → PRO government execution → Upload permit → Complete`
شروط: HR قراءة/تحقق، **لا زر موافقة عام**. رسوم استثنائية → Finance.
مخرَج: `OD-013/WORK_PERMIT` + ملف PAM الحقيقي — `GOVERNMENT_ARTIFACT`.

**WF-022 تحديث جواز**
مسار: `Employee → HR identity validation → Apply → Conditional PRO task if residency affected → Notify`
شروط: لا Manager. يُمنع التكرار ويُحتفظ بالمرفق والرقم القديم/الجديد.
مخرَج: `OD-013/PASSPORT` + صورة الجواز المصرح بها — `TRANSACTION_RECEIPT`.

**WF-023 تحديث مدني**
مسار: `Employee/PRO → HR validation → Apply → Link renewal case → Notify`
شروط: لا Manager ولا Finance ما لم توجد تبعية موثقة.
مخرَج: `OD-013/CIVIL_ID` + ملف PACI — `GOVERNMENT_ARTIFACT`.

**WF-024 استقالة**
مسار: `Employee submits notice → Manager acknowledges/hand-over plan → HR validates dates/notice → Parallel clearance → EOS → Close`
شروط: **ليست "طلب إذن بالاستقالة"** — المدير لا يرفض الإشعار. النص والسياسة تحت المراجعة القانونية الكويتية.
مخرَج: `OD-015` تسجيل/قبول استقالة — `INTERNAL_OFFICIAL_DECISION`.

**WF-025 تسوية نهاية خدمة**
مسار: `HR validates service data → Payroll calculates → Independent Finance reviewer → Authorized signatory → Employee acknowledgement/dispute → Print/File`
شروط: **Manager ليس خطوة ثابتة.** الحساب والقرار والتوقيع أدوار منفصلة.
مخرَج: `OD-017/PRELIMINARY` ثم `OD-017/FINAL` — `INTERNAL_OFFICIAL_DECISION`.

**WF-026 إخلاء طرف**
مسار: `HR starts → Parallel department signoffs/asset tasks → Finance clearance → HR completeness check → Employee acknowledgement → Filed`
شروط: كل إدارة ترى مهمتها فقط؛ `ALL_OF` للجهات المطلوبة مع **تخطي الجهات غير المنطبقة**.
مخرَج: `OD-016` إخلاء طرف نهائي موقّع — `INTERNAL_OFFICIAL_DECISION`.

**WF-027 تدريب**
مسار: `Employee/Manager → Manager DECISION → HR L&D validation → Budget approval only above cost threshold → Execution`
شروط: التدريب الداخلي/المجاني قد يُعتمد آليا بعد المدير. لا Finance بلا تكلفة.
مخرَج: `OD-020/TRAINING` — `INTERNAL_OFFICIAL_DECISION`.

**WF-028 مراجعة ترقية/راتب**
مسار: `Manager nomination` أو `Employee request → triage → HR eligibility/calibration → Finance for salary impact → Committee/Signatory decision → Notify`
شروط: **الطلب لا يساوي حقا في الترقية.** تُفصل الترقية عن تعديل الراتب في البيانات والقرار.
مخرَج: `OD-005/REVIEW_OUTCOME`؛ وعند القبول `OD-005/PROMOTION` أو `/SALARY` أو `/TRANSFER` — `INTERNAL_OFFICIAL_DECISION`.

**WF-029 طلب عام**
مسار: `Employee → HR/Service Desk triage → Convert to canonical type` أو `answer/close`
شروط: **لا Approve/Reject ولا PDF رسمي قبل التحويل.** يُقاس بزمن الفرز.
مخرَج: إشعار تحويل/إغلاق فقط — `NO_DOCUMENT`.
