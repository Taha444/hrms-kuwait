# انسخه إلى env.sh واملأه — و env.sh في .gitignore
# ممنوع رفعه مملوءا إلى أي مستودع

export HRMS_BASE_URL="https://staging.example.com"
export HRMS_ENV="staging"          # staging | client
export HRMS_LOGIN_PATH="/api/auth/login"
export HRMS_TOKEN_FIELD="token"
export HRMS_PROBE_IDS="1,2,5,10,11,99,999999"

export HRMS_EMPLOYEE_USER="";   export HRMS_EMPLOYEE_PASS=""
export HRMS_SUPERVISOR_USER=""; export HRMS_SUPERVISOR_PASS=""
export HRMS_MANAGER_USER="";    export HRMS_MANAGER_PASS=""
export HRMS_HR_USER="";         export HRMS_HR_PASS=""
export HRMS_ACCOUNTANT_USER=""; export HRMS_ACCOUNTANT_PASS=""
export HRMS_PRO_USER="";        export HRMS_PRO_PASS=""
export HRMS_OWNER_USER="";      export HRMS_OWNER_PASS=""
export HRMS_SUPERADMIN_USER=""; export HRMS_SUPERADMIN_PASS=""
