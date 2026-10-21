# GovernGate

GovernGate checks whether a proposed change to core-auth-sdk breaks its consumers. The trusted controller compares Billing and Notification at pinned commits against the SDK target-branch baseline and exact merge-request candidate. GitLab Duo provides advisory impact context; deterministic policy and execution evidence control the gate.

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for the architecture, trust boundaries, evidence model, runbook, and verified results.

## Verified live runs — October 19, 2026

[GovernGate MR !5](https://gitlab.com/governgate2/governgate/-/merge_requests/5) is merged. The blocking manual evidence-review stage is deployed on main at commit `6f543ed7264c8fe5419de9e6e623a8ce18661bad`.

- **Passing case, SDK MR !6:** [SDK pipeline 2965797284](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2965797284) and [controller pipeline 2965822563](https://gitlab.com/governgate2/governgate/-/pipelines/2965822563) passed. The pinned consumer checks passed and [manual evidence-review job 17303673714](https://gitlab.com/governgate2/governgate/-/jobs/17303673714) passed. A successful manual job records the review action; it is not independent proof of test-report authorship.
- **Blocked case, SDK MR !1:** [SDK pipeline 2965797494](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2965797494) was blocked by [controller pipeline 2965800387](https://gitlab.com/governgate2/governgate/-/pipelines/2965800387). [Controller job 17303672652](https://gitlab.com/governgate2/governgate/-/jobs/17303672652) reported Billing baseline PASS and candidate FAIL; Notification passed both versions.

The earlier controller run 2961370304 predates the manual-review stage and failed closed. It is historical evidence, not the current deployment status.

## Intended use and current limits

GovernGate is a working prototype for platform teams, service owners, and engineering leaders coordinating shared SDK changes. The demonstrated workflow compares one SDK against Billing and Notification. Broader repository onboarding and enterprise deployment need separate validation; no customer savings or production incident reduction have been measured.

This operational repository is private. External readers need project access. The public GitHub monorepo contains source, tests, setup documentation, and a captured-evidence demo; that demo does not execute live controller runs. Candidate code can forge its own test reports, so passing results require review and independent result attestation remains future hardening.

## Security boundaries

- The existing six-job SDK security pipeline and working Duo flow are preserved.
- Only the protected GovernGate controller uses the read-only GitLab API credential scoped to governgate-controller. The SDK bridge and manual-review job receive no controller credential.
- The controller verifies SDK and consumer commit identities, paginates source trees, checks file hashes, and rechecks moving refs. Workers run verified source in isolated containers without network or credentials.
- Missing, inconsistent, failed, or incomplete evidence fails closed. A passing matrix requires human review and never triggers an automatic merge.
- The current ledger SHA-256 digest detects inconsistency but is not an independent signature. A reviewer must inspect the trusted controller artifacts.
- Nebius remains optional and disabled pending API approval.

## Run and test locally

Install dependencies with python -m pip install '.[test]' pyyaml and run pytest -q. Container smoke tests and live controller runs require a Docker-in-Docker runner and protected GitLab configuration; local tests do not need credentials.

## Projects

- [GovernGate controller](https://gitlab.com/governgate2/governgate)
- [core-auth-sdk](https://gitlab.com/governgate2/core-auth-sdk)
- [billing-service](https://gitlab.com/governgate2/billing-service)
- [notification-service](https://gitlab.com/governgate2/notification-service)

The public GitHub monorepo and detailed implementation guide are at [governgate-autonomous-release-governance](https://github.com/devothamgn321/governgate-autonomous-release-governance).