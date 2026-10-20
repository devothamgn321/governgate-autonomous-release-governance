# GovernGate controller

GovernGate checks whether a `core-auth-sdk` merge request breaks its known
consumers. The current demo compares Billing and Notification at pinned
commits against both the SDK target-branch baseline and exact MR candidate.
GitLab Duo supplies advisory impact context; deterministic policy and
execution evidence decide whether the change blocks or needs human review.

The full architecture, source verification, worker isolation, evidence model,
live pipeline results, and operator steps are documented in the monorepo
[`IMPLEMENTATION.md`](../IMPLEMENTATION.md).

## Live status — October 19, 2026

The trusted controller ran in
[pipeline 2961370304](https://gitlab.com/governgate2/governgate/-/pipelines/2961370304),
job [17302552421](https://gitlab.com/governgate2/governgate/-/jobs/17302552421),
from protected controller main commit
`866ed176c4551ecafd6658e0d745a272f9696e82`. It resolved SDK bridge MR
[!2](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/2) and
verified four consumer runs: Billing baseline/candidate PASS and Notification
baseline/candidate PASS. The policy returned `REQUIRES_MANUAL_REVIEW`; the
pipeline failed because the deployed CI does not yet include a required
manual approval job.

The local feature branch adds a credential-free manual evidence-review job.
It checks the ledger digest, pinned SDK and consumer commits, worker image
identity, and complete all-pass matrix. The job has no API-token environment.
It still requires GitLab CI, review, and deployment before the live bridge can
use it. Its SHA-256 digest is not an independent signature; a human must
inspect the controller artifacts. Candidate test output remains untrusted.

## Trust and execution boundaries

- The SDK bridge passes no variables or credentials.
- Only the protected controller uses the read-only GitLab API token scoped to
  `governgate-controller`.
- The controller verifies upstream SDK project, detached MR pipeline, bridge
  job/downstream relationship, live MR head, and immutable commit identities.
- It paginates repository trees, checks file content hashes, and rechecks
  moving refs before finalizing.
- Workers receive verified source only. They run without network, host mounts,
  Docker socket, API token, signing key, or Nebius credential.
- Missing or inconsistent evidence fails closed. A passing candidate needs a
  human review and can never auto-merge.

The controller evaluates exact SDK source trees. It does not claim to test a
separately built wheel. Nebius and automated remediation are outside the
protected controller path and remain disabled.

## Local tests

From the monorepo root, follow the Python setup and run
`./scripts/test-all.sh`. This runs all four projects' suites and requires no
GitLab or Nebius credentials. See the root [README](../README.md) for the
command sequence.
