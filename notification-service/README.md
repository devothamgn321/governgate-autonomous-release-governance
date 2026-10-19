# notification-service

`notification-service` builds outgoing alert requests with a short-lived
service token. It calls `core-auth-sdk.issue_token` and never calls
`verify_token`. In the GovernGate demo it is the control consumer for a
verifier-only SDK change: the controller should test it and expect compatible
behavior while billing exercises token verification.

## Authentication behavior

`notifications/sender.py` requires `AUTH_SECRET` in the runtime environment,
then issues a token for `notification-service` with a 60-second lifetime.
Missing secrets and empty recipient/message values fail closed. The service
returns a request object; delivery is handled by the surrounding application.
Keep secrets in the service's runtime secret store and out of source control
and CI logs.

## GovernGate verification

For one SDK merge request, GovernGate runs this same pinned consumer commit
against both the current SDK baseline and the exact candidate SDK source. The
notification baseline should pass; the candidate should continue to pass
when a change only affects `verify_token`. Results are compared with the
affected `billing-service`, which calls the verifier. The engine is merged,
but the SDK bridge and protected controller activation are still pending, so
no live API-backed notification run is claimed. Read the
[GovernGate architecture and activation runbook](https://gitlab.com/governgate2/governgate/-/blob/main/README.md)
and SDK bridge [MR !2](https://gitlab.com/governgate2/core-auth-sdk/-/merge_requests/2).

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
pip install "core-auth-sdk @ git+https://gitlab.com/governgate2/core-auth-sdk.git@v1.0.0"
pip install -r requirements.txt
pytest -v
```

Use a pinned SDK ref when reproducing a comparison. A moving branch name does
not identify reproducible source.

## CI behavior

The pipeline runs integration tests, Semgrep SAST, and secret detection. The
integration job installs `core-auth-sdk` at `SDK_REF` (default `v1.0.0`),
prints the installed SDK version and import location, saves `pip freeze` to
`installed-packages.txt`, records the notification commit and SDK ref in
`sdk-identity.txt`, and publishes JUnit results. That ordinary job verifies
the configured baseline reference; it is not a live GovernGate candidate
comparison. The protected controller supplies verified source bytes to its
isolated worker for the baseline/candidate comparison.

`AUTH_SECRET` is not needed by these tests and must not be added to untrusted
merge-request jobs. The GitLab CI job token is used only for read access to
the private SDK repository according to project allowlist policy.

## License

MIT
