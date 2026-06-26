#!/usr/bin/env bash
# تشغيل سريع للنظام على Linux / macOS
set -e
cd "$(dirname "$0")"
export PYTHONUTF8=1

# إنشاء بيئة افتراضية إن لم تكن موجودة
if [ ! -d "venv" ]; then
  echo ">> إنشاء بيئة افتراضية..."
  python3 -m venv venv
fi

# تفعيل البيئة
source venv/bin/activate

# تثبيت المتطلبات
echo ">> تثبيت المتطلبات..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# تهيئة قاعدة البيانات بالبيانات التجريبية (مرة واحدة فقط)
if [ ! -f "instance/hrms.db" ]; then
  echo ">> تهيئة قاعدة البيانات وإضافة بيانات تجريبية..."
  python seed.py
fi

echo ""
echo "==================================================="
echo "  النظام يعمل الآن على:  http://127.0.0.1:5000"
echo "  حسابات الدخول:  admin / admin123"
echo "  للإيقاف اضغط:  Ctrl + C"
echo "==================================================="
echo ""

python app.py
