---
name: hrms-document-output
description: طبقة المخرجات الرسمية في Kuwait HRMS — فصل الطلب عن المستند، أنواع النتائج الخمسة، دورة حياة المستند المستقلة، كتالوج 9 Layouts و25 مستندا Canonical و6 تقارير وسجلين تقنيين، ونموذج بيانات document_artifact. استخدم هذا السكيل إلزاميا عند أي عمل على PDF، طباعة، شهادة، خطاب، قالب، template، تقرير، مخرَج طلب، أو أي كود يمس document_artifact / request_output / government_artifact. استخدمه أيضا لو طُلب منك "اطبع الطلب" أو "أضف زر تحميل" — لأن الطلب ليس هو المستند.
---

# HRMS Document Output Layer (V2.2 §19 → §24، §28، §29)

## التصحيح الجوهري: الطلب ليس هو المستند
أربعة كائنات **يُمنع دمجها** في شاشة أو PDF واحد:

| الكائن | الغرض | من يراه | يُطبع كمستند رسمي؟ |
|---|---|---|---|
| `INTERNAL REQUEST RECORD` | ما طلبه المستخدم، السبب، المرفقات، النقاش، مسار الحالة | مقدم الطلب والأطراف المخوّلة | **لا** — طباعة داخلية بعلامة مائية فقط |
| `Workflow Evidence` | المهام والقرارات والتحقق والتنفيذ والـ SLA | التدقيق والأطراف حسب الصلاحية | **لا** — لا يظهر في خطاب خارجي |
| `Business Outcome` | الأثر الحقيقي: رصيد إجازة، قسط، دفع، IBAN، تجديد وثيقة | صاحب العلاقة والمنفذون | قد لا يحتاج PDF؛ **يجب تسجيله وربطه بالطلب** |
| `Official Artifact` | الخطاب أو القرار أو الإقرار أو المستند الحكومي النهائي | المستفيد والجهة المخوّلة | **نعم** — وهو زر التنزيل الافتراضي بعد الاكتمال |

**قاعدة واجهة ملزمة:** بعد الاكتمال يظهر زر أساسي «تنزيل المستند الرسمي» أو «عرض نتيجة التنفيذ»، ويبقى «طباعة سجل الطلب» **ثانويا ومقصورا على Audit/HR** بعلامة مائية داخلية. **لا يجوز أن يحمل الزران الملف نفسه.**

القالب يأخذ **فقط** الحقول الضرورية لغرضه، من **Snapshot ثابت وقت الإصدار**. السبب التفصيلي والملاحظات الداخلية وأسماء من مرّ عليهم الطلب **لا تُطبع افتراضيا**.

## 1. أنواع النتائج الخمسة (§20)
| Outcome Type | الوصف | الملف النهائي |
|---|---|---|
| `EXTERNAL_COMPANY_DOCUMENT` | صادر من الشركة لجهة أخرى | PDF رسمي على ورق الشركة وموقّع من المخوّل |
| `INTERNAL_OFFICIAL_DECISION` | قرار أو إقرار رسمي داخل علاقة العمل | PDF رسمي داخلي، قد تُسلَّم نسخة للموظف |
| `GOVERNMENT_ARTIFACT` | مستند تصدره جهة حكومية | **الملف الحكومي الأصلي المرفوع** + غلاف متابعة داخلي منفصل |
| `TRANSACTION_RECEIPT` | إثبات تنفيذ خدمة أو حركة | إيصال أو شاشة نتيجة قابلة للتنزيل — بلا خطاب خارجي |
| `NO_DOCUMENT` | حالة أو توجيه فقط | إشعار مسجّل، بلا PDF رسمي |

**الرفض لا ينتج المستند المطلوب.** قد ينتج إشعار قرار داخلي إذا تطلبت السياسة تسبيبا، لكن **بلا شعار أو عنوان يوهم الجهة الخارجية بأن الخدمة تمت**.

## 2. دورة حياة المستند المستقلة (§21)
```
NOT_REQUIRED → DRAFT_PREVIEW → READY_FOR_SIGNATURE → SIGNED → ISSUED → DELIVERED → FILED
استثنائية: GENERATION_FAILED, SIGNATURE_FAILED, REVOKED, SUPERSEDED, EXPIRED
```
- `DRAFT_PREVIEW` يحمل علامة DRAFT، **بلا رقم إصدار نهائي وبلا QR صالح**.
- `SIGNED` يعني أن بصمة الملف الموقّع = بصمة الملف المحفوظ. **لا يُعاد التوليد بعد التوقيع.**
- `ISSUED` يثبّت رقم المستند وتاريخ الإصدار ونسخة القالب والصياغة وبيانات الموقّع.
- `DELIVERED` يسجل القناة والمستلم والوقت — **ولا يساوي PRINTED**.
- `FILED` = ربط النسخة النهائية بملف الموظف وسياسة الاحتفاظ.
- `REVOKED` يحتاج سببا ومصدر قرار **ولا يحذف النسخة القديمة**.
- **ممنوع استبدال ملف سبق إصداره داخل نفس السجل.** التصحيح ينشئ إصدارا جديدا ويربطه بـ `supersedes_document_id`، ويحوّل صفحة تحقق القديم إلى `SUPERSEDED`.

