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

The protected GovernGate controller and the credential-free SDK bridge are
merged to their GitLab `main` branches (GovernGate MR !5 and SDK MR !2). A live
breaking-change run resolved SDK MR
[!1](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/1) and
blocked it because Billing passed with the baseline SDK but failed with the
candidate; Notification passed both. See GovernGate pipeline
[2965778448](https://gitlab.com/governgate2/governgate/-/pipelines/2965778448).
This verifies the negative path. The positive path still needs a safe SDK
change to pass both consumers, a human evidence review, and a successful
mirrored SDK result. The bridge forwards no variables or credentials; never
pass a personal PAT or Nebius key through it. A separate SDK preparation MR
[!3](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/3) remains
open as a Draft with a failed pipeline and targets the feature branch; confirm
whether it is still needed.

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
3. Once both bridge and controller changes are reviewed and merged and
   activation is verified, the protected controller resolves the MR IID and
   exact source SHA from trusted upstream pipeline metadata.
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
