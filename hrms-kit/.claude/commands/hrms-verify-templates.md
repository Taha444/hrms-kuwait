---
description: تحقق من صياغة القوالب والتوقيع والـ QR
---

اقرأ سكيل `hrms-document-templates`، ثم **ولّد عينة PDF فعلية** لكل من: OD-001/STANDARD، OD-001/PAM_SUPPORT، OD-001/NO_SALARY، OD-006، OD-017/PRELIMINARY، OD-023، واستخرج نصها وافحص:

- `DOC-02` — لا يظهر: «طلب شهادة راتب»، payload keys، role codes، Timeline، أسماء الموافقين، IP، SLA، request_id.
- `DOC-03` — PAM_SUPPORT يعرض موقع العمل والساعات والهواتف والبنك، ولا شيء زائد.
- `NO_SALARY` — جدول الراتب محذوف بالكامل **بلا صفوف فارغة**.
- `DOC-13` — EOS المبدئي يحمل `PRELIMINARY - NOT FOR PAYMENT` وبلا payment reference.
- `DOC-14` — المصروف المعتمد لا يحمل كلمة «مدفوع» قبل وجود `payment_reference`.
- `DOC-17` — RTL/LTR صحيحان، الأرقام والعملات لا تنعكس، لا قص ولا overflow، الخطوط العربية **مضمّنة في الملف**.
- `DOC-07` — عبارة Protected Electronic Signature غير موجودة إلا مع `CRYPTOGRAPHIC_E_SIGNATURE`.
- `DOC-08` — signed hash يطابق الملف و validation status = VALID.
- `DOC-09` / `DOC-10` — افتح صفحة QR: هل تعرض فقط الحقول المسموحة؟ هل الراتب و IBAN محجوبان؟ هل REVOKED يظهر بسبب عام بلا حذف الملف؟

ثم تحقق من مصادر الحقول في جدول §25.1: هل الراتب يأتي من Approved payroll لا من payload؟ (`AP-08`) هل اسم الشركة من Company master لا من نص حر؟ هل `document_number` مستقل عن `request_id`؟

راجع أخيرا: أي صياغة قانونية مفعّلة بلا `legal_copy_version` معتمد = **blocked** لا pass.

حدّث `status.json`.
