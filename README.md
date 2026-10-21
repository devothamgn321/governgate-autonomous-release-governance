# GovernGate — release governance across services

This repository brings the four GovernGate hackathon projects together under one root so the complete local test suite can run in one place. The GitLab repositories remain the deployment and merge-gate source of truth; each subdirectory here is a snapshot of its verified GitLab `main` branch.

## Projects

| Directory | Role |
| --- | --- |
| [`governgate/`](governgate/README.md) | Change-impact analysis, isolated downstream verification, evidence ledger, and GitLab controller |
| [`core-auth-sdk/`](core-auth-sdk/README.md) | Shared token issuing and verification library |
| [`billing-service/`](billing-service/README.md) | Billing consumer that verifies SDK-issued tokens |
| [`notification-service/`](notification-service/README.md) | Notification control consumer that issues SDK tokens |

GovernGate reads a candidate SDK merge request, confirms its source SHA, discovers downstream consumers, and compares baseline and candidate SDK artifacts in isolated test containers. GitLab Duo provides advisory impact context. Test evidence and the deterministic policy engine produce the gate result. Candidate-controlled test reports cannot approve a change: a passing candidate still requires human review. Nebius is optional and remains disabled.

## Run the complete test suite

Use Python 3.10 or newer. From this directory:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
./scripts/test-all.sh
```

The script runs the SDK tests, both consumer test suites, and GovernGate's unit, security-boundary, and end-to-end tests. It does not need a GitLab token or Nebius key. The GitLab API-backed controller run requires a short-lived `read_api` token stored only as a protected, masked, environment-scoped variable in the GovernGate project. Never expose it to an SDK merge-request job.

## Architecture and trust boundary

The complete component map, request flow, source-identity rules, worker
isolation, verdict policy, activation runbook, and verified-versus-pending
status are documented in [IMPLEMENTATION.md](IMPLEMENTATION.md).

```text
core-auth-sdk merge request
        │ GitLab bridge: no forwarded variables or credentials
        ▼
protected GovernGate controller environment
        │ resolve and validate GitLab upstream pipeline/job metadata
        │ read-only GitLab API access
        ├── resolve baseline and candidate SDK source identities
        ├── enumerate billing and notification repositories
        ├── fetch and verify immutable source/artifact inputs
        ▼
isolated test workers: baseline × 2 consumers, candidate × 2 consumers
        │ bounded output, no host Docker socket, no API credential
        ▼
evidence ledger → fail-closed policy → mirrored SDK pipeline status
```

The protected controller and final freshness check use the read-only API credential in the existing governgate-controller environment. Workers, SDK jobs and credential-free manual review do not receive it. After manual review, the final job rechecks upstream identity, SDK target and consumer refs. Changed source requires a new matrix and review. Freshness is a point-in-time check, not an atomic merge guarantee.

## GitLab integration status — October 21, 2026

[GovernGate MR !6](https://gitlab.com/governgate2/governgate/-/merge_requests/6) is merged at `84e6779625460fe29406a5a15c9949f4ee1b206c`. This snapshot contains the deployed controller, blocking manual review, post-review freshness check, skipped-test rejection and legacy signature checks. The GitLab SDK bridge is deployed and retains all six security/test/build jobs. Nebius remains optional and disabled pending API approval.

Fresh positive and negative runs, exact SDK/consumer identities, artifacts and any retries are recorded in [the live execution log](LIVE_VERIFICATION_2026-10-21.md). The monorepo local suite passed **128 tests**: SDK 11, Billing 5, Notification 3 and GovernGate 109. Local tests do not replace the GitLab API-backed run.

GitLab remains the operational CI source of truth. GitHub is a public reproducible source snapshot and documentation mirror. Its Actions workflow runs local tests; copying this repo does not reproduce GitLab secrets, protection settings, memberships, runners or Duo configuration automatically. Private GitLab links require access. Candidate reports are not independent attestation, so mandatory human review remains part of the gate. This prototype does not claim general enterprise readiness.

## Source revisions

See [`SOURCE_REVISIONS.md`](SOURCE_REVISIONS.md) for the exact GitLab commit SHA used for each project and links to the original repositories.

## License

Each project retains its own MIT license file. See the individual subdirectories for license text.
