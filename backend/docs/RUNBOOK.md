# HRMS Kuwait — Operations Runbook

## Backup and restore

### Postgres database backup
- Full daily dump before scheduled maintenance
  ```bash
  pg_dump -Fc -Z9 -h $PGHOST -U $PGUSER -d $PGDATABASE -f "hrms_$(date +%F).dump"
  ```
- Weekly logical snapshot to cold storage (S3/Backblaze/OneDrive) with server-side encryption.
- Retention:
  - Hot (immediate restore): last 14 days on the primary storage
  - Cold: 12 monthly snapshots for the past year

### Restore procedure
1. Provision a new empty database at the same version.
2. `pg_restore -h $PGHOST -U $PGUSER -d $PGDATABASE_NEW hrms_YYYY-MM-DD.dump`
3. Run `alembic upgrade head` — the app requires the migration head recorded in `/api/manifest`.
4. Smoke-test:
   - `GET /api/health/deep` → `status: ok`
   - Login as `000000000000` and reach the dashboard
   - Verify the current period's payroll run exists and matches the snapshot

### Restore drill (mandatory)
Run every quarter. Point-in-time restore into a scratch DB and validate row counts against the primary. Log the drill result in `docs/DRILL_LOG.md`.

## Uploads / attachments backup
- `settings.upload_dir` (default `/var/data/uploads/`) is rsync-mirrored nightly.
- Signature scans, selfies, government docs, and generated PDFs live here.
- Confirm `/api/health/deep`.checks.storage.writable = true.

## Rollback plan (deploy failure)

1. Detect: monitoring (Sentry error rate ≥ 5% or 5xx > 1% for 2 minutes).
2. Roll back on Railway → previous deployment → **Rollback**.
3. If the migration is not idempotent-forward-compatible, run `alembic downgrade -1` first.
4. Announce in the incident channel; open an incident record referencing the failing deploy SHA.
5. Never delete the failing deployment — keep it for the post-mortem.

## Migration deployment order (irreversible order)

All Alembic revisions are chained; they must be applied in order:
```
68862c46506d  → initial
57b1c9e2001e  → user_data_scope
a1b2c3d4e5f6  → user_scope_level
45fe0c3773a6  → user_status
d4e5f6a7b8c9  → residency_renewals
b2c3d4e5f6a7  → employee_actual_fields
b8c9d0e1f2a3  → request_type_confidential
a7b8c9d0e1f2  → notification_templates
e5f6a7b8c9d0  → request_type_category
d0e1f2a3b4c5  → request_type_visible_to_employee
c3d4e5f6a7b8  → employee_eos_saved
c9d0e1f2a3b4  → document_template_name_en
f6a7b8c9d0e1  → print_job_filing_log
a3b4c5d6e7f8  → v15_phase5_feature_flags
e1f2a3b4c5d6  → v15_phase3_claim_delegation_sla
f2a3b4c5d6e7  → v15_phase4_od_code_lifecycle
b4c5d6e7f8a9  → sig01_user_signature
d6e7f8a9b0c1  → pilot_p05_pending_signature
c5d6e7f8a9b0  → pilot_employee_no_commercial_reg_unique
e7f8a9b0c1d2  → pilot_p07_payroll_workflow (+ p08 termination)
f8a9b0c1d2e3  → sec2_15_authorized_signatories
09b0c1d2e3f4  → sec2_17_attendance_policy
1a0b1c2d3e4f  → v22_form_schema_workflow_fields
2b1c2d3e4f50  → v22_audit_expanded_fields
3c2d3e4f5061  → v22_document_artifact_checksum
4d3e4f506172  → v22_tokens_valid_after
5e4f50617283  → v22_totp_2fa
6f5061728394  → v22_attendance_close_template_ver_task_delivery
```

Never merge a migration whose down_revision does not point to the current tip.

## Monitoring endpoints
- `GET /api/health` — liveness, no auth
- `GET /api/health/deep` — DB + storage + scheduler + registry counts (503 when any fails)
- `GET /api/manifest` — version + commit + alembic head + registry stats
- Structured JSON logs: one line per HTTP request (`event: http_request`), ingest into Datadog/CloudWatch.

## Incident checklist

1. Freeze deploys (Railway → env → Auto Deploy off).
2. Snapshot current state (`pg_dump` + latest deploy artifact).
3. Reproduce in the staging environment or a scratch DB restored from step 2.
4. Diagnose using structured logs + audit_log (`correlation_id` filter) + before/after JSON.
5. Fix on a branch, run full test suite, deploy to staging first.
6. Post-mortem in `docs/INCIDENTS/YYYY-MM-DD.md`.

## Data retention

- `audit_log` — 7 years (legal requirement for Kuwaiti employment records)
- `attendance_records` — 5 years
- `payroll_runs` (with `totals_json`) — 7 years, `locked` runs are immutable
- `request_documents` (generated PDFs) — 7 years for HR-visible types; grievance/investigation records — permanent

## Security response

- Suspected credential leak: reset all sessions with a mass `UPDATE users SET tokens_valid_after=now()`. Rotate `SECRET_KEY` in Railway env. Force `must_change_password=true` for affected users.
- Compromised admin: revoke via `PUT /api/users/{id}/disable`, then rotate secrets. `tokens_valid_after` bump kills active sessions immediately.
