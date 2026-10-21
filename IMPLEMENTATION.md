# Current monorepo checkpoint — October 21, 2026

GovernGate MR !6 is merged at 84e6779625460fe29406a5a15c9949f4ee1b206c. The positive SDK pipeline and final trusted freshness job passed today; the breaking SDK pipeline was blocked by a verified Billing regression after one API-timeout retry. See [the full execution log](LIVE_VERIFICATION_2026-10-21.md) for exact links and limits.

The current source snapshot is recorded in [SOURCE_REVISIONS.md](SOURCE_REVISIONS.md). Run `./scripts/test-all.sh` from this monorepo after installing requirements-dev.txt; the complete suite passed 128 tests. The guide below retains dated historical checkpoints from the operational project; this paragraph and the execution log supersede statements that MR !6 is not merged or that its final job has not run.

# GovernGate monorepo implementation guide

**Status: October 20, 2026.** MR !5 is merged into main at `6f543ed7264c8fe5419de9e6e623a8ce18661bad`. The required manual-review stage is deployed. The verified runs below supersede earlier pre-merge status notes.

## Purpose and scope

GovernGate checks whether a change to core-auth-sdk breaks its known consumers. The demonstration covers billing-service, the affected consumer, and notification-service, the control consumer. For each service, the trusted controller runs pinned consumer source against both the SDK target-branch baseline and the exact merge-request candidate. GitLab Duo provides advisory impact context; deterministic policy and execution evidence control the gate.

## Architecture

1. A core-auth-sdk merge request runs its existing six-job security pipeline. GitLab Duo provides impact context as an advisory signal.
2. The credential-free multi-project bridge in [core-auth-sdk MR !2](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/2) starts the downstream GovernGate pipeline and mirrors its result. The bridge must not pass a personal PAT, controller API token, Nebius key, signing key, or arbitrary pipeline variables.
3. The protected GovernGate controller resolves the upstream SDK project, pipeline, trigger job, merge request IID, and exact candidate commit. It requires the expected SDK project and a detached merge-request pipeline. Missing or mismatched identity fails closed.
4. The controller snapshots the SDK baseline and candidate and the selected branch commit for each consumer. It paginates the complete repository trees, downloads files at immutable commit SHAs, verifies GitLab content hashes and archive digests, and rechecks moving refs before finalizing. Changed refs produce SUPERSEDED.
5. The reviewed controller pipeline builds the worker and pins the immutable image ID. It sends only verified source bytes to fresh worker containers. Workers have no network, API credentials, signing key, host mounts, or Docker socket. They use a read-only root, unprivileged user, resource/time/output limits, and are removed after execution.
6. Each consumer is tested twice at the same pinned source commit: once with the SDK baseline and once with the candidate. For the current demo, that is Billing baseline/candidate and Notification baseline/candidate.
7. The controller checks expected test results and records SDK/consumer identities, source digests, worker image identity, and outcomes in the evidence ledger. Missing tests, incomplete pagination, failed setup, timeout, output overflow, unexpected results, identity mismatch, or source movement fails closed.
8. A candidate failure is BLOCKED. A failed baseline or incomplete run cannot count as a pass. Four passing runs produce REQUIRES_MANUAL_REVIEW, because candidate-controlled test code can forge its own reports. A pass never means automatic approval or merge.
9. MR !5 adds the required manual-evidence-review job. It consumes the trusted-controller artifact, validates the ledger digest, SDK project/MR identity, pinned SDK commits and archive hashes, worker image identity, exact consumer set, and all four PASS outcomes. The job is blocking with allow_failure false, declares no environment, and is restricted to protected main pipelines triggered by the bridge. A person must inspect the trusted artifact and start the job.

## Trust and credentials

Only the protected controller and post-review freshness check use the read-only GitLab API credential scoped to the governgate-controller environment. The bridge, SDK jobs, untrusted merge-request jobs, workers, and manual-review job must not receive it. Masking alone is not a trust boundary. Keep Nebius disabled until API access is approved and provisioned.

The ledger's SHA-256 digest is unkeyed in the current live setup. It detects changes or inconsistency but does not independently prove authenticity. HMAC is an optional engine capability, but the reviewer job has no signing key and no signed live run has been demonstrated. The reviewer must inspect trusted controller artifacts. An independently trusted test-result or signing channel remains future hardening.

## Verified live execution

