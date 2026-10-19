# GovernGate Hackathon Monorepo

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

```text
core-auth-sdk merge request
        │ GitLab bridge: MR IID + exact 40-character head SHA
        ▼
protected GovernGate controller environment
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

Only the protected controller needs the GitLab API credential. Its job must use a protected branch, protected environment, restricted runner, and `GOVERNGATE_API_TOKEN` scoped to `governgate-controller`. The SDK bridge forwards typed inputs only and does not forward YAML or pipeline variables. Review the GovernGate README for the full operator sequence and current GitLab activation requirements.

## GitLab integration status

The GovernGate engine and all four README updates are merged into their respective GitLab `main` branches. Their post-merge pipelines passed. The credential-free SDK bridge remains a separate draft merge request while the live controller is activated and verified. The live API-backed four-run comparison and mirrored MR-blocking demonstration are not yet verified. Do not merge the deliberately breaking SDK demonstration MR into `main`.

This monorepo includes the verified GitLab `main` snapshots only; it does not silently import unmerged merge-request changes or claim that the live controller has passed. The root GitHub Actions workflow runs the complete local test suite. GitLab controller settings, protected variables, job-token permissions, and Duo review remain managed in the four original GitLab projects.

## Source revisions

See [`SOURCE_REVISIONS.md`](SOURCE_REVISIONS.md) for the exact GitLab commit SHA used for each project and links to the original repositories.

## License

Each project retains its own MIT license file. See the individual subdirectories for license text.
