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

The engine has been merged to `governgate2/governgate/main`. The proposed
credential-free SDK bridge is tracked in
[MR !2](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/2).
Until that bridge is reviewed and the protected controller is provisioned,
the SDK pipeline does not provide a verified live GovernGate result. The
bridge passes only the SDK MR IID and full head SHA to the controller; it must
not receive an API token or Nebius key. Its result is mirrored into the SDK
pipeline after the existing tests, scans, and wheel build. The separate demo
preparation change is [MR !3](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/3).

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
3. Once the bridge is merged and activation is verified, the final bridge job
   sends the MR IID and exact source SHA to the protected GovernGate controller.
4. Review the controller evidence for the baseline and candidate runs of both
   consumers. A candidate failure blocks. A candidate pass still requires
   human review because candidate code can forge its JUnit report.
5. Merge only after required review and pipeline policy checks. Do not merge
   the intentionally breaking demo MR into `main`.

GovernGate uses a short-lived `read_api` group access token only inside its
protected controller environment. No personal PAT or Nebius key belongs in
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
