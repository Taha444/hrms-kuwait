# Dockerfile للإنتاج (Railway/أي منصّة): يبني الواجهة ثم يشغّل الخادم الذي
# يقدّم الواجهة (frontend/dist) والـ API معًا على منفذ واحد ($PORT).

# ---------- المرحلة 1: بناء الواجهة الأمامية ----------
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# ---------- المرحلة 2: الخادم الخلفي + تقديم الواجهة ----------
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# gcc/libpq: SQLAlchemy + psycopg2
# tesseract-ocr + حزم eng/ara: قراءة MRZ للجواز والبطاقة المدنية الكويتية (app/ocr.py)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
# الواجهة المبنية تُقدَّم من الخادم (main.py يبحث عن frontend/dist)
COPY --from=frontend /app/frontend/dist ./frontend/dist

WORKDIR /app/backend
# إقلاع آمن:
#  1) app.db_migrate — يطبّق الترحيلات ويفشل بصوت مسموع إن تعذّر.
#     كان الأمر هنا `alembic upgrade head || alembic stamp head`، و`stamp head`
#     يكتب رقم أحدث إصدار بلا تطبيق أي ترحيل — فأي فشل مرة واحدة يختم القاعدة
#     عند الرأس وكل نشر بعدها يراها محدَّثة فلا يطبّق شيًئا، صامتًا وإلى الأبد.
#     الختم الآن محصور بحالته الحقيقية (قاعدة create_all بلا alembic_version)
#     وعند إصدار الأساس لا الرأس، فتُطبَّق الترحيلات اللاحقة فعًلا.
#  2) bootstrap — يعبّئ super_admin + owner على قاعدة فارغة (idempotent).
#  3) uvicorn — تشغيل الخادم.
# && لا ; — لا نُقلع بمخطط قديم إن فشلت الترحيلات.
CMD ["sh", "-c", "python -m app.db_migrate && python -m app.bootstrap && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
