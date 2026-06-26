@echo off
REM تشغيل سريع للنظام على Windows
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1

REM إنشاء بيئة افتراضية إن لم تكن موجودة
if not exist "venv" (
  echo ^>^> انشاء بيئة افتراضية...
  python -m venv venv
)

REM تفعيل البيئة
call venv\Scripts\activate.bat

REM تثبيت المتطلبات
echo ^>^> تثبيت المتطلبات...
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt

REM تهيئة قاعدة البيانات بالبيانات التجريبية (مرة واحدة فقط)
if not exist "instance\hrms.db" (
  echo ^>^> تهيئة قاعدة البيانات واضافة بيانات تجريبية...
  python seed.py
)

echo.
echo ===================================================
echo   النظام يعمل الان على:  http://127.0.0.1:5000
echo   حسابات الدخول:  admin / admin123
echo   للايقاف اضغط:  Ctrl + C
echo ===================================================
echo.

python app.py
