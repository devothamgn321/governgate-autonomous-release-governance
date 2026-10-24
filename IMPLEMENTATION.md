# GovernGate implementation and operator runbook

Updated October 21, 2026. [Architecture and diagrams](ARCHITECTURE.md) describes the current code and security boundaries. [Source revisions](SOURCE_REVISIONS.md) pins all four GitLab snapshots. [Live verification](LIVE_VERIFICATION_2026-10-21.md) records exact runs and retries.

## Current checkpoint

GovernGate MR !6 is merged at `84e6779625460fe29406a5a15c9949f4ee1b206c`. It deploys the trusted controller, blocking human evidence review, final freshness check, skipped-test rejection and regression coverage. The SDK bridge is deployed. GitHub synchronization PR #3 merged as `cc4f876f6f2df6dc7688ad51e248a7d40486dc09`; all 104 tracked files matched the tested snapshot and its [main workflow passed](https://github.com/devothamgn321/governgate-autonomous-release-governance/actions/runs/39681631899). This guide replaces older pending-activation instructions; historical evidence remains in the dated execution log.

## Repository map

| Directory | Purpose |
| --- | --- |
| `governgate/` | Protected controller, worker, evidence/review, legacy engine modules and tests |
| `core-auth-sdk/` | Shared JWT SDK, six existing required jobs, multi-project bridge |
| `billing-service/` | Affected consumer: verifies SDK tokens |
| `notification-service/` | Control consumer: issues SDK tokens |
| `scripts/test-all.sh` | Runs all four local Python test suites |
| `.github/workflows/tests.yml` | Public mirror test workflow; no GitLab live-controller activation |

## Run locally

Use Python 3.12, matching verified CI:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
./scripts/test-all.sh
```

The last verified snapshot passed 128 tests: SDK 11, Billing 5, Notification 3, GovernGate 109. Unit and fixture tests require no GitLab/Nebius secrets. They do not execute the live GitLab matrix or prove runner protection. Docker sandbox smoke validation runs separately in GitLab CI. A docs-only change does not imply new live cross-service execution.

## Configuration to reproduce on GitLab

1. Keep the four separate GitLab projects and record their IDs. The current controller fixes SDK `87600355`, controller `87601227`, Billing `87601313`, Notification `87601329`; cloning under different projects requires reviewed code/config changes and tests.
2. Protect GovernGate `main`. Use a reviewed trusted runner supporting Docker-in-Docker with TLS. Protect `governgate-controller` where the GitLab plan supports it; configure authorized maintainers/deployers. Verify actual settings in GitLab because source does not back them up.
3. Provision the least-privilege read-only GitLab API credential needed by the controller. Store only as `GOVERNGATE_API_TOKEN`, protected and masked, environment scope exactly `governgate-controller`. Restrict repository access. Do not use a broad personal PAT in SDK or untrusted MR pipelines; do not scope this variable to all environments.
4. Retain controller rules requiring protected main and multi-project pipeline source. The manual review job must have no controller environment or credential. The final freshness job must depend on both trusted-controller evidence and successful manual review.
5. Keep the deployed SDK bridge's `inherit.variables: false`, both forwarding flags false, `strategy: mirror`, main target and `allow_failure: false`. Preserve SDK unit/security, Bandit, dependency audit, Semgrep, secret detection and wheel jobs, plus the existing Duo flow.
6. Configure normal branch/merge policy separately. GovernGate does not perform merges, configure project protection from code, or guarantee availability of trial-specific features after plan changes. Keep Nebius disabled until approved access is available.

Do not paste credential values into chat, source, MR descriptions or logs. This runbook supplies configuration requirements, not a fresh audit of account settings or a claim that a read-only token can configure projects.

## Run an end-to-end SDK check

1. Open/update a same-project core-auth-sdk MR targeting main. Its detached MR pipeline runs the six existing jobs, followed by `governgate-impact` in `.post`.
2. Follow the bridge into GovernGate. Test-stage unit tests, sandbox smoke and included scans must pass. `trusted-controller` runs only on protected main for the bridge-triggered pipeline.
3. Inspect `governgate-evidence.json` and `governgate-report.md` from the actual trusted-controller job. Confirm the upstream SDK MR/head, target baseline, both consumer commits, worker image ID and the four expected runs. The current suite expects Billing 5 and Notification 3 tests per run; candidate code must not determine what evidence is trusted.
4. For a complete all-pass matrix, inspect the candidate diff and evidence limitations, then an authorized reviewer starts `manual-evidence-review`. It validates the artifact without an API token; it is blocking and not allowed to fail silently.
5. `trusted-freshness-check` revalidates the upstream relationship, open same-project MR, candidate head, target main and both consumer main refs. On change or API failure, rerun the SDK pipeline and repeat matrix/review. Do not approve by bypassing a failed job.
6. Confirm the bridge mirrors the completed downstream status. Apply the repository's review/merge policy separately. Keep the intentionally breaking demonstration MR unmerged.

## How to read failures

| Signal | Meaning and action |
| --- | --- |
| BLOCKED | Baselines passed and a candidate regressed; fix SDK or consumer compatibility, then rerun |
| INCOMPLETE_EVIDENCE | Identity/API/setup/timeout/test-report/baseline validation failed; inspect trusted logs and obtain a complete new run |
| SUPERSEDED | A source ref moved during verification; rerun matrix and review at current refs |
| Manual job waiting | Expected for all-pass evidence; reviewer must inspect and start the blocking job |
| Final freshness failure | Evidence no longer matches request/refs or API verification unavailable; rerun full SDK pipeline |

Retries are not success evidence by themselves. Keep the failed attempt, reason, retry job and final outcome in the log. The October 21 negative case needed one API-timeout retry before the Billing regression was measured.

## Latest verified live cases

| Case | SDK pipeline | Controller pipeline | Outcome |
| --- | --- | --- | --- |
| Compatible SDK MR !6 | [2972745264](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2972745264) | [2972749377](https://gitlab.com/governgate2/governgate/-/pipelines/2972749377) | Billing and Notification passed both; manual review and final freshness passed |
| Breaking SDK MR !1 | [2972745921](https://gitlab.com/governgate2/core-auth-sdk/-/pipelines/2972745921) | [2972749891](https://gitlab.com/governgate2/governgate/-/pipelines/2972749891) | Billing baseline passed/candidate failed; Notification passed both; review/finalize not run |

These are dated evidence, not a promise that every later pipeline has the same state. GitLab links may require project membership. No new SDK MR merge is implied.

## Documentation and change checklist

- Change protected controller behavior through a feature branch and reviewed MR. Keep candidate code out of trusted orchestration.
- Update architecture diagrams, component responsibilities, credential boundaries, outcome tables and runbook together.
- Run relevant regression tests; after behavior changes, execute new positive and negative live cases once deployed, and record exact SHAs, pipelines, artifacts and retries.
- Update the public snapshot and source revisions without overwriting newer GitLab code. Documentation corrections in this monorepo can differ from the original snapshot; source-revision rows describe code provenance, not a byte-for-byte promise for later edited documentation.
- Save evidence before CI artifact expiry. Back up GitLab settings separately without publishing secrets. GitHub source survives independently of the GitLab plan, but operational CI features require their own migration/plan review.

## Remaining implementation limits

Independent result attestation, an atomic freshness-to-merge guarantee, broader consumer onboarding and runner-host assurance remain future hardening. The disabled legacy analyzer still has the documented optional-parameter insertion edge case. No measured production impact or enterprise readiness is claimed. Nebius remains optional and unverified until approved access and a documented live call exist.
