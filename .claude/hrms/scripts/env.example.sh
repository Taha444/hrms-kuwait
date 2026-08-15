# انسخه إلى .claude/hrms/scripts/env.sh واملأه — و.env.sh مستثنى من git
# ممنوع رفع هذا الملف مملوءا إلى أي مستودع

export HRMS_BASE_URL="https://staging.example.com"
export HRMS_ENV="staging"          # staging | client
export HRMS_COMPANIES="GUF MUF"

# حسابات الاختبار — من بيئة Staging فقط
export HRMS_EMPLOYEE_USER=""       ; export HRMS_EMPLOYEE_PASS=""
export HRMS_SUPERVISOR_USER=""     ; export HRMS_SUPERVISOR_PASS=""
export HRMS_MANAGER_USER=""        ; export HRMS_MANAGER_PASS=""
export HRMS_HR_USER=""             ; export HRMS_HR_PASS=""
export HRMS_ACCOUNTANT_USER=""     ; export HRMS_ACCOUNTANT_PASS=""
export HRMS_PRO_USER=""            ; export HRMS_PRO_PASS=""
export HRMS_OWNER_USER=""          ; export HRMS_OWNER_PASS=""
export HRMS_SUPERADMIN_USER=""     ; export HRMS_SUPERADMIN_PASS=""

# مسارات الـ API — عدّلها حسب النظام
export HRMS_LOGIN_PATH="/api/auth/login"
export HRMS_TOKEN_FIELD="token"
