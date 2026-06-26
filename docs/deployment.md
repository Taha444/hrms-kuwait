# دليل النشر (Deployment)

## 1) النشر السريع بـ Docker Compose
```bash
cp .env.example .env        # عدّل SECRET_KEY و POSTGRES_PASSWORD و CORS_ORIGINS
docker compose up --build -d
```
- `web` (nginx) على المنفذ 80 يقدّم الواجهة ويمرّر `/api` و`/uploads` إلى `api`.
- `api` يطبّق `alembic upgrade head` تلقائيًا عند الإقلاع ثم يشغّل uvicorn.
- `db` تخزّن البيانات في حجم دائم `db_data`، والملفات المرفوعة في `uploads`.

### تعبئة بيانات تجريبية (اختياري بعد الإقلاع)
```bash
docker compose exec api python -m app.seed
```

## 2) HTTPS عبر Caddy (موصى به للإنتاج)
ضع Caddy كبروكسي أمامي للحصول على شهادة TLS تلقائية:
```
# Caddyfile
your-domain.com {
    reverse_proxy web:80
}
```
أضِف خدمة `caddy` إلى docker-compose واربطها بشبكة المشروع، أو استخدم Caddy/Nginx على
المضيف موجِّهًا إلى منفذ `web`. حدّث `CORS_ORIGINS` إلى `https://your-domain.com`.

## 3) الهجرات (Migrations) يدويًا
```bash
cd backend
alembic upgrade head                         # تطبيق
alembic revision --autogenerate -m "msg"     # إنشاء هجرة جديدة بعد تعديل النماذج
```

## 4) النسخ الاحتياطي
```bash
# نسخ احتياطي لقاعدة PostgreSQL
docker compose exec db pg_dump -U hrms hrms > backup_$(date +%F).sql
# استعادة
cat backup.sql | docker compose exec -T db psql -U hrms hrms
```
احتفظ كذلك بنسخة من حجم `uploads` (المستندات وصور السيلفي).

## 5) الأمان في الإنتاج — قائمة تحقق
- [ ] `SECRET_KEY` عشوائي طويل و`POSTGRES_PASSWORD` قوي.
- [ ] HTTPS مفعّل، و`CORS_ORIGINS` مقصور على دومينك.
- [ ] نسخ احتياطي دوري لقاعدة البيانات و`uploads`.
- [ ] مراقبة سجلّات `api` و`web`.
- [ ] تدوير صور السيلفي/المستندات القديمة حسب سياسة الاحتفاظ.

## 6) متغيّرات البيئة المهمة (الواجهة الخلفية)
| المتغيّر | الوصف |
|---|---|
| `DATABASE_URL` | رابط قاعدة البيانات (postgresql+psycopg2/… أو sqlite:///…) |
| `SECRET_KEY` | مفتاح توقيع JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | مدد الرموز |
| `UPLOAD_DIR` | مجلد الملفات المرفوعة |
| `CORS_ORIGINS` | أصول الواجهة المسموح بها |
| `SCHEDULER_ENABLED` | تفعيل المسح اليومي |
| `DEFAULT_USER_PASSWORD` | كلمة المرور الموحّدة لأول دخول |
