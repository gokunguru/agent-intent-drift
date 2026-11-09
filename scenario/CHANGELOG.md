# Scenario changelog

Every change to the scenario (`change_request.json`, `r1_baseline.json`, agent
prompts) is logged here with its reason, and bumps `version` in
`change_request.json`.

- `0.x`: pilot versions. Can change between pilot runs.
- `1.0`: frozen version for the full campaign, tagged `scenario-v1.0` in git.
  No change after the freeze; every campaign run must reference it.

## 0.1 (2026-11-08)

Initial scenario: temporary SSH access from 10.50.0.0/24 to R1
(MGMT-IN, seq 20) during the 02:00-04:00 maintenance window, then revert.
End-state check at 04:05.
