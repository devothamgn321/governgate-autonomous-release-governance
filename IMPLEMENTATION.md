# GovernGate implementation guide

**Status reviewed: October 18, 2026.** This guide distinguishes implemented and tested behavior from GitLab integration steps that are still pending. The runnable monorepo is a snapshot of the four GitLab `main` branches listed in [SOURCE_REVISIONS.md](SOURCE_REVISIONS.md); it does not include the unmerged SDK bridge or GovernGate controller MR changes.

## What the system does

GovernGate checks the downstream effect of a proposed `core-auth-sdk` change. It holds each consumer at an identified commit, executes that consumer against both the current SDK baseline and the exact SDK merge-request candidate, and applies a deterministic policy to the observed outcomes. The current demo has two consumers: `billing-service`, which calls `verify_token`, and `notification-service`, which calls `issue_token` and acts as a control for verifier-only changes.

GitLab Duo supplies advisory impact analysis in the existing SDK workflow. It helps explain why a consumer may be affected; it does not decide the gate. GovernGate's policy and verified execution evidence determine whether the candidate is blocked or needs human review.

## Components and responsibilities

| Component | Implementation | Responsibility |
| --- | --- | --- |
| Semantic analysis | `governgate/governgate/semantic_analyzer.py` | Identifies API or semantic changes for impact context. |
| Consumer discovery | `governgate/governgate/consumer_discovery.py` | Finds registered downstream projects and their default refs. |
| GitLab client | `governgate/governgate/gitlab_client.py` | Reads project, MR, pipeline, tree, and repository-file data. |
| Trusted controller | `governgate/governgate/controller.py` | Resolves upstream pipeline identity, pins source revisions, coordinates workers, rechecks for source movement, and emits the result. |
| Differential verifier | `governgate/governgate/differential_verifier.py` | Compares each consumer's baseline and candidate outcomes. |
| Worker | `governgate/ci/worker.py`, `worker_results.py`, `Dockerfile.worker` | Tests verified source in an isolated container and returns bounded test evidence. |
| Evidence ledger | `governgate/governgate/evidence_ledger.py` | Records commit identities, source hashes, worker image identity, and outcomes; supports optional HMAC integrity checks. |
| Policy and reporting | `governgate/governgate/policy_engine.py`, `impact_reporter.py` | Produces deterministic fail-closed verdicts and a human-readable report. |
| Optional analysis modules | `root_cause.py`, `remediation.py`, `nemotron_client.py` | Provide supporting analysis and optional integrations; they are not required by the protected controller path. |
| SDK bridge template | `governgate/templates/governgate-check.gitlab-ci.yml` | Shows the downstream integration pattern. The live SDK bridge remains under review in SDK MR !2. |

The four repository responsibilities and pinned GitLab source revisions are listed in the root [README](README.md) and [source revision record](SOURCE_REVISIONS.md).

## End-to-end flow

```mermaid
sequenceDiagram
    participant Dev as SDK merge request
    participant CI as Existing SDK CI and Duo flow
    participant Bridge as Credential-free bridge
    participant Controller as Protected GovernGate controller
    participant GitLab as GitLab read API
    participant Workers as Isolated test workers
    participant Policy as Evidence and policy

    Dev->>CI: Open or update detached merge-request pipeline
    CI->>CI: Run six existing SDK test, security, scan, and build jobs
    CI->>CI: Duo adds advisory impact context
    CI->>Bridge: Start bridge after existing checks
    Bridge->>Controller: Trigger downstream pipeline; forward no variables or secrets
    Controller->>GitLab: Resolve upstream project, pipeline, and bridge-job identity
    GitLab-->>Controller: Verified SDK MR IID, ref, pipeline SHA, and bridge relationship
    Controller->>GitLab: Read target SDK SHA, candidate SDK SHA, and consumer tree/file data
    GitLab-->>Controller: Pinned source identities and content
    Controller->>Workers: Run baseline and candidate for each pinned consumer
    Workers-->>Controller: Test outcomes and bounded output
    Controller->>GitLab: Recheck MR head and pinned baseline refs
    Controller->>Policy: Record evidence and evaluate deterministic verdict
    Policy-->>Controller: BLOCKED, SUPERSEDED, INCOMPLETE, or REQUIRES_MANUAL_REVIEW
    Controller-->>Bridge: Return pipeline result
    Bridge-->>Dev: Mirror downstream status into SDK pipeline
```

## Identity and source verification

The bridge is designed to carry no GitLab API token, Nebius key, or arbitrary variables. The controller determines its caller from GitLab's upstream project, pipeline, and bridge-job metadata. It checks that the caller is the expected SDK project, that the source is a detached merge-request pipeline targeting `main`, that the job is the expected `governgate-impact` bridge, and that the recorded downstream controller project and pipeline match the current run. The MR IID comes from the detached MR ref. The pipeline SHA must match the live MR head. Missing, stale, or inconsistent identity fails closed.

