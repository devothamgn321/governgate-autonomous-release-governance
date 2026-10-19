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

Only the protected controller needs the GitLab API credential. The proposed controller change checks that the upstream pipeline belongs to the SDK project, came from a detached merge-request pipeline, points to the expected MR ref, was started by the `governgate-impact` bridge job, and still matches the live MR head. The bridge forwards no variables or credentials. This handoff is proposed in GovernGate MR !3 and is not in the local `main` snapshot yet. Review the GovernGate README for the current activation requirements.

## GitLab integration status

The GovernGate engine and all four README updates are merged into their respective GitLab `main` branches, and their post-merge pipelines passed. SDK bridge MR [!2](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/2) remains open as a draft. Its SDK test, security, and wheel-build jobs passed, but its bridge job failed after creating downstream pipeline [2961234944](https://gitlab.com/governgate2/governgate/-/pipelines/2961234944). That downstream run failed closed because GovernGate `main` did not yet contain the trusted upstream resolver.

GovernGate MR [!3](https://gitlab.com/governgate2/governgate/-/merge_requests/3) now contains commit `f97389a5d905ab85498df6b6a9282ba030175b46`. It uses GitLab's pipeline-scoped `trigger_jobs` API and checks that the recorded downstream pipeline and project match the running controller. Its pipeline [2961247877](https://gitlab.com/governgate2/governgate/-/pipelines/2961247877) passed. The prior controller failure remains the only live downstream execution; no baseline/candidate consumer comparison or mirrored merge-blocking result has been verified. The MR is not merged, and `GOVERNGATE_API_TOKEN` is not configured. Do not merge the deliberately breaking SDK demonstration MR into `main`.

The protected `governgate-controller` environment allows the project owner and Rohan Mahendra (`bmrohan003`) to deploy. The project has no `GOVERNGATE_API_TOKEN` variable yet. GitLab documents the `CI_UPSTREAM_*` variables from version 18.9, and the `trigger_jobs` endpoint plus a real downstream relationship have been verified in a live API response. A run with the updated controller is still needed to verify the injected values and execute the consumers. Nebius is optional and disabled.

This local monorepo includes the verified GitLab `main` snapshots only; it does not silently import unmerged merge-request changes or claim that the live controller has passed. The root GitHub Actions workflow runs the complete local test suite. GitLab controller settings, protected variables, job-token permissions, and Duo review remain managed in the four original GitLab projects. The four current GitLab projects are private, and this monorepo has not been published; the Devpost public-repository requirement is not yet met.

## Source revisions

See [`SOURCE_REVISIONS.md`](SOURCE_REVISIONS.md) for the exact GitLab commit SHA used for each project and links to the original repositories.

## License

Each project retains its own MIT license file. See the individual subdirectories for license text.
