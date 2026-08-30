#!/usr/bin/env bash
# جرد سطح الـ API من الكود — يستخرج ما يستطيع ويطبع ما يحتاج عملا يدويا
# الاستخدام: bash .claude/hrms/scripts/discover.sh [مسار-المشروع]
ROOT="${1:-.}"
OUT=".claude/hrms/audit"
mkdir -p "$OUT"
EX='--exclude-dir=node_modules --exclude-dir=.git --exclude-dir=vendor --exclude-dir=dist --exclude-dir=build --exclude-dir=.claude'

echo "=== جرد سطح الـ API — $ROOT ==="
echo ""
echo "--- الستاك المكتشف ---"
[ -f "$ROOT/artisan" ]           && echo "Laravel   → php artisan route:list --json"
[ -f "$ROOT/config/routes.rb" ]  && echo "Rails     → rails routes"
[ -f "$ROOT/manage.py" ]         && echo "Django    → python manage.py show_urls"
[ -f "$ROOT/nest-cli.json" ]     && echo "NestJS    → افحص @Controller و @Get/@Post"
[ -f "$ROOT/package.json" ]      && echo "Node      → افحص ملفات الراوتر"
[ -f "$ROOT/go.mod" ]            && echo "Go        → افحص تسجيل المسارات"

echo ""
echo "--- مسارات مستخرجة بالبحث ---"
grep -rhoE "(Route::(get|post|put|patch|delete)|router\.(get|post|put|patch|delete)|app\.(get|post|put|patch|delete))\(['\"][^'\"]+" $EX "$ROOT" 2>/dev/null \
  | grep -oE "['\"][^'\"]+$" | tr -d "\"'" | sort -u | tee "$OUT/routes-raw.txt" | head -60
echo ""
echo "(الكل في $OUT/routes-raw.txt — العدد: $(wc -l < "$OUT/routes-raw.txt" 2>/dev/null || echo 0))"

echo ""
echo "--- مسارات بلا middleware مصادقة ظاهر (فحص أولي) ---"
grep -rnE "Route::(get|post)\(" $EX "$ROOT" 2>/dev/null | grep -v "middleware" | head -20

echo ""
echo "--- catch يبتلع الأخطاء (يخفي 500) ---"
grep -rnE "catch\s*\([^)]*\)\s*\{\s*\}" $EX "$ROOT" 2>/dev/null | head -10
grep -rn "catch" $EX --include=*.php --include=*.js --include=*.ts "$ROOT" 2>/dev/null \
  | grep -iE "return (null|\[\]|response\(\)->json\(\[\]\))" | head -10

echo ""
echo "--- استعلامات بنص مباشر (مرشح SQLi) ---"
grep -rnE "(DB::raw|query\(|execute\(|rawQuery)" $EX "$ROOT" 2>/dev/null | head -15

echo ""
echo "--- SELECT * ---"
grep -rn "SELECT \*" $EX "$ROOT" 2>/dev/null | head -10

echo ""
echo "--- رفع الملفات ---"
grep -rnE "(upload|multipart|FormData|move_uploaded|putFile|store\()" $EX "$ROOT" 2>/dev/null | head -15

echo ""
echo "--- الكتابة على القرص (يجب أن تكون على تخزين دائم) ---"
grep -rnE "(\./uploads|storage_path|__dirname.*upload|fs\.writeFile)" $EX "$ROOT" 2>/dev/null | head -15

echo ""
echo "=== الخطوة التالية ==="
echo "1. شغّل أمر الستاك أعلاه للحصول على القائمة الكاملة والدقيقة"
echo "2. اكتبها في $OUT/endpoints.json بالشكل:"
echo '   { "read_endpoints": ["/api/employees", ...], '
echo '     "write_endpoints": [...], "id_endpoints": [...] }'
echo "3. ثم: python3 .claude/hrms/scripts/probe_matrix.py --all"
