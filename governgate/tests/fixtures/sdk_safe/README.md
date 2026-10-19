# core-auth-sdk

Shared token issuing and verification used by internal services. Part of the GovernGate demo environment.

It is a thin wrapper around [PyJWT](https://pyjwt.readthedocs.io). PyJWT does all the cryptography; this SDK fixes the policy:

- HS256 only (blocks `alg: none` and algorithm-confusion attacks)
- every token needs `exp` and `sub`
- the secret is always passed in, at least 32 characters, never defaulted

## API (v1.0.0)

```python
from core_auth_sdk import issue_token, verify_token, InvalidTokenError

token = issue_token("user-42", secret)          # signed, expires in 5 min
claims = verify_token(token, secret)            # raises InvalidTokenError if not trusted
```

## Consumers

| Service | Uses |
| --- | --- |
| billing-service | `verify_token` |
| notification-service | `issue_token` |

## Tests

```bash
pip install ".[test]"
pytest -v
```

The security tests (wrong secret, tampered token, expired, `alg: none`, wrong algorithm, missing claims, weak secret) must pass on every change.

## License

MIT