## 3. الكتالوج الموحّد: 9 + 25 + 6 + 2 (§24)
**الرقم 54 القديم كان عدد أكواد تاريخية، لا عدد تصميمات تُبنى يدويا.**
الصواب: فصل **التصميم البصري** عن **تعريف المستند** عن **Profile الاستخدام**.

### 9 عائلات تصميم (LAY-01 → LAY-09)
| الكود | العائلة | الاستخدام |
|---|---|---|
| LAY-01 | Letter / Certificate | خطابات وشهادات خارجية |
| LAY-02 | Employment Decision / Notice | قرارات وإشعارات وظيفية |
| LAY-03 | Agreement / Acknowledgement | اتفاقات وإقرارات |
| LAY-04 | Investigation / Minutes | تحقيق ومحاضر |
| LAY-05 | Calculation / Settlement | حسابات وتسويات |
| LAY-06 | Clearance / Checklist | إخلاء وفحص |
| LAY-07 | Government Transaction Cover | أغلفة متابعة حكومية |
| LAY-08 | Transaction Receipt / Change Confirmation | إيصالات تحديث |
| LAY-09 | Report / Statement | تقارير وكشوف |

### 25 مستندا Canonical + 6 تقارير + سجلان
**اقرأ `references/document-catalog.md`** — فيه `OD-001 → OD-025` و `RPT-001 → RPT-006` و `SYS-001/002` مع الـ Layout والـ Profiles والأكواد التاريخية.

**معيار القبول:** أثبت أن النظام يحوي **9 ملفات Layout فقط**، وأن كل كود `PRN` تاريخي يُحل إلى `OD` أو `RPT` أو `SYS` معروف بلا 404 وبلا اختلاف غير مقصود.

## 4. نموذج البيانات (§28)
```
document_artifact
  id, company_id, employee_id, request_id
  template_code, template_version, legal_copy_version
  document_number, language, profile, classification, audience, status
  snapshot_json, generated_at, issued_at, delivered_at, filed_at
  storage_key, mime_type, byte_size, sha256, page_count
  signatory_authority_id, signature_method, signed_at, signature_validation_status
  qr_token_hash, supersedes_document_id, revoked_at, revocation_reason

request_output
  request_id, outcome_type, outcome_record_type, outcome_record_id
  primary_artifact_id, government_artifact_id, completed_at
  → قيد فريد يمنع أكثر من Primary output نشط للطلب والإصدار نفسه

government_artifact
  source_authority, document_type, source_reference, issued_at, expiry_date
  storage_key, sha256, uploaded_by, verified_by, verified_at, cover_sheet_artifact_id
  → الملف الحكومي لا يمر على محرر قوالب الشركة
```

## 5. قواعد هندسية إلزامية (§28.4)
- التوليد **Server-side فقط** من `placeholders` ضمن Allowlist. **يُمنع HTML/JavaScript الحر.**
- `Snapshot` يُنشأ وقت `READY_FOR_SIGNATURE`؛ تغيّر بيانات الموظف لاحقا **لا يغيّر الملف القديم**.
- endpoint التوليد **Idempotent** بمفتاح: `request_id + template_version + snapshot_hash`.
- الملف: `Content-Type: application/pdf`، يبدأ بـ `%PDF`، **الخطوط العربية مضمّنة**، بلا JavaScript وبلا روابط جلسة حساسة.
- يُفضَّل `PDF/A-2b` للأرشفة بعد نجاح التحقق الآلي — **ولا تُدّعى المطابقة بلا Validator**.
- اسم الملف: `{document_number}_{employee_no}_{document_type}_{issue_date}.pdf` — **لا الاسم وحده ولا request payload**.

## 6. منع انتحال المستند الحكومي (§23)
النظام **لا يولّد** إقامة ولا بطاقة مدنية ولا إذن عمل بشعار حكومي. يولّد **غلاف متابعة شركة فقط**، ثم يحفظ المستند الحقيقي الصادر من PAM/MOI/PACI مع:
`source_authority, source_reference, issued_at, expiry_date, file_hash, verified_by`.

## 7. فصل أزرار الواجهة (§29)
| السياق | الزر الأساسي | الزر الثانوي | الصلاحية |
|---|---|---|---|
| طلب تحت المراجعة | عرض الحالة / استكمال معلومات | طباعة سجل داخلي | مقدم الطلب؛ الطباعة Audit/HR فقط |
| طلب مكتمل بوثيقة شركة | تنزيل المستند الرسمي | عرض سجل الطلب | صاحب العلاقة والمخوّل |
| طلب مكتمل بتحديث | عرض نتيجة التنفيذ | تنزيل إيصال إن وجد | صاحب العلاقة والمخوّل |
| معاملة حكومية مكتملة | تنزيل المستند الحكومي | تنزيل غلاف المتابعة | PRO/HR والموظف حسب السياسة |
| مستند موقّع | تنزيل النسخة الموقّعة | التحقق من الأصالة | حسب التصنيف |

المعاينة تحمل Watermark **ولا تتيح Copy HTML نشط**.

## التحقق
`/hrms-verify-documents` — يفحص `AC-11, AC-12` وكل اختبارات `DOC-01 → DOC-20`.
للصياغات والتوقيع والـ QR: انتقل إلى سكيل `hrms-document-templates`.
