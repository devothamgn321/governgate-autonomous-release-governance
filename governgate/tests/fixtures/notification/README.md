# notification-service

Builds alert requests signed with a short-lived service token. Part of the GovernGate demo environment.

**Depends on:** `core-auth-sdk` — calls `issue_token` only. It never calls `verify_token`.

This is the **control** consumer: when `verify_token` changes, GovernGate should list it as a consumer of the SDK but mark it **not affected** by that change.

## Run tests locally

```bash
pip install "core-auth-sdk @ git+https://gitlab.com/governgate2/core-auth-sdk.git@v1.0.0"
pip install -r requirements.txt
pytest -v
```

## License

MIT
