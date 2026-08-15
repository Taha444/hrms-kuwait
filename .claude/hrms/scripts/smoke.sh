#!/usr/bin/env bash
# فحص سريع: هل النظام حي؟ هل كل دور يدخل؟ هل الـ endpoints الأساسية ترد؟
# الاستخدام: source .claude/hrms/scripts/env.sh && bash .claude/hrms/scripts/smoke.sh
set -uo pipefail
: "${HRMS_BASE_URL:?شغّل env.sh أولا}"
B="$HRMS_BASE_URL"; LP="${HRMS_LOGIN_PATH:-/api/auth/login}"; TF="${HRMS_TOKEN_FIELD:-token}"
FAIL=0

echo "=== HRMS Smoke — $B ==="
echo "الوقت: $(date -u +%FT%TZ) UTC"
echo ""

echo "--- 1. النظام حي ---"
code=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 15 "$B/" || echo 000)
echo "GET /            → $code"
[ "$code" = "000" ] && { echo "!! لا يمكن الوصول للخادم"; exit 1; }

for p in /health /api/health /api/version /api/system/health; do
  c=$(curl -sk -o /tmp/h.json -w '%{http_code}' --max-time 10 "$B$p" || echo 000)
  [ "$c" = "200" ] && { echo "GET $p → 200"; head -c 400 /tmp/h.json; echo ""; }
done

echo ""
echo "--- 2. تسجيل الدخول بكل دور ---"
login() { # $1=role
  local uv="HRMS_${1}_USER" pv="HRMS_${1}_PASS"
  local u="${!uv:-}" p="${!pv:-}"
  [ -z "$u" ] && { echo "$1: (لا يوجد حساب مضبوط)"; return 1; }
  local r; r=$(curl -sk --max-time 15 -X POST "$B$LP" -H 'Content-Type: application/json' \
        -d "{\"username\":\"$u\",\"password\":\"$p\"}" 2>/dev/null)
  local t; t=$(echo "$r" | python3 -c "import sys,json;print(json.load(sys.stdin).get('$TF',''))" 2>/dev/null)
  if [ -n "$t" ]; then echo "$1: OK"; echo "$t" > "/tmp/tok_$1"; return 0
  else echo "$1: FAIL — $(echo "$r" | head -c 200)"; FAIL=$((FAIL+1)); return 1; fi
}
for R in EMPLOYEE SUPERVISOR MANAGER HR ACCOUNTANT PRO OWNER SUPERADMIN; do login "$R"; done

echo ""
echo "--- 3. الـ endpoints الأساسية لكل دور ---"
EPS="/api/employees /api/requests /api/tasks /api/notifications /api/renewals"
printf "%-12s" "الدور"; for e in $EPS; do printf "%-22s" "$(basename $e)"; done; echo ""
for R in EMPLOYEE SUPERVISOR MANAGER HR ACCOUNTANT PRO OWNER SUPERADMIN; do
  [ -f "/tmp/tok_$R" ] || continue
  T=$(cat "/tmp/tok_$R"); printf "%-12s" "$R"
  for e in $EPS; do
    c=$(curl -sk -o /tmp/b.json -w '%{http_code}' --max-time 15 -H "Authorization: Bearer $T" "$B$e" || echo 000)
    n=$(python3 -c "
import json
try:
    d=json.load(open('/tmp/b.json'))
    d=d.get('data',d) if isinstance(d,dict) else d
    print(len(d) if isinstance(d,(list,dict)) else '-')
except: print('-')" 2>/dev/null)
    flag=""; [ "$c" = "500" ] && { flag="!!"; FAIL=$((FAIL+1)); }
    printf "%-22s" "$c/$n$flag"
  done; echo ""
done

echo ""
echo "--- 4. تسريب معلومات ---"
for p in /.env /.git/config /api/config /actuator /debug; do
  c=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 8 "$B$p" || echo 000)
  [ "$c" = "200" ] && { echo "!! $p متاح للعامة (200)"; FAIL=$((FAIL+1)); }
done
srv=$(curl -skI --max-time 8 "$B/" | grep -iE '^(server|x-powered-by):' || true)
[ -n "$srv" ] && echo "ترويسات تكشف التقنية: $srv"

echo ""
rm -f /tmp/tok_* /tmp/b.json /tmp/h.json
if [ "$FAIL" -eq 0 ]; then echo "=== Smoke نظيف ==="; exit 0
else echo "=== $FAIL مشكلة — راجع أعلاه ==="; exit 1; fi
