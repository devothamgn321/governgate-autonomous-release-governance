# core-auth-sdk

`core-auth-sdk` is the shared JWT policy library used by the GovernGate demo's
billing and notification services. It wraps PyJWT and keeps token policy in one
place: HS256 only, required `exp` and `sub` claims, and an explicit secret of at
least 32 characters. The library does not provide a default secret.

## API (`v1.0.0`)

```python
from core_auth_sdk import issue_token, verify_token, InvalidTokenError

token = issue_token("user-42", secret)  # signed, expires in 5 minutes
claims = verify_token(token, secret)    # raises InvalidTokenError if invalid
```

The caller owns secret delivery and rotation. Services read `AUTH_SECRET` from
their runtime environment and fail closed if it is missing. Do not commit
secrets or put them in merge-request job logs.

## GovernGate relationship

GovernGate watches changes to this SDK and tests its known consumers at pinned
commits. Billing calls `verify_token`, so changes to token verification may
affect billing. Notification calls only `issue_token`; it is the control
consumer for verifier-only changes. See the [GovernGate architecture and
runbook](https://gitlab.com/governgate2/governgate/-/blob/main/README.md).

The credential-free bridge is deployed on SDK main and starts reviewed GovernGate main after the existing checks. It forwards no YAML or pipeline variables. The controller derives MR and candidate identity from GitLab's verified upstream pipeline/bridge metadata; it does not trust caller-supplied IID/SHA variables. See the [current architecture](../ARCHITECTURE.md) and [operator steps](../IMPLEMENTATION.md).

## Pipeline and merge workflow

The existing SDK pipeline has six required jobs: unit/security tests, Bandit,
dependency audit, Semgrep SAST, secret detection, and wheel build. The wheel
artifact includes a SHA-256 checksum and source commit identity. Keep these
checks intact when reviewing the bridge or demo changes. GitLab Duo's existing
catalog flow is independent and remains in place.

For an SDK change:

1. Open a merge request targeting `main`; the existing test and security jobs
   run against that change.
2. Review all six jobs and inspect the wheel source SHA and checksum.
3. The final bridge starts the protected GovernGate pipeline. The controller
   resolves the MR IID and exact candidate SHA from verified GitLab metadata.
4. Review the controller evidence for the baseline and candidate runs of both
   consumers. A candidate failure blocks. A candidate pass still requires
   human review because candidate code can forge its JUnit report.
5. After human review, the protected final freshness job must confirm the MR,
   SDK target and both consumer refs still match. Merge only after required review and pipeline policy checks. Do not merge
   the intentionally breaking demo MR into `main`.

GovernGate uses a least-privilege read-only API credential only inside its
protected controller and final freshness jobs. No personal PAT or Nebius key belongs in
SDK jobs. The controller project owns its protected credential; the bridge
does not forward secrets or arbitrary pipeline variables.

## Consumers

| Service | SDK function | Expected impact for a verifier-only change |
| --- | --- | --- |
| [`billing-service`](https://gitlab.com/governgate2/billing-service) | `verify_token` | Affected consumer; candidate behavior should be tested. |
| [`notification-service`](https://gitlab.com/governgate2/notification-service) | `issue_token` | Control consumer; expected to remain compatible. |

## Tests

```bash
pip install ".[test]"
pytest -v
```

Security coverage includes wrong secrets, tampered and expired tokens,
`alg: none`, wrong algorithms, missing claims, and weak secrets. CI publishes
JUnit results and builds a wheel with its source commit identity.

## License

MIT
