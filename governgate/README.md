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

The trusted controller and credential-free manual evidence-review job are on
GovernGate `main`; MR [!5](https://gitlab.com/governgate2/governgate/-/merge_requests/5)
is merged. The latest protected run is
[pipeline 2965778448](https://gitlab.com/governgate2/governgate/-/pipelines/2965778448)
on commit `6f543ed7264c8fe5419de9e6e623a8ce18661bad`. It resolved the
intentionally breaking SDK MR !1. Billing baseline passed and candidate
failed; Notification baseline and candidate passed. GovernGate returned
`BLOCKED` as designed, so manual review was skipped. The positive path still
needs a safe candidate run where all consumers pass, a human inspects the
evidence, and the manual job is started.

The manual job checks the ledger digest, pinned SDK and consumer commits,
worker image identity, and complete all-pass matrix. It has no API-token
environment. The SHA-256 digest detects changes but is not an independent
signature; candidate test output remains untrusted, so the reviewer must
inspect the controller artifacts.

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
