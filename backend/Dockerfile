# صورة الواجهة الخلفية (FastAPI)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# tesseract-ocr: يُفعِّل قراءة MRZ من صورة الجواز فعليًا (app/ocr.py يكتشفه تلقائيًا)
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# عند الإقلاع: تطبيق الهجرات ثم تشغيل الخادم
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
