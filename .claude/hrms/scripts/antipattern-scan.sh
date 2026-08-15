#!/usr/bin/env bash
# HRMS Anti-Pattern Scanner
# يفحص الكود عن الأنماط الممنوعة صراحة في المواصفة V2.2 §15 و §28.4
# الاستخدام: bash .claude/hrms/scripts/antipattern-scan.sh [مسار-المشروع]

ROOT="${1:-.}"
# .venv/site-packages: مكتبات الطرف الثالث ليست كود المشروع. bleach وحدها
# تُنتج ثمانية إيجابيات كاذبة في AP-06 (innerHTML داخل html5lib) فتُخفي
# أي مخالفة حقيقية وسط الضجيج.
EXCLUDE='--exclude-dir=node_modules --exclude-dir=.git --exclude-dir=vendor --exclude-dir=dist --exclude-dir=build --exclude-dir=.next --exclude-dir=coverage --exclude-dir=.claude --exclude-dir=.venv --exclude-dir=venv --exclude-dir=site-packages --exclude-dir=__pycache__ --exclude-dir=legacy_prototype'
FOUND=0

hit() { # $1=code $2=وصف $3=نمط $4=امتداد-اختياري
  local out
  out=$(grep -rniE $EXCLUDE ${4:+--include=$4} "$3" "$ROOT" 2>/dev/null | head -20)
  if [ -n "$out" ]; then
    echo ""
    echo "[!] $1 — $2"
    echo "$out" | sed 's/^/      /'
    FOUND=$((FOUND+1))
  fi
}

echo "=== HRMS Anti-Pattern Scan — $ROOT ==="

hit "AP-01" "صلاحية موافقة عامة بدل الصلاحيات المفصولة (§4.5)" \
    "approve_request|can_approve_all|permission[\"']?:? ?[\"']approve[\"']"

hit "AP-02" "شريط Approve/Reject موحّد في الواجهة (§9.2)" \
    "ApproveRejectBar|approveRejectButtons|<ApprovalActions"

hit "AP-03" "حدود سياسة مكتوبة داخل الكود بدل policy_rule (§7)" \
    "(amount|threshold|limit|max_days) *[><=]+ *[0-9]{2,}"

hit "AP-04" "حالات الطباعة مدموجة في حالة الطلب (§3.3، §15)" \
    "READY_TO_PRINT|PRINT_TO_READY|'PRINTED'|\"PRINTED\"|status.*=.*FILED"

hit "AP-05" "Super Admin كموافق افتراضي (§15)" \
    "super_?admin.*(approve|fallback_approver|default_approver)"

hit "AP-06" "توليد HTML/JS حر داخل مسار المستند (§28.4)" \
    "innerHTML|dangerouslySetInnerHTML|eval\(|new Function\("

hit "AP-07" "إنشاء طلب جديد عند إعادة المعلومات (§15)" \
    "create.*request.*needs_info|new Request.*NEEDS_INFO"

hit "AP-08" "استخدام request payload كمصدر لأرقام الراتب في المستند (§25.1)" \
    "payload\.(basic_salary|gross_salary|allowances)"

hit "AP-09" "ادعاء التوقيع الإلكتروني المحمي بلا تشفير (§27.2، DOC-07)" \
    "Protected Electronic Signature|توقيع إلكتروني محمي"

hit "AP-10" "اسم ملف المستند بلا document_number (§29)" \
    "filename.*employee_name|\.pdf.*\$\{name\}"

hit "AP-11" "حالة Pending بلا خطوة/معيّن (§15)" \
    "status *[:=] *['\"]?pending['\"]?[^_a-zA-Z]" "*.sql"

echo ""
if [ "$FOUND" -eq 0 ]; then
  echo "نظيف — لم يُعثر على أنماط ممنوعة."
  exit 0
else
  echo "=== عُثر على $FOUND نمط ممنوع. راجع البنود أعلاه قبل الدمج. ==="
  echo "ملاحظة: بعض النتائج قد تكون إيجابيات كاذبة — راجعها يدويا ولا تحذف بلا فهم."
  exit 1
fi
