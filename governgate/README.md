# GovernGate

GovernGate checks whether a proposed change to `core-auth-sdk` breaks its known
consumers. The current demo covers `billing-service` and `notification-service`.
It compares each service at one pinned commit against the SDK's current `main`
and the SDK commit under review.

The engine and protected-controller CI are merged to
[`governgate2/governgate`](https://gitlab.com/governgate2/governgate). Engine MR
[!1](https://gitlab.com/governgate2/governgate/-/merge_requests/1) was merged on
October 18, 2026 at `c702640dbef1adebb6bd47441bbc5a7619046c65`. The engine's
post-merge pipeline [2961146318](https://gitlab.com/governgate2/governgate/-/pipelines/2961146318)
passed all four jobs. The SDK bridge is still a separate proposed change; the
live API-backed controller has not yet been activated or demonstrated.

## Architecture

```text
core-auth-sdk merge request
  ├─ existing SDK unit/security checks, SAST, secret detection, and wheel build
  └─ proposed credential-free CI bridge (SDK MR !2)
       └─ typed inputs: MR IID + exact 40-character SDK head SHA
            └─ protected governgate/main controller pipeline
                 ├─ reads MR, SDK, and consumer source from GitLab API
                 ├─ checks commit identity and SHA-256 file content metadata
                 └─ sends source archives to isolated Docker workers via stdin
                      ├─ billing baseline and candidate
                      └─ notification baseline and candidate
```

The bridge is a GitLab multi-project trigger job. It executes no Python and
receives no API or Nebius key. It disables inherited variables and disables
forwarding YAML and pipeline variables. It mirrors the controller pipeline
result back to the SDK pipeline. The controller only accepts a same-project,
open SDK MR targeting `main`, and verifies that the submitted head SHA equals
the live MR head before collecting evidence.

The controller snapshots the current SDK target commit, the exact MR source
commit, and the current `main` commit of each consumer. It paginates complete
repository trees, checks each downloaded file against GitLab's SHA-256 content
metadata at the requested commit, and fails closed on missing or inconsistent
data. For each consumer it runs the same pinned source revision twice: once
against the SDK baseline and once against the candidate. It rechecks the MR
head and all baseline commits at the end; movement makes the result
`SUPERSEDED`.

The worker image is built from the reviewed controller pipeline and resolved
to its local immutable image ID before use. Workers receive only verified
source bytes over stdin. They do not receive API tokens, signing keys, host
mounts, the Docker socket, or network access. Each worker runs as an
unprivileged UID in a fresh container with a read-only root filesystem,
resource limits, dropped capabilities, and daemon log output disabled. The
controller caps captured output and removes containers after timeouts or
abnormal exits. Dependencies are fixed in the worker image; consumer
requirements cannot replace the SDK being tested. This verifies exact source
commits, not a built SDK wheel installed into each consumer.

## Evidence and verdicts

Evidence records the MR IID, target and candidate SDK identities, consumer
commit identities, source archive hashes, resolved worker image ID, and each
test outcome. If configured, the evidence ledger is HMAC-signed; verification
rejects a missing signature when a signing key is configured. No secret is
written to the report.

The controller fails closed on missing consumers, incomplete pagination,
identity mismatch, failed setup, missing or unexpected tests, zero executed
tests, timeout, output overflow, source movement, or unknown outcomes. A
candidate test failure yields `BLOCKED`. A broken baseline or incomplete run
cannot be treated as a passing result. Passing candidate tests yield
`REQUIRES_MANUAL_REVIEW`, never `READY_FOR_APPROVAL`, because candidate code
shares a process and UID with pytest and can forge JUnit contents. XML entity
payloads are rejected. Candidate results remain advisory until an independent
trusted result channel is implemented.

The protected controller performs GitLab reads during the verification flow.
Its intended credential is a short-lived group access token with `read_api`
scope, stored as a protected, masked project variable in the `governgate`
project and scoped only to the `governgate-controller` environment. The CI
bridge must never receive this credential. The legacy CLI and archived analysis
modules are separate from the protected controller path; the production
controller does not invoke automated remediation, merge-request write actions,
or Nebius. Nebius remains disabled pending API approval.

## Repository responsibilities

| Repository | Role in the demonstration |
| --- | --- |
| [`governgate`](https://gitlab.com/governgate2/governgate) | Trusted controller, GitLab source validation, evidence ledger, worker image, and smoke tests. |
| [`core-auth-sdk`](https://gitlab.com/governgate2/core-auth-sdk) | Shared JWT library and the SDK MR that supplies baseline and candidate commits. The bridge is proposed in MR [!2](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/2). |
| [`billing-service`](https://gitlab.com/governgate2/billing-service) | Affected consumer: calls `verify_token`; a verifier signature or policy change can break it. |
| [`notification-service`](https://gitlab.com/governgate2/notification-service) | Control consumer: calls `issue_token`, not `verify_token`; a verifier-only change is expected not to affect it. |

The SDK's existing six-job security pipeline and working GitLab Duo catalog
flow are preserved. The demo-preparation change is tracked separately in SDK
MR [!3](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/3); it
must not replace the newer security pipeline with an archived CI file.

## Activation and demonstration runbook

The engine is merged, but activation is a maintainer-controlled GitLab setup
step. Complete these steps in order before relying on the cross-service gate:

1. Keep `governgate/main` protected. Restrict pushes and controller changes to
   trusted maintainers and require review for changes to controller code,
   worker images, and CI configuration.
2. Disable access to protected variables and runners from merge-request
   pipelines in every affected project. In the controller project's CI/CD
   settings, set the minimum role allowed to use pipeline variables to
   `no_one_allowed`. Inputs are the only supported external parameters. This
   prevents high-precedence variables from overriding predefined values, Docker
   transport settings, Python startup, or build commands.
3. Audit group, project, and runner variables for inherited personal tokens,
   Nebius keys, and signing keys. Remove unsafe placements before enabling the
   controller. Masking alone does not isolate a secret.
4. Create a short-lived group access token with `read_api` only. Store it only
   as protected and masked project variable `GOVERNGATE_API_TOKEN` in the
   `governgate` project, scoped to `governgate-controller`. Do not put it at
   group scope or pass it to an SDK or worker job. Keep Nebius disabled.
5. Protect the `governgate-controller` environment and restrict who can run it.
   Configure the job-token allowlist narrowly so the SDK project's bridge can
   start the controller pipeline without granting unrelated project access.
6. Use a dedicated Docker-in-Docker runner with TLS certificate sharing. Do not
   mount a shared host Docker socket. Keep the worker image pinned and updated.
7. In the SDK project, require successful pipelines before merge and require
   the configured review approvals. Review the SDK bridge MR and verify its
   pipeline. The bridge belongs after the SDK's existing test, security, and
   build jobs and must not alter them. Preserve the six-job pipeline and the
   existing Duo flow.
8. Run the controller through the real SDK MR event. Confirm it reads the
   expected SDK head and consumer commits, records all four runs, attaches
   evidence, and propagates a non-passing result to the SDK pipeline. Confirm
   the SDK MR cannot be merged while the mirrored gate is non-passing.
9. Review the evidence and the MR result. For a successful demonstration, the
   expected fixture behavior is billing baseline `PASS` / candidate `FAIL` and
   notification baseline `PASS` / candidate `PASS`. Do not merge the
   intentionally breaking SDK MR into `main`.
10. Treat candidate passes as requiring human review until independent trusted
    test reporting replaces the candidate-controlled JUnit channel. A YAML
    bridge is also not an unbypassable organization-wide policy; protect it
    with approvals or a GitLab pipeline execution policy.

The controller supports detached merge-request pipelines, which provide the
source branch SHA. Merged-result pipelines use a synthetic commit SHA and are
not supported; they fail closed until the controller explicitly learns how to
bind the synthetic result to verified SDK and consumer source commits.

## Verified results and limits

The merged engine MR's final pipeline
[2961143061](https://gitlab.com/governgate2/governgate/-/pipelines/2961143061)
passed all four jobs and reported 69 tests, no new SAST findings, and no
secret-detection findings. Post-merge pipeline
[2961146318](https://gitlab.com/governgate2/governgate/-/pipelines/2961146318)
also passed all four jobs. Local tests passed 69 cases. GitLab container smoke
used archived deterministic fixtures and exercised baseline/candidate runs,
isolation, candidate early exit, forged JUnit, and output flooding. These runs
do not prove live API access or a real downstream SDK-MR gate. No
API-backed controller run, credential provisioning, or Nebius request is
claimed as complete.

## Development

```sh
pip install '.[test]' pyyaml
pytest -q
```

Container smoke and the protected controller require a Docker-in-Docker runner.
For worker-local testing, build the image with `ci/Dockerfile.worker` and run
`ci/smoke.py` with its immutable image ID. Do not run untrusted candidate
source directly on the controller host.

The repository's unchanged [`LICENSE`](LICENSE) file declares the MIT License.

## License

MIT