The controller captures the target SDK commit, exact candidate SDK commit, and current `main` commit of each consumer. Repository-tree reads are paginated so a partial tree cannot silently omit source. Each file is checked against GitLab's content metadata at its pinned commit. Before finalizing, the controller rechecks the live MR head and consumer baseline refs; movement marks the run superseded. The worker receives verified source bytes, not a mutable branch name.

This implementation tests exact SDK source in the worker with the consumer. It does not claim that a separately built SDK wheel was installed into each consumer. A build artifact identity is recorded in the SDK CI flow, but the current live controller comparison uses pinned source snapshots.

## Isolation and secrets

Only the protected controller needs read-only GitLab API access. The planned `GOVERNGATE_API_TOKEN` is a short-lived `read_api` group token held as a protected, masked variable in the GovernGate project and scoped to the protected `governgate-controller` environment. It is not configured yet. No personal PAT is passed to an untrusted merge-request pipeline. Nebius is optional, has no approved key yet, and remains disabled.

Workers receive only source inputs and test configuration. They have no API token, signing key, host mounts, Docker socket, or network access. The worker image is built in the trusted pipeline and resolved to an immutable local image ID. Workers run with a read-only root filesystem, dropped capabilities, resource and time limits, and bounded logs/output; containers are removed after completion or failure. Dependencies are fixed by the worker image so consumer requirements cannot replace the candidate SDK under test.

The controller is restricted to protected `main` controller pipelines. Protected-environment deploy access was configured for the owner and teammate `bmrohan003`; repository branch protections, review approvals, job-token allowlists, and protected-variable settings remain part of the activation checklist. Protecting the environment alone does not make the bridge an organization-wide policy, so review and branch protection remain necessary.

## Evidence and verdict rules

The evidence ledger records the MR IID, target and candidate SDK commits, each consumer commit, downloaded source hashes, worker image ID, and individual outcomes. HMAC signing is optional and used only when its key is configured. Reports do not include secret values.

The system rejects missing consumers, incomplete pagination, content/hash mismatches, identity mismatches, missing or unexpected tests, zero executed tests, setup failures, timeouts, output overflow, source movement, malformed reports, and unknown outcomes. A candidate failure is `BLOCKED`. A failed baseline or incomplete run cannot become a pass. If all candidate tests pass, the outcome is `REQUIRES_MANUAL_REVIEW`: candidate code runs in the same process and UID as pytest and can forge its own JUnit output. A passing test report is therefore not an independent trusted approval signal.

## Repository and CI integration

`core-auth-sdk` retains its verified six-job security/test/build pipeline and existing Duo flow. The optional bridge belongs after those checks and should mirror the downstream controller result into the SDK pipeline. The bridge must not change the six existing jobs or forward credentials. Billing and notification retain their normal integration CI; the protected controller performs the cross-service baseline/candidate comparison using pinned source.

The current feature MRs and GitLab pipeline evidence are recorded in the root README. As of this review, GovernGate MR !3's resolver fix is on its feature branch and its pipeline passed, but it is not merged. The SDK bridge MR !2 remains open/draft. One older live downstream run failed closed before executing the consumer comparisons. No successful API-backed end-to-end gate is claimed.

## Local verification

From the monorepo root, run the complete suite:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
./scripts/test-all.sh
```

The October 18, 2026 local run passed 88 tests: 11 SDK, 5 billing, 3 notification, and 69 GovernGate tests. This confirms the local source snapshot and deterministic fixtures, not the pending live GitLab controller run. The GitLab worker smoke additionally exercises isolated baseline/candidate fixtures, early exits, forged JUnit, and output flooding.

## Activation checklist

1. Review and merge the GovernGate controller resolver MR after its review checks pass.
2. Review the SDK bridge MR while preserving the six-job pipeline and Duo flow; do not merge the intentionally breaking demo change into `main`.
3. Add a short-lived `read_api` token only as protected, masked `GOVERNGATE_API_TOKEN` scoped to `governgate-controller`; never place it in the SDK project or at broad group scope.
4. Confirm controller environment access, protected branch and variable settings, restricted job-token allowlist, and a dedicated Docker-in-Docker runner with TLS.
5. Trigger the bridge from a real detached SDK MR pipeline. Verify the injected upstream identity, exact SDK and consumer SHAs, four consumer runs, evidence artifact, and mirrored SDK status.
6. Demonstrate the expected fixture case: billing baseline passes and candidate fails; notification baseline and candidate pass. Confirm a failing mirrored result prevents merge. Keep a passing candidate at human review.
7. Record the real pipeline URL and evidence in the submission. Keep Nebius disabled unless API access is approved and the integration is separately tested.

## Scope and known limits

The live controller has not completed a verified consumer comparison, so GovernGate is not yet a proven automatic cross-service merge gate. Automated remediation and Nebius are outside the protected controller's active path. There is no independent trusted test-result channel yet. The monorepo is a reproducible source snapshot, not a replacement for each GitLab repository's CI settings or branch protections. Hackathon path eligibility still depends on the actual project creation date; use Path A only if that date is verified. If the project predates the Path A window, Path B requires the separately specified public deployment.
