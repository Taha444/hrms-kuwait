#!/usr/bin/env bash
# تشغيل التطوير: الواجهة الخلفية (8000) + الواجهة الأمامية (5173)
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "==> تهيئة الواجهة الخلفية"
cd "$ROOT/backend"
if [ ! -d ".venv" ]; then python -m venv .venv; fi
# shellcheck disable=SC1091
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate
pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
[ -f hrms_app.db ] || python -m app.seed
uvicorn app.main:app --reload --port 8001 &
API_PID=$!

echo "==> تهيئة الواجهة الأمامية"
cd "$ROOT/frontend"
[ -d node_modules ] || npm install
npm run dev

kill $API_PID 2>/dev/null || true
