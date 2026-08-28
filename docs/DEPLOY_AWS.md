# النشر على AWS — دليل تفصيلي

النظام اليوم على Railway: صورة Docker واحدة تقدّم الواجهة والـAPI معًا،
وقاعدة Postgres، والمرفقات على قرص الحاوية. هذا الدليل ينقله إلى AWS
بقاعدة بياناته وملفاته.

---

## 1. المكوّنات ولماذا كلٌّ منها

| المكوّن | الخدمة | لماذا |
|---|---|---|
| الصورة | **ECR** | مستودع صور خاص؛ ECS يسحب منه |
| التشغيل | **ECS Fargate** | حاوية بلا خادم تُدار. الصورة جاهزة، ولا نظام تشغيل تُرقّعه |
| المدخل | **ALB** | TLS، وفحص صحّة، ونطاق ثابت |
| القاعدة | **RDS PostgreSQL** | نسخ احتياطي واسترجاع زمني ودعم بلا إدارتك لها |
| المرفقات | **S3** | قرص الحاوية مؤقّت — انظر §7 |
| الأسرار | **Secrets Manager** | لا مفاتيح في تعريف المهمة |
| السجلّات | **CloudWatch Logs** | مخرجات uvicorn |
| النطاق | **Route 53 + ACM** | شهادة مجّانية تتجدّد تلقائًيا |

**المنطقة:** `me-central-1` (الإمارات) أو `me-south-1` (البحرين) — كلتاهما
قريبة من الكويت. اخترْ واحدة **وضع كل شيء فيها**: القاعدة والدلو والصورة.
الخلط بين منطقتين يضيف زمًنا وكلفة نقل بلا فائدة.

---

## 2. قاعدة البيانات — RDS

### الإنشاء

- المحرّك: PostgreSQL 16
- الفئة: `db.t4g.micro` للبداية (تكفي 15 موظًفا وعشرات المعاملات)
- التخزين: 20 GB مع **التوسّع التلقائي مفعًّلا**
- **Multi-AZ**: للتسليم النهائي نعم؛ للتجريب لا (يضاعف الكلفة)
- **الوصول العام: لا.** القاعدة داخل VPC خاص، تصلها الحاوية وحدها
- النسخ الاحتياطي: 7 أيام على الأقل
- التشفير عند التخزين: مفعَّل

### مجموعات الأمان

قاعدتان لا واحدة:

- `sg-hrms-app` — تقبل 80/443 من ALB
- `sg-hrms-db` — تقبل **5432 من `sg-hrms-app` وحدها**، لا من نطاق عناوين

الربط بمجموعة الأمان لا بالعنوان: عنوان الحاوية يتغيّر مع كل نشرة.

### النقل من Railway

من جهازك، ورابط Railway الخارجي:

```bash
pg_dump --no-owner --no-acl --format=custom \
  "postgresql://…railway…" -f hrms.dump
```

ثم إلى RDS — **من داخل الشبكة** (نسخة EC2 مؤقّتة أو نفق SSH؛ القاعدة
ليست عامّة):

```bash
pg_restore --no-owner --no-acl --clean --if-exists \
  -d "postgresql://hrms:PASS@…rds.amazonaws.com:5432/hrms" hrms.dump
```

**تحقّق قبل أن تكمل:**

```sql
SELECT version_num FROM alembic_version;
SELECT count(*) FROM employees;
SELECT count(*) FROM requests;
```

رقم الترحيل يجب أن يطابق ما على Railway (`y4q5r6s7t8u` وقت كتابة هذا).
اختلافه يعني نسخة ناقصة — أعد النقل ولا تُقلع فوقها.

---

## 3. المرفقات — S3

```bash
aws s3api create-bucket --bucket hrms-kuwait-docs \
  --region me-central-1 \
  --create-bucket-configuration LocationConstraint=me-central-1

aws s3api put-public-access-block --bucket hrms-kuwait-docs \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

aws s3api put-bucket-versioning --bucket hrms-kuwait-docs \
  --versioning-configuration Status=Enabled
```

**الحجب العام إلزامي**: الدلو يحمل جوازات وبطاقات مدنية وعقوًدا. والنظام
يقدّم الملفات عبر الخادم بعد فحص الصلاحية، فلا يحتاج الدلو أن يكون عامًّا
أصًلا.

