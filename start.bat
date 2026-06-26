@echo off
REM تشغيل التطوير على ويندوز: الخلفية (8000) + الأمامية (5173)
setlocal
set ROOT=%~dp0

echo ==^> تهيئة الواجهة الخلفية
cd /d "%ROOT%backend"
if not exist .venv ( py -3.11 -m venv .venv )
call .venv\Scripts\activate
pip install -q -r requirements.txt
if not exist .env ( copy .env.example .env )
if not exist hrms_app.db ( python -m app.seed )
start "HRMS API" cmd /k "call .venv\Scripts\activate && uvicorn app.main:app --reload --port 8001"

echo ==^> تهيئة الواجهة الأمامية
cd /d "%ROOT%frontend"
if not exist node_modules ( npm install )
npm run dev
endlocal
