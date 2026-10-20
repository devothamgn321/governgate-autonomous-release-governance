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
- The protected controller successfully resolved SDK MR !2 and ran Billing
  and Notification against both baseline and candidate commits. All four
  consumer runs passed in [GovernGate pipeline 2961370304](https://gitlab.com/governgate2/governgate/-/pipelines/2961370304),
  job [17302552421](https://gitlab.com/governgate2/governgate/-/jobs/17302552421).
- The controller returned `REQUIRES_MANUAL_REVIEW`. That run still failed its
  mirrored pipeline because the deployed CI has no required manual approval
  job yet. The feature branch in this repository adds that job and validates
  the evidence artifact; it is not live until its GitLab MR passes and is
  reviewed/merged.
- The deliberately breaking SDK demonstration MR [!1](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/1)
  remains unmerged. Its SDK jobs passed and the downstream gate blocked it as
  expected; GitLab also reports conflicts and unresolved review threads.
- The reusable SDK bridge MR [!2](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/2)
  remains a draft. Its current downstream run has now completed the consumer
  matrix, but awaits the manual-review workflow fix.
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
