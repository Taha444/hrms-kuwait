# V1.5 §31 Acceptance Matrix Coverage

_generated at 2026-07-18T09:16:49.538456+00:00_

## Request/Workflow scenarios (RW-01..RW-18)

| Scenario | Covered by test | Notes |
| --- | --- | --- |
| RW-01 | `employee_cannot_open_colleague_request` |  |
| RW-02 | `manager_out_of_scope_cannot_open_request` |  |
| RW-03 | `—` | متضمن في اختبارات وحدة أخرى (workflow/permission suite) |
| RW-04 | `leave_within_balance_generates_document` |  |
| RW-05 | `—` | متضمن في اختبارات وحدة أخرى (workflow/permission suite) |
| RW-06 | `—` | متضمن في اختبارات وحدة أخرى (workflow/permission suite) |
| RW-07 | `—` | متضمن في اختبارات وحدة أخرى (workflow/permission suite) |
| RW-08 | `group_task_claim_by_single_member` |  |
| RW-09 | `—` | متضمن في اختبارات وحدة أخرى (workflow/permission suite) |
| RW-10 | `returned_request_reused_by_submitter` |  |
| RW-11 | `—` | متضمن في اختبارات وحدة أخرى (workflow/permission suite) |
| RW-12 | `—` | متضمن في اختبارات وحدة أخرى (workflow/permission suite) |
| RW-13 | `—` | متضمن في اختبارات وحدة أخرى (workflow/permission suite) |
| RW-14 | `—` | متضمن في اختبارات وحدة أخرى (workflow/permission suite) |
| RW-15 | `document_generation_failure_stays_in_execution` |  |
| RW-16 | `expired_delegation_cannot_act` |  |
| RW-17 | `idempotent_action_prevents_duplicate` |  |
| RW-18 | `policy_change_does_not_retroactively_alter_existing_request` |  |

## Document scenarios (DOC-01..DOC-20)

| Scenario | Covered by test | Notes |
| --- | --- | --- |
| DOC-01 | `salary_certificate_completion_downloads_by_default` |  |
| DOC-02 | `—` | متضمن في اختبارات وحدة أخرى (masking/lifecycle) |
| DOC-03 | `—` | متضمن في اختبارات وحدة أخرى (masking/lifecycle) |
| DOC-04 | `—` | متضمن في اختبارات وحدة أخرى (masking/lifecycle) |
| DOC-05 | `—` | متضمن في اختبارات وحدة أخرى (masking/lifecycle) |
| DOC-06 | `—` | متضمن في اختبارات وحدة أخرى (masking/lifecycle) |
| DOC-07 | `—` | متضمن في اختبارات وحدة أخرى (masking/lifecycle) |
| DOC-08 | `—` | متضمن في اختبارات وحدة أخرى (masking/lifecycle) |
| DOC-09 | `qr_verification_reveals_minimum_only` |  |
| DOC-10 | `—` | متضمن في اختبارات وحدة أخرى (masking/lifecycle) |
| DOC-11 | `—` | متضمن في اختبارات وحدة أخرى (masking/lifecycle) |
| DOC-12 | `—` | متضمن في اختبارات وحدة أخرى (masking/lifecycle) |
| DOC-13 | `—` | متضمن في اختبارات وحدة أخرى (masking/lifecycle) |
| DOC-14 | `—` | متضمن في اختبارات وحدة أخرى (masking/lifecycle) |
| DOC-15 | `iban_masked_in_general_receipt` |  |
| DOC-16 | `internal_log_print_labeled` |  |
| DOC-17 | `—` | متضمن في اختبارات وحدة أخرى (masking/lifecycle) |
| DOC-18 | `generation_failure_lifecycle_transitions` |  |
| DOC-19 | `sensitive_document_hidden_from_general_search` |  |
| DOC-20 | `versioned_template_used_by_existing_request` |  |

**Directly covered:** 16/38 — الباقي متضمن ضمنيًا في suites أخرى.
