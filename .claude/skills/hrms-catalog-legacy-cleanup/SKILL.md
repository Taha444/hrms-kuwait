---
name: hrms-catalog-legacy-cleanup
description: تنظيف كتالوج الطلبات في Kuwait HRMS — إزالة الأنواع المكررة والقديمة من شاشة إنشاء الطلب، منع internal_action من الظهور كطلبات، إلغاء مسار REQSIG الموازي، وتنظيف التسميات القديمة. استخدم هذا السكيل عند أي عمل على كتالوج الطلبات أو أنواع الطلبات أو شاشة تقديم طلب.
---

# Package 3 — كتالوج الطلبات والتنظيف

## P3-13 — أنواع مكررة (P0/P1)

### الدليل
الموظف يرى **27 نوع طلب**، فيهم تكرارات مؤكدة:
```
WF-005:  REQCERTSAL  +  salary_certificate     ← الاتنين "طلب شهادة راتب"، بـapproval chains مختلفة
WF-009:  REQADV  +  advance  +  loan
WF-003:  REQEXIT  +  REQPER  +  exit_permission
```

**التكرار في شهادة الراتب أخطرها**: نفس الخدمة بمسارَي اعتماد مختلفين. الموظف يختار عشوائيا فيمر بمسار مختلف عن زميله — وهذا يخلق تفاوتا في المعاملة لا مجرد إزعاج في الواجهة.

### المطلوب
```
Employee-facing creation catalog  →  Canonical Request Types فقط
Legacy aliases                    →  backend compatibility للسجلات القديمة فقط
الاختلافات داخل نفس الـworkflow    →  subtype / conditional fields
```
> **ليست duplicate request cards.**

### التنفيذ
1. لكل مجموعة مكررة: حدد الـ canonical وأي approval chain هي المعتمدة — **قرار عمل، اسأل عنه**
2. الباقي يصبح alias: يقبل السجلات القديمة، ولا يظهر في الإنشاء
3. الاختلاف الحقيقي (سلفة مقابل قرض · إذن مقابل خروج مبكر) يصبح `subtype` داخل نوع واحد
4. أعد العد: الموظف يجب أن يرى العدد المعتمد، لا 27

**لا تحذف الـ aliases** — السجلات التاريخية تحتاجها.

## P3-14 — internal_action ليست طلبات
الـ registry يعرّف `ADMEMP · ADMTASK · ADMMISS · ADMLIC · ADMSIGN` كـ `internal_action`، ومع ذلك بعضها يُرجع في request catalog.

**كل Action يبدأ من مكانه الطبيعي:**
```
ADMEMP   → Onboarding
ADMTASK  → Task System
ADMMISS  → Notification / Document Missing flow
ADMLIC   → Archive / Company Document Renewal
ADMSIGN  → Signature / approval flow
```
> **لا يوجد Request موازٍ لنفس العملية.**

الفحص: هل الـ endpoint الذي يغذّي الكتالوج يحترم `internal_action` أصلا؟ الأرجح أنه يتجاهل التصنيف.

## P3-15 — REQSIG ليس مسارا موازيا
دورة التوقيع الإلكتروني **موجودة وكاملة**:
```
First upload → Active · Replacement → Reason → Pending
HR Approve/Reject · القديم يظل Active حتى الموافقة · Version History/Audit
```
لكن `REQSIG` schema ما زالت تطلب `attachments.required=["signature"]`.

**المطلوب:** تغيير التوقيع من Signature module **فقط**. أي مسار REQSIG ظاهر للمستخدم:
- يُشال من كتالوج الإنشاء، **أو**
- يوجّه للـ Signature workflow الصحيح

> **لا يبقى مساران مستقلان لتغيير نفس التوقيع.**

**قاعدة حماية 18:** القديم يظل Active حتى الموافقة — لا تكسرها أثناء التنظيف.

## P3-16 — التسميات القديمة
```
(V1.3) في الـlabel        →  تُزال
"طلب طلب إجازة"           →  البادئة مكررة في القالب والقيمة — أزل إحداهما
indefinite خام في العربي   →  ترجمة في الواجهة والتقارير
```
ليست blockers وحدها، لكنها تُغلق مع نفس الجولة.

**ملاحظة على `(V1.3)`:** لو ظهرت لتمييز نوعين بنفس الاسم، فالمشكلة الحقيقية هي `P3-13` — نوعان نشطان لنفس الخدمة. وحّدهما بدل تمييزهما بلاصقة.

## القبول
`DOD-01` `DOD-03` `DOD-04`
