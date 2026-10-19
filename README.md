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

Only the protected controller needs the GitLab API credential. GovernGate MR !3 adds checks that the upstream pipeline belongs to the SDK project, came from a detached merge-request pipeline, points to the expected MR ref, was started by the `governgate-impact` bridge job, and still matches the live MR head. Its pipeline passed, but the change is not merged and is absent from this GitLab `main` snapshot. Review the GovernGate README and implementation guide for the current activation requirements.

## GitLab integration status

The GovernGate engine and all four README updates are merged into their respective GitLab `main` branches, and their post-merge pipelines passed. SDK bridge MR [!2](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/2) remains open as a draft. Its SDK test, security, and wheel-build jobs passed, but its bridge job failed after creating downstream pipeline [2961234944](https://gitlab.com/governgate2/governgate/-/pipelines/2961234944). That downstream run failed closed because GovernGate `main` did not yet contain the trusted upstream resolver.

GovernGate MR [!3](https://gitlab.com/governgate2/governgate/-/merge_requests/3) now contains commit `f97389a5d905ab85498df6b6a9282ba030175b46`. It uses GitLab's pipeline-scoped `trigger_jobs` API and checks that the recorded downstream pipeline and project match the running controller. Its pipeline [2961247877](https://gitlab.com/governgate2/governgate/-/pipelines/2961247877) passed. The prior controller failure remains the only live downstream execution; no baseline/candidate consumer comparison or mirrored merge-blocking result has been verified. The MR is not merged, and `GOVERNGATE_API_TOKEN` is not configured. Do not merge the deliberately breaking SDK demonstration MR into `main`.

The protected `governgate-controller` environment allows the project owner and Rohan Mahendra (`bmrohan003`) to deploy. The project has no `GOVERNGATE_API_TOKEN` variable yet. GitLab documents the `CI_UPSTREAM_*` variables from version 18.9, and the `trigger_jobs` endpoint plus a real downstream relationship have been verified in a live API response. A run with the updated controller is still needed to verify the injected values and execute the consumers. Nebius is optional and disabled.

The architecture and implementation documentation is merged in GovernGate MR [!2](https://gitlab.com/governgate2/governgate/-/merge_requests/2), SDK MR [!4](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/4), billing MR [!1](https://gitlab.com/governgate2/billing-service/-/merge_requests/1), and notification MR [!1](https://gitlab.com/governgate2/notification-service/-/merge_requests/1). Each post-merge pipeline passed: GovernGate `2961155788`, SDK `2961155999`, billing `2961157136`, and notification `2961156991`.

### Staged controller integration update — October 18, 2026

GovernGate MR [!3](https://gitlab.com/governgate2/governgate/-/merge_requests/3) adds trusted upstream identity resolution for the credential-free SDK bridge. At commit `f97389a5d905ab85498df6b6a9282ba030175b46`, its pipeline [2961247877](https://gitlab.com/governgate2/governgate/-/pipelines/2961247877) passed. The controller checks the upstream SDK project and detached merge-request pipeline, validates the bridge job through GitLab's pipeline-scoped trigger-jobs API, binds its downstream pipeline to the current controller run, and confirms that the pipeline SHA still matches the live MR head. The bridge forwards no variables or credentials.

SDK bridge MR [!2](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/2) remains open. Its latest observed pipeline [2961227944](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2961227944) passed the six existing SDK jobs, then its bridge failed because `main` did not yet contain the resolver. The MR !3 resolver has passed CI but is not merged, so the live API-backed comparison is still pending. After review and merge of the controller change, configure the protected read-only API token and rerun the SDK bridge pipeline.

The GitHub `main` branch contains the verified GitLab `main` snapshots listed in [SOURCE_REVISIONS.md](SOURCE_REVISIONS.md). Feature branch `feature/trusted-upstream-controller` adds the pending controller and bridge changes for review; neither that branch nor the GitLab MRs claim that a live cross-service run has passed. The root GitHub Actions workflow runs the complete local test suite. GitLab controller settings, protected variables, job-token permissions, and Duo review remain managed in the four original GitLab projects. The four GitLab source projects are private, so Devpost's GitLab public-repository requirement remains unmet.

## Source revisions

See [`SOURCE_REVISIONS.md`](SOURCE_REVISIONS.md) for the exact GitLab commit SHA used for each project and links to the original repositories.

## License

Each project retains its own MIT license file. See the individual subdirectories for license text.
