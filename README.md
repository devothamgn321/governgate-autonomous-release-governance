# GovernGate: autonomous release governance

GovernGate checks whether a proposed `core-auth-sdk` change breaks its
downstream services. It compares the same pinned Billing and Notification
source revisions against the current SDK baseline and the exact SDK merge
request commit. GitLab Duo supplies advisory impact context; deterministic
policy and execution evidence control the result.

This public GitHub monorepo packages the four related projects and runs their
local test suites together. GitLab remains the live CI and merge-request
control plane. Project responsibilities, the complete architecture, trust
boundaries, setup, and current live evidence are in
[`IMPLEMENTATION.md`](IMPLEMENTATION.md). Exact source snapshot commits are in
[`SOURCE_REVISIONS.md`](SOURCE_REVISIONS.md).

## Current verified state — October 19, 2026

- GitLab has four repositories: [GovernGate](https://gitlab.com/governgate2/governgate),
  [core-auth-sdk](https://gitlab.com/governgate2/core-auth-sdk),
  [billing-service](https://gitlab.com/governgate2/billing-service), and
  [notification-service](https://gitlab.com/governgate2/notification-service).
- The trusted controller and blocking manual evidence-review stage are on
  GovernGate `main`; GovernGate MR [!5](https://gitlab.com/governgate2/governgate/-/merge_requests/5)
  is merged. The credential-free SDK bridge is on SDK `main`; SDK MR
  [!2](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/2) is
  merged.
- The latest live breaking-change run is
  [GovernGate pipeline 2965778448](https://gitlab.com/governgate2/governgate/-/pipelines/2965778448),
  on controller commit `6f543ed7264c8fe5419de9e6e623a8ce18661bad`. Billing
  passed with the baseline SDK and failed with the candidate; Notification
  passed both. GovernGate correctly returned `BLOCKED`; manual review was
  skipped because a consumer failed.
- The six-job SDK security, test, and build pipeline passed on SDK main in
  [pipeline 2965757890](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2965757890).
- The passing-candidate path still needs a fresh run: both consumers must
  pass, a reviewer must inspect the evidence and start the blocking manual
  job, and the SDK pipeline must show the resulting status.
- SDK MR [!1](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/1)
  remains an intentionally breaking, unmerged demo. Its latest pipeline
  [2965776106](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2965776106)
  failed at the downstream gate as designed. It also has conflicts and
  unresolved review threads; do not merge it into SDK `main`.
- Other open changes are SDK docs MR [!5](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/5),
  Draft SDK prep MR [!3](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/3),
  Billing docs MR [!2](https://gitlab.com/governgate2/billing-service/-/merge_requests/2),
  and Notification docs MR [!2](https://gitlab.com/governgate2/notification-service/-/merge_requests/2).
  The docs MRs have unresolved review threads; MR !3 is failed and targets a
  feature branch, so confirm whether it is still needed.
- The existing six-job SDK security pipeline and Duo impact-analysis flow are
  preserved. Nebius remains optional and disabled.

## Run the complete local suite

Use Python 3.10 or newer from this directory:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
./scripts/test-all.sh
```

The suite covers the SDK, both consumer services, and GovernGate unit,
security-boundary, and integration tests. It needs no GitLab or Nebius token.

## Security boundary

The SDK bridge forwards no variables or credentials. Only the protected
GovernGate controller uses the scoped, read-only GitLab API token. Candidate
source runs in isolated workers without network access, host mounts, Docker
socket, API credentials, or signing keys. The controller pins source commits,
checks downloaded content hashes, paginates repository trees, and fails closed
on missing or inconsistent evidence. A candidate can potentially forge its
own test output, so a passing matrix is explicitly held for human review and
never auto-merges. See the implementation guide for details and limitations.

## Project layout

| Directory | Purpose |
| --- | --- |
| [`governgate/`](governgate/README.md) | Analysis, trusted controller, isolated workers, evidence, and CI gate |
| [`core-auth-sdk/`](core-auth-sdk/README.md) | Shared token issue/verification library and SDK CI |
| [`billing-service/`](billing-service/README.md) | Downstream authorization consumer |
| [`notification-service/`](notification-service/README.md) | Control consumer |
