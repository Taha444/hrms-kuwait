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

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
# الواجهة المبنية تُقدَّم من الخادم (main.py يبحث عن frontend/dist)
COPY --from=frontend /app/frontend/dist ./frontend/dist

WORKDIR /app/backend
# تعبئة بيانات تجريبية ثم تشغيل الخادم على منفذ المنصّة (افتراضي 8000)
CMD ["sh", "-c", "python -m app.seed; uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