**التأصيل مفعَّل** عمًدا: نسخة موقّعة تُستبدل بالخطأ تُسترجع.

### نقل الملفات القائمة

الأداة موجودة في المستودع:

```bash
python -m app.migrate_storage --check      # ماذا يوجد وأين
python -m app.migrate_storage --normalize  # توحيد المسارات
python -m app.migrate_storage --upload     # الرفع إلى الدلو
python -m app.migrate_storage --verify     # التحقّق ملًفا ملًفا
```

**لا تضبط `STORAGE_BACKEND=s3` قبل نجاح `--verify`.** الضبط المبكر يجعل
الخادم يبحث في الدلو عن ملفات لم تُرفع بعد، فتظهر المستندات القديمة
مفقودة وهي سليمة على القرص.

---

## 4. الأسرار — Secrets Manager

```bash
aws secretsmanager create-secret --name hrms/prod \
  --secret-string '{
    "SECRET_KEY":"…64 حرًفا عشوائًيا…",
    "DATABASE_URL":"postgresql+psycopg2://hrms:PASS@…:5432/hrms",
    "TWILIO_AUTH_TOKEN":""
  }'
```

`SECRET_KEY` يوقّع رموز الدخول: من يعرفه يصنع رمز إدارة عليا. وّلده
عشوائًيا ولا تنسخه من مثال:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

**تغييره يُخرج كل المستخدمين** — وهذا مقصود عند أي اشتباه في تسرّب.

في تعريف المهمة تُربط هذه بـ`secrets` لا `environment`، فلا تظهر قيمتها
في وصف المهمة ولا في سجلّ من يقرأه.

---

## 5. الصلاحيات — دوران لا واحد

**`hrmsExecutionRole`** (لسحب الصورة وقراءة الأسرار عند الإقلاع):
`AmazonECSTaskExecutionRolePolicy` + إذن `secretsmanager:GetSecretValue`
على السرّ وحده.

**`hrmsTaskRole`** (للتطبيق نفسه): الوصول إلى الدلو **وحده**:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject",
               "s3:HeadObject", "s3:ListBucket"],
    "Resource": ["arn:aws:s3:::hrms-kuwait-docs",
                 "arn:aws:s3:::hrms-kuwait-docs/*"]
  }]
}
```

`boto3` يقرأ هذا الدور تلقائًيا. **لا تضع `AWS_ACCESS_KEY_ID` في متغيّرات
البيئة**: المفتاح المكتوب يُنسخ مع كل تعريف مهمة ولا تنتهي صلاحيته، والدور
يتبدّل من تلقائه كل ساعات.

---

## 6. الصورة والتشغيل

### الرفع إلى ECR

```bash
aws ecr create-repository --repository-name hrms-kuwait

aws ecr get-login-password --region me-central-1 \
  | docker login --username AWS --password-stdin \
    <ACCOUNT>.dkr.ecr.me-central-1.amazonaws.com

docker build -t hrms-kuwait .
docker tag hrms-kuwait:latest \
  <ACCOUNT>.dkr.ecr.me-central-1.amazonaws.com/hrms-kuwait:latest