[GovernGate MR !5](https://gitlab.com/governgate2/governgate/-/merge_requests/5) is merged. The blocking manual evidence-review stage is deployed on main at commit `6f543ed7264c8fe5419de9e6e623a8ce18661bad`.

- **Passing case, SDK MR !6:** [SDK pipeline 2965797284](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2965797284) and [controller pipeline 2965822563](https://gitlab.com/governgate2/governgate/-/pipelines/2965822563) passed. The pinned consumer checks passed and [manual evidence-review job 17303673714](https://gitlab.com/governgate2/governgate/-/jobs/17303673714) passed. A successful manual job records the review action; it is not independent proof of test-report authorship.
- **Blocked case, SDK MR !1:** [SDK pipeline 2965797494](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2965797494) was blocked by [controller pipeline 2965800387](https://gitlab.com/governgate2/governgate/-/pipelines/2965800387). [Controller job 17303672652](https://gitlab.com/governgate2/governgate/-/jobs/17303672652) reported Billing baseline PASS and candidate FAIL; Notification passed both versions.

The earlier controller run 2961370304 predates the manual-review stage and failed closed. It is historical evidence, not the current deployment status.

## Intended use and current limits

GovernGate is a working prototype for platform teams, service owners, and engineering leaders coordinating shared SDK changes. The demonstrated workflow compares one SDK against Billing and Notification. Broader repository onboarding and enterprise deployment need separate validation; no customer savings or production incident reduction have been measured.

This operational repository is private. External readers need project access. The public GitHub monorepo contains source, tests, setup documentation, and a captured-evidence demo; that demo does not execute live controller runs. Candidate code can forge its own test reports, so passing results require review and independent result attestation remains future hardening.

## Repository responsibilities

- [governgate](https://gitlab.com/governgate2/governgate): trusted controller, GitLab identity/source validation, policy, evidence, worker image, and CI gate.
- [core-auth-sdk](https://gitlab.com/governgate2/core-auth-sdk): shared token library, preserved six-job security pipeline and Duo flow, and deployed credential-free bridge.
- [billing-service](https://gitlab.com/governgate2/billing-service): affected downstream consumer.
- [notification-service](https://gitlab.com/governgate2/notification-service): control downstream consumer.

The public GitHub monorepo is [governgate-autonomous-release-governance](https://github.com/devothamgn321/governgate-autonomous-release-governance). It contains all four projects, integrated tests, source revisions, and a companion implementation guide.

## Local verification

From the GovernGate repository, install the test dependencies and run the unit suite:

    python -m pip install '.[test]' pyyaml
    pytest -q

The live controller also needs the protected GitLab variable and a trusted Docker-in-Docker runner. Unit tests require no GitLab or Nebius credentials. The public monorepo integrated suite previously passed 104 tests: SDK 11, Billing 5, Notification 3, GovernGate 85.

## Remaining checkpoints

1. Review the MR !6 source-review fixes and run new positive/negative pipelines after deployment. The source review does not audit runner host isolation or all live permission settings.
2. Reproduce the positive and negative pipeline outcomes after relevant code changes; retain pinned identities and trusted-controller artifacts.
3. Strengthen independent test-result attestation. Candidate-controlled reports and the unkeyed ledger digest are documented limitations.
4. Validate onboarding of additional SDKs and consumers before claiming general enterprise readiness. No customer savings or incident-reduction metrics have been measured.
5. Keep Nebius optional and disabled pending approved access and a verified live call.
6. Verify public mirror freshness separately from this private operational repository.

The detailed cross-repository source revisions and local run instructions are in the public GitHub monorepo. This guide records the GovernGate architecture and current GitLab execution status.

## October 20 review-fix checkpoint — MR !6 (not merged)

The branch adds a final trusted-freshness-check stage after the blocking manual-evidence-review job. It uses the existing protected governgate-controller environment and fixed GitLab API endpoint. Before authenticating it requires the expected controller project, protected main and multi-project pipeline source. It resolves the immutable upstream bridge/downstream relationship again, binds the evidence MR/candidate to that request, requires an open same-project SDK MR targeting main, and compares the current SDK target and both consumer main commits with the recorded evidence. A mismatch or API failure blocks completion. Rerun the SDK pipeline to rebuild the matrix and repeat manual review; retrying the freshness job alone cannot validate changed source. No candidate code executes in this final job, and the manual job remains credential-free.

This is a point-in-time check at pipeline completion, not an atomic merge transaction or independent test-result attestation. Re-run verification when relevant source changes after completion. Branch protection and merge policy remain necessary.

Other fixes: any skipped required worker test is INCONCLUSIVE; the legacy semantic analyzer detects reordered parameters, parameter-kind changes, variadic removal and changed defaults conservatively as breaking SIGNATURE_CHANGED when not already classified. The disabled legacy CLI is not re-enabled.

Validation: 109 tests passed locally on Python 3.12. New regression coverage includes moved SDK target/consumer refs, closed MR, unrelated evidence, API failure, untrusted context, final-stage dependencies and signature changes. MR pipelines validate the branch; the protected post-review job requires deployment to main and a fresh bridge-triggered run for live verification. No new live cross-service run has been claimed. Nebius remains optional. See MR !6 for exact commit and pipeline evidence.
