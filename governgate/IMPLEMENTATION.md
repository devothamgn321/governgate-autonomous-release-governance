# GovernGate controller implementation

The current architecture is documented in [ARCHITECTURE.md](ARCHITECTURE.md), including system context, pipeline sequence, four-run matrix, credential boundary, source/evidence lifecycle and completion states.

This directory is the GitLab GovernGate project snapshot. In the public monorepo, see the [complete operator runbook](../IMPLEMENTATION.md), [source revisions](../SOURCE_REVISIONS.md) and [dated live verification](../LIVE_VERIFICATION_2026-10-21.md). For standalone GitLab use, the public [operator runbook](https://github.com/devothamgn321/governgate-autonomous-release-governance/blob/main/IMPLEMENTATION.md) provides configuration and recovery steps.

## Current execution path

`controller.py` validates protected context and the upstream SDK pipeline relationship, verifies source identity, executes both pinned consumers against SDK baseline and candidate, rechecks refs and writes fail-closed evidence. `manual_review.py` validates all-pass evidence in a blocking credential-free job; its final mode runs with the protected read-only API credential and rechecks all current refs. `.gitlab-ci.yml` orders test → verify → review → finalize.

The live gate uses the fixed Billing/Notification allowlist and `controller.verdict`; generic discovery, legacy policy, remediation and optional AI modules are separate prototype capabilities. They do not determine live approval. Nebius remains disabled.

## Local validation

```sh
python -m pip install '.[test]' pyyaml
pytest -q
```

The verified controller suite passed 109 tests; the complete monorepo passed 128. These tests require no API credential. Docker sandbox smoke and API-backed pipelines are separate checks. The October 21 compatible pipeline 2972749377 passed through final freshness; breaking pipeline 2972749891 blocked a Billing candidate regression after a recorded API-timeout retry.

Candidate-controlled JUnit is not independently attested; human review remains required. Ledger SHA-256 is integrity checking, not a signature. Final freshness is point-in-time, not an atomic merge guarantee. See the architecture's limitations table before claiming broader support.
