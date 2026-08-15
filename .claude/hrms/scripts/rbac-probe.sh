#!/usr/bin/env bash
# مصفوفة دور × endpoint — أسرع طريقة لكشف ثغرات الصلاحيات
# الاستخدام: source env.sh && bash .claude/hrms/scripts/rbac-probe.sh
set -uo pipefail
: "${HRMS_BASE_URL:?شغّل env.sh أولا}"
B="$HRMS_BASE_URL"; LP="${HRMS_LOGIN_PATH:-/api/auth/login}"; TF="${HRMS_TOKEN_FIELD:-token}"

# عدّل القائمة حسب مسارات النظام الفعلية
SENSITIVE="/api/employees /api/payroll /api/payroll/run /api/eos /api/documents
/api/employees/1/passport /api/employees/1/civil-id /api/employees/1/contract
/api/warnings /api/grievances /api/leaves /api/signatures /api/audit
/api/renewals /api/templates /api/users /api/permissions /api/companies"

tok() {
  local uv="HRMS_${1}_USER" pv="HRMS_${1}_PASS" u p r
  u="${!uv:-}"; p="${!pv:-}"; [ -z "$u" ] && return 1
  r=$(curl -sk --max-time 15 -X POST "$B$LP" -H 'Content-Type: application/json' \
      -d "{\"username\":\"$u\",\"password\":\"$p\"}" 2>/dev/null)
  echo "$r" | python3 -c "import sys,json;print(json.load(sys.stdin).get('$TF',''))" 2>/dev/null
}

echo "=== RBAC Probe — $B ==="
echo "الرمز: كود HTTP · '!' = 200 لدور يُتوقع منعه · '?' = يحتاج مراجعة يدوية"
echo ""
printf "%-42s" "endpoint"
for R in EMPLOYEE SUPERVISOR MANAGER HR ACCOUNTANT PRO OWNER; do printf "%-8s" "${R:0:6}"; done
echo ""
printf '%.0s-' {1..100}; echo ""

declare -A T
for R in EMPLOYEE SUPERVISOR MANAGER HR ACCOUNTANT PRO OWNER; do T[$R]=$(tok "$R" || echo ""); done

for e in $SENSITIVE; do
  printf "%-42s" "$e"
  for R in EMPLOYEE SUPERVISOR MANAGER HR ACCOUNTANT PRO OWNER; do
    if [ -z "${T[$R]}" ]; then printf "%-8s" "—"; continue; fi
    c=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 12 \
        -H "Authorization: Bearer ${T[$R]}" "$B$e" || echo 000)
    m=""
    case "$e:$R" in
      */passport*:ACCOUNTANT|*/civil-id*:ACCOUNTANT|*/contract*:ACCOUNTANT|\
      */warnings*:ACCOUNTANT|*/eos*:ACCOUNTANT|*/leaves*:ACCOUNTANT|*/documents*:ACCOUNTANT)
        [ "$c" = "200" ] && m="!" ;;
      */payroll*:PRO|*/payroll*:EMPLOYEE|*/payroll*:SUPERVISOR)
        [ "$c" = "200" ] && m="!" ;;
      */grievances*:MANAGER|*/grievances*:PRO|*/grievances*:ACCOUNTANT)
        [ "$c" = "200" ] && m="!" ;;
      */users*:EMPLOYEE|*/permissions*:EMPLOYEE|*/templates*:EMPLOYEE|*/audit*:EMPLOYEE)
        [ "$c" = "200" ] && m="!" ;;
    esac
    [ "$c" = "500" ] && m="?"
    printf "%-8s" "$c$m"
  done
  echo ""
done

echo ""
echo "'!' = ثغرة صلاحيات محتملة — تحقق يدويا من جسم الرد"
echo "'?' = خطأ خادم — سجّله كعيب مستقل"
echo "ملاحظة: المصفوفة تفحص القراءة فقط. الكتابة تُختبر يدويا وعلى Staging حصرا."
