# GovernGate implementation and execution guide

**Status checked October 19, 2026.** This guide records the design, what has
been demonstrated in GitLab, and what remains under review. The source tree is
a four-project monorepo snapshot; it does not itself change the GitLab project
settings or live repositories.

## Purpose and scope

GovernGate checks downstream compatibility when `core-auth-sdk` changes. The
current demonstration covers `billing-service` and `notification-service`.
For each consumer, the trusted controller runs the same pinned consumer source
once with the SDK target-branch baseline and once with the exact merge-request
candidate. A deterministic policy evaluates the four results and writes an
evidence record and report. GitLab Duo supplies advisory impact analysis in
the existing SDK CI flow; Duo does not decide the gate.

## Architecture

```text
SDK merge request
  ├─ six existing test/security/scan/build jobs
  ├─ GitLab Duo impact analysis (advisory)
  └─ credential-free multi-project bridge (merged SDK MR !2)
       │ no forwarded variables, personal PAT, or provider key
       ▼
Protected GovernGate controller pipeline
  ├─ resolves upstream project, pipeline, bridge job, MR IID, and source SHA
  ├─ reads pinned SDK and consumer source using scoped read-only GitLab API
  ├─ checks full repository trees and each file's content identity
  ├─ builds worker and pins its immutable image ID
  └─ runs Billing baseline/candidate and Notification baseline/candidate
       │ source bytes only; no network or credentials in workers
       ▼
Evidence ledger + deterministic policy + report
  ├─ BLOCKED / INCOMPLETE / SUPERSEDED → pipeline fails closed
  └─ REQUIRES_MANUAL_REVIEW → required reviewer action (merged GovernGate MR !5)
       ▼
Mirrored SDK pipeline result; never an automatic merge
```

The protected controller is the only component that needs GitLab API access.
The user-configured token is read-only and scoped to the `governgate-controller`
environment. The trusted controller validates the upstream SDK project,
detached merge-request pipeline and ref, bridge-job relationship, downstream
pipeline identity, and live merge-request head. It accepts only the expected
SDK project and target branch. Missing or inconsistent identity fails closed.

The controller snapshots the SDK target commit, candidate commit, and each
consumer default-branch commit. Repository-tree pagination must be complete;
downloaded files must match GitLab's content hashes at those immutable refs.
It rechecks moving refs before finalizing. It records source identities and
archive hashes. The tests use the exact SDK source tree; the live design does
not claim a built wheel was installed into consumers.

Workers receive verified source bytes through standard input. They run in
fresh containers with a read-only root, no network, no host mounts or Docker
socket, dropped capabilities, resource/time/output limits, and no API token,
signing key, or Nebius credential. Dependencies are pinned in the worker
image. Results are collected by the trusted controller, not by importing or
installing candidate code on the controller host.

## Verdicts and human review

Failed candidate checks are `BLOCKED`; missing, malformed, stale, or
incomplete evidence is an error; moved source is `SUPERSEDED`. These states
must fail the mirrored pipeline. A passing candidate is
`REQUIRES_MANUAL_REVIEW`, because untrusted candidate code can forge test
reports from inside the test process. It must never be represented as an
automatic approval or merge.

