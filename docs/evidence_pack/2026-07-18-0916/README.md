# HRMS Kuwait — Evidence Pack

**Generated at:** 2026-07-18T09:16:48.136072+00:00
**Commit:** `5d70d142114b3012a2bb9e1f02a035acccc71372`
**Spec:** V1.5 Consolidated Revision 2
**Environment:** development

## Contents

| File | Description |
| --- | --- |
| `manifest.json` | Deployment identity — commit + build/deploy time + registry stats |
| `registry.json` | 29 canonical workflows + 25 OD + 6 RPT + 2 SYS + 9 layouts + aliases |
| `status_model.json` | V1.5 request lifecycle + document lifecycle + step types |
| `acceptance_matrix.md` | RW-01..RW-18 + DOC-01..DOC-20 coverage report |
| `feature_flags.json` | Feature flag effective state per company (dual-read tracking) |
| `test_results.txt` | Full pytest output (exit code 0) |

## Registry counts

- Canonical workflows: 29
- Canonical documents: 25
- Reports: 6
- System records: 2
- Layouts: 9
- Legacy request aliases: 50
- Legacy template aliases: 84
- Migration version: `v1.5-consolidated-rev-2`

## Verification steps for reviewer

1. Compare `manifest.json` commit hash against the deployed backend
   (`GET https://<host>/api/manifest`).
2. Confirm `registry.summary` counts match V1.5 spec §9-12
   (9/25/6/2/50/84).
3. Review `acceptance_matrix.md` — every RW/DOC row must map to either a
   named test or an existing unit test suite.
4. `test_results.txt` must show `passed` on all entries and exit code 0.
5. `feature_flags.json` documents which companies are on canonical vs
   legacy display — expected: all default (off) until management
   authorizes rollout.
