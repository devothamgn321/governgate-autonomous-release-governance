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
  └─ credential-free multi-project bridge (proposed MR !2)
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
  └─ REQUIRES_MANUAL_REVIEW → required reviewer action (implementation in review)
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

The live October 19 controller run completed all four pinned consumer runs as
`PASS`, recorded `REQUIRES_MANUAL_REVIEW`, and then failed the downstream
pipeline because the deployed CI had no explicit manual review job. The
feature branch adds a required manual job after the trusted controller. It
validates the evidence ledger's digest, expected SDK and consumer identities,
worker image identity, and complete all-pass matrix. It has no protected
environment or API variable, so the controller token is not exposed to the
review job. The reviewer must inspect the evidence artifact and start the
manual job; failures and incomplete evidence never reach that step. This
workflow change still needs a GitLab feature-branch pipeline and review before
it is live.

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
| [core-auth-sdk](https://gitlab.com/governgate2/core-auth-sdk) | Shared token library, existing six-job security pipeline, Duo flow, and proposed credential-free bridge |
| [billing-service](https://gitlab.com/governgate2/billing-service) | Downstream authorization consumer |
| [notification-service](https://gitlab.com/governgate2/notification-service) | Control consumer for SDK changes that should not affect verification |

The exact GitLab source revisions captured in this monorepo are listed in
[`SOURCE_REVISIONS.md`](SOURCE_REVISIONS.md). Each service keeps its own normal
CI; cross-service comparison is orchestrated by the protected GovernGate
pipeline.

## Verified GitLab execution

On October 19, 2026, the authenticated GitLab UI retried the downstream
pipeline for SDK bridge MR [!2](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/2),
source commit `9ef8ca0b3b3078e99e1249b9fe3f332255e4f303`. GovernGate pipeline
[2961370304](https://gitlab.com/governgate2/governgate/-/pipelines/2961370304)
ran on controller main `866ed176c4551ecafd6658e0d745a272f9696e82`; protected
job [17302552421](https://gitlab.com/governgate2/governgate/-/jobs/17302552421)
resolved SDK MR !2 and produced this matrix:

| Consumer | SDK baseline | SDK candidate |
| --- | --- | --- |
| Billing | PASS | PASS |
| Notification | PASS | PASS |

The verdict was `REQUIRES_MANUAL_REVIEW`. That job exited nonzero, so the
downstream pipeline failed and the SDK bridge remains blocked. This verifies
the live API-backed source resolution and four-run consumer matrix; it does
not demonstrate the proposed manual job because that code has not yet been
deployed to GitLab.

SDK MR [!1](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/1)
is the deliberately breaking demonstration change and must remain unmerged.
Its latest observed branch pipeline [2965596249](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2965596249)
passed the SDK jobs; MR pipeline [2965596233](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2965596233)
failed at the downstream gate as designed. GitLab showed unresolved conflicts
and review threads. Do not merge this demonstration MR into SDK `main`.

The SDK bridge MR !2 is still a draft. Its description should be refreshed
after the manual-review change passes its own CI. GovernGate resolver MR !3
was merged at `866ed176c4551ecafd6658e0d745a272f9696e82`; its pipeline
[2961361082](https://gitlab.com/governgate2/governgate/-/pipelines/2961361082)
passed. The existing six SDK jobs and Duo flow remain intact. Nebius is
optional and disabled pending API approval.

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

Implementation still requiring review/deployment:

1. Publish the manual evidence-review gate on a GovernGate feature branch and
   run its GitLab MR pipeline.
2. Review and merge the GovernGate workflow change, then rerun SDK bridge MR
   !2 and verify the manual job is blocking, has no credentials, and succeeds
   only after a human reviews the passing evidence.
3. Refresh SDK bridge MR !2's description and verify its mirrored pipeline
   reports the manual-review state accurately.
4. Keep the breaking SDK MR !1 unmerged. Demonstrate its expected blocked
   result in the submission evidence.
5. Decide the GitLab project visibility needed by Devpost and verify the
   hackathon's start-date path from project history.
6. Add independent evidence signing or a trusted test-result channel only if
   time permits; do not imply the current unkeyed digest proves authenticity.

The contemporaneous action-by-action record is
[`reports/implementation-checkpoints.md`](reports/implementation-checkpoints.md).