GovernGate MR [!5](https://gitlab.com/governgate2/governgate/-/merge_requests/5)
is merged. Its required manual job follows the trusted controller. Its validator checks
the evidence ledger digest, expected SDK and consumer identities, worker image
identity, and complete all-pass matrix. The job has no protected environment
or API variable, so the controller token is not exposed to the reviewer job.
The reviewer must inspect the evidence artifact and start the manual job;
failures and incomplete evidence never reach that step. The latest MR branch
pipeline, [2965673943](https://gitlab.com/governgate2/governgate/-/pipelines/2965673943),
passed unit tests, sandbox smoke, SAST, and secret detection on its feature
branch. The latest live protected run was
[2965778448](https://gitlab.com/governgate2/governgate/-/pipelines/2965778448)
for the intentionally breaking SDK MR !1. Billing failed on the candidate,
so the controller correctly returned `BLOCKED` and skipped manual review.
The passing-candidate path still needs an end-to-end run on current `main`.

The ledger uses a canonical SHA-256 digest. HMAC signing is optional in the
engine. The manual review job does not receive a signing key, and the current
live controller run has no demonstrated HMAC signature; therefore its digest
checks consistency, not independent authenticity. The human must review the
controller-produced artifacts. A separately trusted result/signature channel
would strengthen this boundary and remains future work.

## Repository responsibilities

| Project | Responsibility |
| --- | --- |
| [GovernGate](https://gitlab.com/governgate2/governgate) | Trusted controller, GitLab identity/source checks, worker image, evidence ledger, policy, reports, and gate CI |
| [core-auth-sdk](https://gitlab.com/governgate2/core-auth-sdk) | Shared token library, existing six-job security pipeline, Duo flow, and merged credential-free bridge |
| [billing-service](https://gitlab.com/governgate2/billing-service) | Downstream authorization consumer |
| [notification-service](https://gitlab.com/governgate2/notification-service) | Control consumer for SDK changes that should not affect verification |

The exact GitLab source revisions captured in this monorepo are listed in
[`SOURCE_REVISIONS.md`](SOURCE_REVISIONS.md). Each service keeps its own normal
CI; cross-service comparison is orchestrated by the protected GovernGate
pipeline.

## Verified GitLab execution

On October 19, 2026, the authenticated GitLab UI ran the intentionally
breaking SDK MR [!1](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/1)
through the merged controller. GovernGate pipeline
[2965778448](https://gitlab.com/governgate2/governgate/-/pipelines/2965778448)
ran on controller main `6f543ed7264c8fe5419de9e6e623a8ce18661bad` and
produced this matrix:

| Consumer | SDK baseline | SDK candidate |
| --- | --- | --- |
| Billing | PASS | FAIL |
| Notification | PASS | PASS |

The verdict was `BLOCKED`, as expected for a breaking change; manual review was
skipped. This verifies live API-backed source resolution, source identity
checks, and the blocking consumer-failure path. The successful all-pass path
through human review still needs end-to-end verification.

SDK MR [!1](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/1)
is the deliberately breaking demonstration change and must remain unmerged.
Its latest observed branch pipeline [2965596249](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2965596249)
passed the SDK jobs; MR pipeline [2965596233](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2965596233)
failed at the downstream gate as designed. GitLab showed unresolved conflicts
and review threads. Do not merge this demonstration MR into SDK `main`.

The SDK bridge MR !2 is merged. SDK main pipeline
[2965757890](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2965757890)
passed all six existing security, test, and build jobs. The existing Duo flow
is preserved. Nebius is optional and disabled pending API approval.

## Current live repository status

| Repository | Current main commit | Latest verified main pipeline |
| --- | --- | --- |
| GovernGate | `6f543ed7264c8fe5419de9e6e623a8ce18661bad` | [2965721808](https://gitlab.com/governgate2/governgate/-/pipelines/2965721808) |
| core-auth-sdk | `bac25944d996acafd3a6fa3e4d2833164f3aaa3f` | [2965757890](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2965757890) |
| billing-service | `1c9cba0941a7e5c964177863defc4174710622d4` | [2961157136](https://gitlab.com/governgate2/billing-service/-/pipelines/2961157136) |
| notification-service | `676cbdc7811cdf0af3490ebd6897b692e6ad7368` | [2961156991](https://gitlab.com/governgate2/notification-service/-/pipelines/2961156991) |

Open GitLab changes at this check: SDK breaking demo MR [!1](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/1),
SDK documentation MR [!5](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/5),
Draft SDK preparation MR [!3](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/3),
Billing documentation MR [!2](https://gitlab.com/governgate2/billing-service/-/merge_requests/2),
and Notification documentation MR [!2](https://gitlab.com/governgate2/notification-service/-/merge_requests/2).
The docs MRs show unresolved review threads; SDK MR !3 has a failed pipeline
and targets a feature branch. GovernGate has no open MRs. Do not merge the
breaking SDK MR !1; confirm whether the preparation MR !3 is still needed.

## Local setup and validation

From the monorepo root, install Python 3.10+ and run:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
./scripts/test-all.sh
```

The suite runs SDK, Billing, Notification, and GovernGate tests, including
security-boundary checks. It needs no GitLab token or Nebius key. A live
controller run additionally requires the protected read-only API variable and
a trusted Docker-in-Docker runner.

## Submission and remaining implementation

The GitHub monorepo is the public source package; GitLab remains the CI source
of truth. The GitLab projects were observed as private in the submission
review, so any Devpost requirement for public GitLab repositories remains a
submission setting to resolve. The project start date/path must be supported
by the actual project history and hackathon rules; do not claim eligibility
without that evidence. Nebius is not required for the core demo and should
remain disabled until approved access exists.

Implementation still to verify:

1. Run a safe SDK MR through current `main`; verify all four consumer runs
   pass, inspect the artifacts, start the blocking manual job, and confirm the
   result is reflected in the SDK pipeline.
2. Resolve the open documentation-MR review threads and update their status
   text. Confirm whether the failed, feature-targeted SDK MR !3 is necessary.
3. Keep the breaking SDK MR !1 unmerged and record its expected `BLOCKED`
   outcome as the negative test.
4. Update the GitHub monorepo snapshots after approved GitLab source changes.
   The checked-in source directories are dated snapshots; see
   `SOURCE_REVISIONS.md`.
5. Treat independent evidence signing as future hardening. The current
   unkeyed digest does not prove authenticity, so a human must inspect the
   trusted-controller artifacts.
6. Resolve hackathon visibility, eligibility, and submission fields as a
   separate submission task; they are not established by these code tests.

The contemporaneous action-by-action record is
[`reports/implementation-checkpoints.md`](reports/implementation-checkpoints.md).
