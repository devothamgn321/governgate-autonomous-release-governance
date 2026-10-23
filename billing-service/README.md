# billing-service

`billing-service` authorizes a payment only after `core-auth-sdk.verify_token`
accepts the caller's login token. It is the GovernGate demo's affected
consumer: a change to the SDK's verifier signature, validation policy, or
claims can break this service.

## Authentication behavior

`billing/payments.py` reads `AUTH_SECRET` from the process environment and
fails closed when it is missing. It rejects non-positive amounts, delegates
token validation to `verify_token`, and converts invalid-token errors into
`PaymentRejected`. Billing does not parse JWTs or implement cryptography
itself. Keep secrets in the service's runtime secret store; never commit them
or expose them in CI logs.

## GovernGate verification

GovernGate snapshots the current `billing-service/main` commit and holds it
fixed across two isolated test runs:

| Run | SDK source | Consumer source |
| --- | --- | --- |
| Baseline | Current `core-auth-sdk/main` commit | Same pinned billing commit |
| Candidate | Exact SDK MR head commit | Same pinned billing commit |

The comparison detects whether candidate behavior fails where the baseline
passes. GovernGate also runs `notification-service` as a control consumer.
The SDK bridge and protected controller are deployed. In the October 21 breaking case, Billing baseline passed and candidate failed, blocking the SDK pipeline; the compatible case passed both. See the [current architecture](../ARCHITECTURE.md), [operator runbook](../IMPLEMENTATION.md) and [dated evidence](../LIVE_VERIFICATION_2026-10-21.md). An all-pass matrix still requires human review and final freshness validation.

## Local development

```bash
python -m venv .venv
. .venv/bin/activate
pip install "core-auth-sdk @ git+https://gitlab.com/governgate2/core-auth-sdk.git@v1.0.0"
pip install -r requirements.txt
pytest -v
```

For an intentional SDK compatibility check, install an explicit commit or tag
and record the exact reference. Do not treat a floating branch name as
reproducible evidence.

## CI behavior

The pipeline runs integration tests, Semgrep SAST, and secret detection. The
integration job installs `core-auth-sdk` at `SDK_REF` (default `v1.0.0`),
prints the installed SDK version and import location, saves `pip freeze` to
`installed-packages.txt`, records the billing commit and SDK ref in
`sdk-identity.txt`, and publishes JUnit results. A GovernGate candidate run
must use the verified source commit supplied by the protected controller;
`SDK_REF` in this regular pipeline is the demo baseline, not proof of a live
candidate comparison.

`AUTH_SECRET` is not needed by these tests and must not be added to untrusted
merge-request jobs. The GitLab CI job token is used only for read access to the
private SDK repository according to project allowlist policy.

## License

MIT
