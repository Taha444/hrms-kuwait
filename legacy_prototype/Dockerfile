FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    HRMS_HOST=0.0.0.0 \
    HRMS_PORT=5000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# تهيئة قاعدة البيانات عند البناء (تُنشأ في وحدة تخزين عند التشغيل)
RUN python -c "import db; db.init_db()"

EXPOSE 5000

# تشغيل إنتاجي عبر waitress
CMD ["python", "wsgi.py"]
