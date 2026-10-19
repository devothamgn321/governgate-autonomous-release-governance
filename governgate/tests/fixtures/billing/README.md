# billing-service

Authorizes payments after checking the caller's login token. Part of the GovernGate demo environment.

**Depends on:** `core-auth-sdk` — calls `verify_token(token, secret)` in `billing/payments.py`.

This is the consumer GovernGate should find and test when `verify_token` changes.

## Run tests locally

```bash
pip install "core-auth-sdk @ git+https://gitlab.com/governgate2/core-auth-sdk.git@v1.0.0"
pip install -r requirements.txt
pytest -v
```

## CI

`SDK_REF` (default `v1.0.0`) picks which core-auth-sdk commit is installed. Each run writes `sdk-identity.txt` and `installed-packages.txt` so the exact SDK under test is on record.

## License

MIT