docker push <ACCOUNT>.dkr.ecr.me-central-1.amazonaws.com/hrms-kuwait:latest
```

`Dockerfile` **في الجذر** هو صورة الإنتاج. الذي في `backend/` لـ
docker-compose المحلي وحده — وقد كلّفنا الخلط بينهما نشرة كاملة.

### حجم المهمة

**1 vCPU / 2 GB** — لا أقلّ. LibreOffice يفتح عملية كاملة عند تحويل العقد
إلى PDF، و1 GB تجعله يُقتل في منتصف التحويل فتفشل توليدة كل عقد بلا سبب
ظاهر في السجلّ.

والصورة كبيرة (LibreOffice + Tesseract)، فأول سحب بطيء. هذا طبيعي.

### متغيّرات البيئة

```
DATABASE_URL          ← من السرّ
SECRET_KEY            ← من السرّ
STORAGE_BACKEND=s3
S3_BUCKET=hrms-kuwait-docs
S3_REGION=me-central-1
UPLOAD_DIR=/tmp/uploads
CORS_ORIGINS=https://hrms.example.com
SCHEDULER_ENABLED=true
PORT=8000
```

### ALB وفحص الصحّة

- المسار: **`/api/health`** — لا `/api/health/deep`
- الفترة: 30 ثانية، المهلة: 5

الفحص العميق يفحص القاعدة والتخزين ويمسح الخطوط؛ استدعاؤه كل نصف دقيقة
يحمّل النظام بلا فائدة. اتركه لك تستدعيه يدوًيا.

---

## 7. خمسة مزالق حقيقية

### قرص الحاوية مؤقّت

كل نشرة تبدأ بقرص نظيف. بقاء `STORAGE_BACKEND=local` يعني أن **كل ما رُفع
بين نشرتين يختفي** — والنظام لا يشتكي: السجلّ في القاعدة والملف مفقود.
هذا وحده يوجب S3 على AWS.

### الترحيلات تتسابق

الحاوية تُقلع بـ`python -m app.db_migrate` ثم الخادم. وبنسختين تُقلعان
معًا يشتغل alembic مرّتين على قاعدة واحدة.

**العلاج:** أبقِ العدد المطلوب **1** أثناء الترحيل، وارفعه بعده. أو شغّل
الترحيل مهمّة منفصلة مرّة واحدة ثم انشر.

### المجدول آمن — وهذه ليست صدفة

`daily_scan` و`sla_scan` و`digest_scan` كلها داخل `run_once` بقفل في
القاعدة ([scheduler.py:53](../backend/app/scheduler.py:53))، فالنسخة
الثانية تجد المهمة مأخوذة وتنصرف. يمكنك زيادة النسخ بلا إشعارات مكرّرة.

### الساعة (AWS-03)

فحص الصحّة يبلّغ `clock.skew_seconds`. انحرافها يفسد صلاحية الرموز
وتواريخ التدقيق. Fargate يزامن الوقت تلقائًيا — تحقّق بعد النشر ولا
تفترض.

### الخطوط

الصورة تحمل LibreOffice وخطوًطا عربية موثَّقة بالقياس. بعد أول نشرة:

```bash
curl -s https://<النطاق>/api/health/deep
```

في `gov_contract` يجب أن ترى `"status":"ok"` وأسماء خطوط عربية صريحة.
غير ذلك يعني عقًدا بمربّعات فارغة يبدو توليده ناجًحا.

---

## 8. الترتيب

1. VPC ومجموعتا الأمان
2. RDS، ونقل القاعدة، والتحقّق من `alembic_version`
3. الدلو، ورفع الملفات، و`--verify`
4. السرّ والدوران
5. ECR ورفع الصورة
6. ECS بنسخة **واحدة** + ALB
7. الشهادة والنطاق
8. `‎/api/health/deep` — كل الأقسام `ok`
9. `STORAGE_BACKEND=s3` ونشرة ثانية
10. رفع عدد النسخ
11. إيقاف Railway **بعد** أسبوع من الاستقرار لا قبله

---

## 9. الكلفة التقريبية (شهرًيا، بالدولار)

| البند | تقريًبا |
|---|---|
| Fargate (1 vCPU / 2 GB، نسخة دائمة) | 35–45 |
| RDS db.t4g.micro + 20 GB | 15–20 |
| ALB | 16–20 |
| S3 + النقل | 2–5 |
| **المجموع** | **‎~70–90** |

Multi-AZ للقاعدة يضيف مثل كلفتها. والتقدير للاستعمال المتوقَّع لا لسقف.

---

## 10. بعد النشر

- عطّل الوصول العام للقاعدة إن كنت فتحته للنقل
- احذف نسخة EC2 المؤقّتة
- امسح `hrms.dump` من جهازك — نسخة كاملة من بيانات الموظفين
- فعّل تنبيه فاتورة
- جرّب **استرجاًعا** من نسخة احتياطية مرة واحدة: نسخة لم تُجرَّب ليست نسخة

ثم [دفتر BKL-07](qa/BKL07_E2E_RUNBOOK.md) على البيئة الجديدة.
